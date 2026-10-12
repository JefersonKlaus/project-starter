# API FastAPI local

A API está definida em [main.py](main.py) e expõe o endpoint `POST /analisar`.

## Pré-requisitos

- Python 3.10+
- Ambiente virtual na raiz do projeto: `project-starter/.venv`
- Dependências instaladas com [requirements.txt](requirements.txt)
- `backend-ia/.env` contendo `GROQ_API_KEY` e `API_SECRET`

`GROQ_API_KEY` é obrigatória: a API usa o modelo hospedado na Groq para gerar
as arquiteturas. Sem essa variável, a aplicação não conclui o startup. O
`API_SECRET` protege o endpoint com o header `X-API-Key`.

Na raiz do projeto, instale as dependências uma vez:

```bash
source .venv/bin/activate
python -m pip install -r backend-ia/api/requirements.txt
```

## Rodar localmente

```bash
cd /home/klaus/code/project-starter/backend-ia/api
source ../../.venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Para recarregar automaticamente durante o desenvolvimento:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

O modelo e o banco vetorial são carregados no startup; a primeira inicialização
pode demorar. Acesse `http://127.0.0.1:8000/docs` para a documentação Swagger.

## Endpoint

O corpo é JSON, não `multipart/form-data`:

```json
{
  "prompt": "Gere um aplicativo TO DO list sem autenticação via Cognito"
}
```

Exemplo com `curl`:

```bash
curl -X POST http://127.0.0.1:8000/analisar \
  -H "Content-Type: application/json" \
  -H "X-API-Key: SUA_API_SECRET" \
  -d '{"prompt":"Gere um aplicativo TO DO list sem autenticação via Cognito"}'
```

O script recomendado para o fluxo local é
[`../test_machine.py`](../test_machine.py). Ele lê `API_SECRET` do `.env`, envia
o prompt em JSON e salva a resposta como `backend-ia/resultado_arquitetura.json`.

## Instalar o cloudflared no Linux

Se o `cloudflared` ainda não estiver instalado:

```bash
curl -L --output cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
```

## Expor com cloudflared (opcional)

Com a API local rodando, abra outro terminal e execute:

```bash
cloudflared tunnel --url http://127.0.0.1:8000 --metrics localhost:45678
```

Não coloque chaves reais em comandos, documentação ou commits. Se uma chave foi
exposta, revogue-a e gere outra no provedor correspondente.