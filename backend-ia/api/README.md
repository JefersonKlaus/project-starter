# AWS Lambda (POST)

The entry point is `main.lambda_handler`, exposed as a `POST` endpoint (Lambda
Function URL or API Gateway proxy integration). The API is open: no
authentication is required. The function is deployed as a plain **zip package**
(about 13 MB): no container image, no embeddings model inside the Lambda.

Request flow and responsibilities:

```
main.py -> orchestrator.py -> request_parser.py (input: models.RequestPayload)
                           -> service_architecture.py -> service_ai.py -> rag.py / machine.py
                           -> response.py (output)
```

| Module                    | Responsibility                                                        |
| ------------------------- | --------------------------------------------------------------------- |
| `main.py`                 | Lambda handler; delegates to the orchestrator                         |
| `orchestrator.py`         | Runs parse -> service -> response and maps failures to HTTP statuses  |
| `request_parser.py`       | Serializer: API Gateway event -> `models.RequestPayload` (400/422)    |
| `models.py`               | Input model (`RequestPayload`) and generation schemas                 |
| `service_architecture.py` | Service: RAG lookup + generation + audit references                   |
| `service_ai.py`           | Service: lazy loading and caching of the RAG index and the Groq client |
| `response.py`             | Output: proxy response with JSON body and CORS headers                |
| `rag.py`                  | BM25 search over `rag_index.json`, downloaded from S3                 |
| `machine.py`              | Prompt and Groq model invocation                                      |
| `config.py`               | Environment variables (and `.env` for local runs)                     |
| `package.sh`              | Local tool: builds `lambda.zip`                                       |
| `/rag/ingest.py`          | Local tool: builds `rag_index.json` from the reference Python files  |

## Prerequisites

- Python 3.12 (the Lambda runtime)
- Virtual environment at the project root: `project-starter/.venv`
- Dependencies installed from [requirements-dev.txt](requirements-dev.txt)
  (`requirements.txt` holds only what goes into the zip; `boto3` is provided by
  the Lambda runtime and is therefore listed as a dev dependency)

### Environment variables

| Variable         | Required | Description                                                                      |
| ---------------- | -------- | -------------------------------------------------------------------------------- |
| `GROQ_API_KEY`   | yes      | Key of the Groq model used to generate the architectures                         |
| `RAG_S3_BUCKET`  | yes      | Bucket that stores `rag_index.json`                                              |
| `RAG_S3_KEY`     | no       | Object key of the index inside the bucket (default `rag_index.json`)             |
| `RAG_INDEX_PATH` | no       | Local path where the index is copied (default `/tmp/rag_index.json`)             |
| `CORS_ORIGINS`   | no       | Comma-separated browser origins echoed in `Access-Control-Allow-Origin`. Leave it unset when CORS is configured on the Function URL / API Gateway |

Locally the variables can be placed in `backend-ia/.env`; in AWS configure them
on the Lambda function.

## How the RAG works

The index is generated locally by `backend-ia/scripts/ingest_rag.py`: it reads
the reference Python files, splits them into chunks (1000 characters, 200 of
overlap, Python-aware splitter) and writes them to `rag_index.json`. No
embeddings are generated: the Lambda searches the chunks with BM25 (keyword
ranking, pure Python), which is what keeps the package small enough for a zip.

1. Build the index:

   ```bash
   cd backend-ia
   python scripts/ingest_rag.py --source <folder with the reference .py files> --output rag_index.json
   ```

2. Upload it:

   ```bash
   aws s3 cp rag_index.json s3://<bucket>/rag_index.json
   ```

On the first invocation of a container the Lambda downloads the file to
`RAG_INDEX_PATH` and builds the BM25 index in memory; warm invocations reuse
both, as well as the Groq client. After uploading a new index, running containers
keep the old copy until they are recycled; redeploy (or wait) to refresh them.

The query is enriched with AWS/serverless terms before the search, as before, and
the three best chunks are sent to Groq as `[CONTEXTO RAG]`.

## Request and response

Send a JSON body:

```json
{
  "prompt": "Generate a TO DO list application without Cognito authentication"
}
```

```bash
curl -X POST https://<function-url>/ \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Generate a TO DO list application without Cognito authentication"}'
```

The handler always returns an API Gateway proxy response
(`statusCode`, `headers`, `body`). Status codes:

| Status | Meaning                                                              |
| ------ | -------------------------------------------------------------------- |
| 200    | Architecture generated (`rag_references` lists the RAG sources used) |
| 400    | Body is not valid JSON                                               |
| 422    | Body does not match the schema (`prompt` is required)                |
| 500    | Generation failed                                                    |

Errors carry a `{"detail": ...}` body.

## Invoke locally

```bash
cd backend-ia/api
source ../../.venv/bin/activate
python -m pip install -r requirements-dev.txt
python -c '
import json, main
event = {"body": json.dumps({"prompt": "Generate a TO DO list application"})}
print(json.dumps(main.lambda_handler(event, None), indent=2))
'
```

To test without S3, point `RAG_INDEX_PATH` to a local `rag_index.json`: when the
file already exists the download is skipped.

Run the tests with `python -m pytest tests`.

## Deploying (manual)

```bash
export AWS_REGION=us-east-1
export ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export BUCKET=cloud-specialist-rag-$ACCOUNT
export FUNCTION=cloud-specialist-create
```

1. **Build and upload the index** (see "How the RAG works"):

   ```bash
   aws s3 mb s3://$BUCKET
   python ../scripts/ingest_rag.py --source <reference folder> --output rag_index.json
   aws s3 cp rag_index.json s3://$BUCKET/rag_index.json
   ```

2. **Build the package**: `./package.sh` produces `lambda.zip` with the code and
   the Linux/Python 3.12 wheels of `requirements.txt`.

3. **Execution role**:

   ```bash
   aws iam create-role --role-name $FUNCTION-role --assume-role-policy-document \
     '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
   aws iam attach-role-policy --role-name $FUNCTION-role \
     --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
   aws iam put-role-policy --role-name $FUNCTION-role --policy-name rag-s3-read --policy-document \
     "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"s3:GetObject\",\"Resource\":\"arn:aws:s3:::$BUCKET/rag_index.json\"}]}"
   ```

4. **Create the function** (IAM is eventually consistent: retry after a few seconds if the role is rejected):

   ```bash
   aws lambda create-function \
     --function-name $FUNCTION \
     --runtime python3.12 --architectures x86_64 \
     --handler main.lambda_handler \
     --zip-file fileb://lambda.zip \
     --role arn:aws:iam::$ACCOUNT:role/$FUNCTION-role \
     --memory-size 1024 --timeout 300 \
     --environment "Variables={GROQ_API_KEY=gsk_...,RAG_S3_BUCKET=$BUCKET}"
   aws lambda wait function-active-v2 --function-name $FUNCTION
   ```

5. **Public endpoint** (Function URL: open, POST, up to 15 minutes of execution):

   ```bash
   aws lambda create-function-url-config --function-name $FUNCTION --auth-type NONE \
     --cors '{"AllowOrigins":["*"],"AllowMethods":["POST"],"AllowHeaders":["content-type"]}'
   aws lambda add-permission --function-name $FUNCTION --statement-id public-url \
     --action lambda:InvokeFunctionUrl --principal "*" --function-url-auth-type NONE
   aws lambda get-function-url-config --function-name $FUNCTION --query FunctionUrl --output text
   ```

   API Gateway HTTP API also works, but its 30 s integration timeout is shorter
   than a typical Groq generation.

6. **Test and watch the logs**:

   ```bash
   aws logs tail /aws/lambda/$FUNCTION --follow
   ```

Updating later: `./package.sh && aws lambda update-function-code --function-name $FUNCTION --zip-file fileb://lambda.zip`
for code changes; re-run `ingest_rag.py` + `aws s3 cp rag_index.json s3://$BUCKET/rag_index.json` for RAG changes.

Because the endpoint is public, consider a concurrency limit
(`--reserved-concurrent-executions 5`) or API Gateway throttling to avoid
abuse of the Groq quota.

Do not put real keys in commands, documentation, or commits. If a key has been
exposed, revoke it and generate a new one with the corresponding provider.
