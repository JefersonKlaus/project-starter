# AWS Lambda (POST)

The entry point is `main.lambda_handler`, exposed as a `POST` endpoint (Lambda
Function URL or API Gateway proxy integration). The API is open: no
authentication is required. The function is deployed as a plain **zip package**
with a dependencies layer: no container image, no embeddings model inside the
Lambda. The zip is flat (`main.py` at its root), which is why the modules import
each other as top-level modules (`import orchestrator`, `from ai.rag import ...`).

Request flow and responsibilities:

```
main.py -> orchestrator.py -> request_parser.py (input: models.RequestPayload)
                           -> service_architecture.py -> service_ai.py -> ai/rag.py / ai/machine.py
                           -> response.py (output)
```

| Module                    | Responsibility                                                         |
| ------------------------- | ---------------------------------------------------------------------- |
| `main.py`                 | Lambda handler; delegates to the orchestrator                          |
| `orchestrator.py`         | Runs parse -> service -> response and maps failures to HTTP statuses   |
| `request_parser.py`       | Serializer: API Gateway event -> `models.RequestPayload` (400/422)     |
| `models.py`               | Input model (`RequestPayload`)                                         |
| `service_architecture.py` | Service: RAG lookup + generation + audit references                    |
| `service_ai.py`           | Service: downloads the RAG index from S3, caches the index and the LLM |
| `response.py`             | Output: proxy response with JSON body and CORS headers                 |
| `config.py`               | Environment variables (and `.env` for local runs)                      |
| `ai/rag.py`               | BM25 search over `rag_index.json`                                      |
| `ai/machine.py`           | Prompt and Groq model invocation                                       |
| `ai/models.py`            | Output schema (`AWSArchitecture`) validated with Pydantic              |
| `../run_local.py`         | Local tool: invokes the handler on your machine (see "Run locally")    |
| `../../rag/ingest.py`     | Local tool: builds `rag_index.json` from the reference Python files    |

## Prerequisites

- Python 3.12 (the Lambda runtime)
- A virtual environment, e.g. `project-starter/.venv`
- Dependencies installed from [requirements-dev.txt](requirements-dev.txt)
  (`requirements.txt` holds only what goes into the Lambda layer; `boto3` is
  provided by the Lambda runtime and is therefore listed as a dev dependency)

### Environment variables

| Variable         | Required | Description                                                                      |
| ---------------- | -------- | -------------------------------------------------------------------------------- |
| `GROQ_API_KEY`   | yes      | Key of the Groq model used to generate the architectures                         |
| `RAG_S3_BUCKET`  | yes*     | Bucket that stores `rag_index.json` (*not needed when `RAG_INDEX_PATH` exists)   |
| `RAG_S3_KEY`     | no       | Object key of the index inside the bucket (default `rag_index.json`)             |
| `RAG_INDEX_PATH` | no       | Local path of the index (default `/tmp/rag_index.json`). If the file exists, the S3 download is skipped |
| `CORS_ORIGINS`   | no       | Comma-separated browser origins echoed in `Access-Control-Allow-Origin`. Leave it unset when CORS is configured on the Function URL / API Gateway |

In AWS these are set by Terraform (`infra/main.tf`). Locally, put them in
`backend-ia/.env` (git-ignored): `config.py` loads that file on import, without
overriding variables already present in the shell. Start from
[`backend-ia/.env.example`](../.env.example).

## How the RAG works

The index is generated locally by `backend-ia/rag/ingest.py`: it reads the
reference Python files, splits them into chunks (1000 characters, 200 of
overlap, Python-aware splitter) and writes them to `rag_index.json`. No
embeddings are generated: the Lambda searches the chunks with BM25 (keyword
ranking, pure Python), which is what keeps the package small enough for a zip.

1. Build the index (always pass `--source`; without it the script indexes this
   API's own code, which is useless as a reference):

   ```bash
   cd backend-ia
   python rag/ingest.py --source <folder with the reference .py files> --output rag_index.json
   ```

2. Upload it to the bucket of the environment (dev = `sandbox-<RAG_BUCKET>`):

   ```bash
   aws s3 cp rag_index.json s3://sandbox-project-starter-backend-ia-rag/rag_index.json
   ```

On the first invocation of a container the Lambda downloads the file to
`RAG_INDEX_PATH` and builds the BM25 index in memory; warm invocations reuse
both, as well as the Groq client. After uploading a new index, running containers
keep the old copy until they are recycled; redeploy (or wait) to refresh them.
Terraform grants the function `s3:GetObject` on that single object only, so a
missing file shows up as a `403 Forbidden` (S3 hides 404 without `ListBucket`).

The query is enriched with AWS/serverless terms before the search and the three
best chunks are sent to Groq as `[CONTEXTO RAG]`.

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
(`statusCode`, `headers`, `body`); REST API (v1) and HTTP API / Function URL
(v2) events are both accepted. Status codes:

| Status | Meaning                                                              |
| ------ | -------------------------------------------------------------------- |
| 200    | Architecture generated (`rag_references` lists the RAG sources used) |
| 400    | Body is not valid JSON                                               |
| 422    | Body does not match the schema (`prompt` is required)                |
| 500    | Generation failed                                                    |

Errors carry a `{"detail": ...}` body.

## Run locally

`run_local.py` calls `main.lambda_handler` exactly as the Lambda runtime does:
it builds a proxy event, loads `backend-ia/.env`, and prints the response.
Nothing is mocked, so a real Groq call is made.

1. **Install the dev dependencies** (once):

   ```bash
   cd backend-ia/api
   python -m venv ../../.venv && source ../../.venv/bin/activate   # Windows: ..\..\.venv\Scripts\activate
   python -m pip install -r requirements-dev.txt
   ```

2. **Create `backend-ia/.env`** from the example and set `GROQ_API_KEY`:

   ```bash
   cp ../.env.example ../.env
   ```

3. **Get a RAG index.** Either build one locally (no AWS needed):

   ```bash
   python ../rag/ingest.py --source <folder with the reference .py files> --output ../rag_index.json
   ```

   `run_local.py` picks up `backend-ia/rag_index.json` or `backend-ia/rag/rag_index.json`
   automatically (or use `RAG_INDEX_PATH` / `--index`). Or set `RAG_S3_BUCKET` in `.env` and have AWS
   credentials in your shell to download the same file the Lambda uses.

4. **Invoke**:

   ```bash
   python run_local.py                                        # default prompt
   python run_local.py --prompt "Crie uma API de produtos com DynamoDB"
   python run_local.py --event event.json                     # a full proxy event, e.g. copied from the AWS console
   python run_local.py --output result.json                   # save the response body
   python run_local.py --write-code ./generated               # dump the Terraform/Python files it generated
   python run_local.py --raw                                  # show statusCode/headers/body as the Lambda returns them
   ```

   The exit code is `0` on HTTP 200 and `1` otherwise, so it can be used in scripts.

What the script does, in order: load `.env` -> resolve the index
(`--index` > `RAG_INDEX_PATH` > `backend-ia/rag_index.json` > S3) -> check
`GROQ_API_KEY` -> import `main` (only now, because `config.py` reads the
environment at import time) -> call the handler -> print / save the result.

### Tests

```bash
cd backend-ia/api
python -m pytest
```

The tests never call Groq or S3 (everything external is mocked) and run in CI on
every pull request.

## Deploying

Deployment is done by Terraform (`infra/`) through the **Deploy Lambdas** GitHub
workflow (`.github/workflows/deploy.yml`): it runs the tests, zips
`lambda_create/` (flat, `main.py` at the root), builds the dependencies layer
from `requirements.txt`, and applies to the environment's AWS account. It runs
automatically on pushes to `main` (development) and manually for stage/prod.

Terraform does **not** create the RAG bucket nor upload the index: do that once
per environment (see "How the RAG works"). When the Lambda runs behind API
Gateway, use a proxy integration and configure CORS on the API (the function
only echoes `CORS_ORIGINS`; it does not answer `OPTIONS` preflights).

Because the endpoint is public, consider a concurrency limit
(`reserved_concurrent_executions`) or API Gateway throttling to avoid abuse of
the Groq quota.

Do not put real keys in commands, documentation, or commits. If a key has been
exposed, revoke it and generate a new one with the corresponding provider.
