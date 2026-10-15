# Local FastAPI API

The API is defined in [main.py](main.py) and exposes the `POST /analisar` endpoint.

## Prerequisites

- Python 3.10+
- Virtual environment at the project root: `project-starter/.venv`
- Dependencies installed from [requirements-dev.txt](requirements-dev.txt)
- `backend-ia/.env` containing `GROQ_API_KEY` and `API_SECRET`

`GROQ_API_KEY` is required: the API uses a model hosted by Groq to generate
architectures. Without this variable, the application cannot complete startup.
`API_SECRET` protects the endpoint through the `X-API-Key` header.

From the project root, install the dependencies once:

```bash
source .venv/bin/activate
python -m pip install -r backend-ia/api/requirements-dev.txt
```

## Run locally

```bash
cd /home/klaus/code/project-starter/backend-ia/api
source ../../.venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

To reload automatically during development:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The model and vector database are loaded at startup; the first initialization
may take some time. Open `http://127.0.0.1:8000/docs` for the Swagger documentation.

## Endpoint

The request body is JSON, not `multipart/form-data`:

```json
{
  "prompt": "Generate a TO DO list application without Cognito authentication"
}
```

Example using `curl`:

```bash
curl -X POST http://127.0.0.1:8000/analisar \
  -H "Content-Type: application/json" \
  -H "X-API-Key: SUA_API_SECRET" \
  -d '{"prompt":"Generate a TO DO list application without Cognito authentication"}'
```

The recommended script for the local workflow is
[`../test_machine.py`](../test_machine.py). It reads `API_SECRET` from `.env`, sends
the prompt as JSON, and saves the response as `backend-ia/resultado_arquitetura.json`.

## Install cloudflared on Linux

If `cloudflared` is not installed yet:

```bash
curl -L --output cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
```

## Expose with cloudflared (optional)

With the local API running, open another terminal and run:

```bash
cloudflared tunnel --url http://127.0.0.1:8000 --metrics localhost:45678
```

Do not put real keys in commands, documentation, or commits. If a key has been
exposed, revoke it and generate a new one with the corresponding provider.