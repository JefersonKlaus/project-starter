# Evals

Testes automatizados para medir a qualidade das arquiteturas geradas pelo `POST /analisar`.

A ideia é simples: uma lista fixa de pedidos (`prompts.json`) é enviada para a API, cada resposta passa por validadores automáticos e o resultado vira uma **nota comparável entre execuções**. Toda mudança no sistema (prompt, RAG, modelo, template Terraform) só é aceita se a nota subir ou ficar igual.

## Estrutura

```
evals/
├── baseline/resultado_arquitetura.json   # saída ruim conhecida (deve reprovar)
├── results/                              # uma execução por arquivo (AAAA-MM-DD_HHMM.json)
├── prompts.json                          # casos de teste e o que se espera de cada um
├── validators.py                         # funções que apontam erros
├── run_evals.py                          # roda todos os casos contra a API
├── check_baseline.py                     # testa os validadores sem chamar a API
├── NOTAS.md                              # histórico de notas por mudança
└── README.md
```

## Requisitos

- Python 3.10+
- `pip install requests python-dotenv`
- Terraform instalado e disponível no PATH (`terraform version` deve funcionar no mesmo terminal). Sem ele, o validador `terraform` reprova todos os casos.
- API rodando (`cd api && uvicorn main:app --host 0.0.0.0 --port 8000`)
- `GROQ_API_KEY` definida no `.env`, pois a API consome o modelo hospedado na Groq
- `API_SECRET` definido no `.env`, para autenticar as requisições

Recomendado para acelerar o `terraform init` (baixa o provider da AWS):

```bash
mkdir -p ~/.terraform-cache
export TF_PLUGIN_CACHE_DIR=~/.terraform-cache
```

## Variáveis de ambiente

| Variável | Padrão | Uso |
|---|---|---|
| `GROQ_API_KEY` | (obrigatória) | Acesso ao modelo usado pela API |
| `API_SECRET` | (obrigatória) | Enviada no header `X-API-Key` |
| `EVAL_URL` | `http://localhost:8000/analisar` | Endereço da API |

## Como rodar

Os comandos abaixo devem ser executados dentro de `backend-ia/`, com a API em
outro terminal:

```bash
# 1. Verifica todos os JSONs presentes em evals/baseline (não usa a API)
python evals/check_baseline.py

# 2. Roda todos os casos contra a API
python evals/run_evals.py
```

## Fluxo de um prompt manual

Para testar o prompt CRUD usado em `test_machine.py`:

```bash
python test_machine.py
```

Com HTTP `200`, o arquivo gerado fica em
`backend-ia/resultado_arquitetura.json`. Para que `check_baseline.py` o leia,
mova-o para a pasta esperada:

```bash
mv resultado_arquitetura.json evals/baseline/resultado_arquitetura.json
python evals/check_baseline.py
```

Use `cp` no lugar de `mv` para preservar o arquivo na raiz. O comando de
checagem percorre todos os `*.json` de `evals/baseline`, portanto remova ou
renomeie resultados antigos se quiser avaliar somente um arquivo.

O prompt manual atual é:

```text
Aplicativo de lista de tarefas (to-do list). O usuário pode criar uma tarefa, listar todas as tarefas, consultar uma tarefa por id, atualizar uma tarefa e remover uma tarefa.
```

### Saída esperada

```
Rodando crud-basico...
  -> FALHOU
     [consistencia] esperava 4 Lambdas, veio 0
...
Casos aprovados: X/12
  python: X/12
  tf_nao_vazio: X/12
  regras_tf: X/12
  consistencia: X/12
  terraform: X/12

Detalhes salvos em evals/results/2026-09-29_1030.json
```

Um caso só **passa** se todos os validadores aprovarem. Erros de API (timeout, 401, 500, JSON inválido do modelo) contam como falha e o runner continua.

## Validadores

Cada validador recebe `(resultado, esperado)` e devolve uma lista de erros. Lista vazia significa que passou.

| Nome | O que verifica |
|---|---|
| `python` | Sintaxe válida (`ast.parse`), sem `httpMethod`, sem `return json.dumps(` direto, sem ler `region`/`table_name` do `event` |
| `tf_nao_vazio` | O Terraform tem pelo menos 3 recursos. Evita que os outros validadores aprovem "no vazio" |
| `regras_tf` | Sem `source_arn = "*"` e runtime Python >= 3.10 |
| `consistencia` | Nº de `.py` igual ao nº de `aws_lambda_function`; igual ao esperado; roles e permissions para cada Lambda; recursos obrigatórios presentes |
| `terraform` | `terraform init -backend=false` e `terraform validate` numa pasta temporária |

Para adicionar um validador, escreva a função em `validators.py` e registre no dicionário `VALIDADORES`. O runner usa o dicionário, então nada mais muda.

## Casos de teste (`prompts.json`)

```json
{
  "id": "crud-basico",
  "prompt": "API CRUD de itens com DynamoDB",
  "esperado": {
    "lambdas": 4,
    "recursos": ["aws_dynamodb_table", "aws_api_gateway_rest_api"]
  }
}
```

- `id`: nome curto do caso.
- `prompt`: o pedido enviado à API.
- `esperado.lambdas`: quantas Lambdas devem existir.
- `esperado.recursos`: tipos de recurso Terraform que devem aparecer.

O campo `esperado` só pode conter o que uma máquina consegue verificar. "Código bom" não vira teste.

Os 12 casos cobrem: CRUD (com variação de redação), só leitura, só criação, só exclusão, duas entidades, fila SQS, upload S3, autenticação Cognito e Lambda agendada. Os casos difíceis tendem a reprovar no começo, e isso é esperado.

Atenção a falsos positivos: se o modelo usar `aws_apigatewayv2_api` em vez de `aws_api_gateway_rest_api`, o validador reprova um resultado que pode estar correto. Nesse caso, ajuste o `esperado`, não o sistema.

## Fluxo de trabalho

1. **Baseline dos validadores:** coloque o JSON em `evals/baseline/` e execute `python evals/check_baseline.py`. O script usa `esperado = {"lambdas": 5, ...}` definido em `check_baseline.py`, diferente dos casos de `prompts.json`. Se algum validador aprovar algo que deveria reprovar, corrija o validador antes de seguir.
2. **Nota inicial:** rode `run_evals.py` 2 ou 3 vezes e anote a média. Isso mostra a oscilação natural do modelo.
3. **Registre no `NOTAS.md`:** uma linha por mudança, com a descrição do que foi alterado.
4. **Mude uma coisa por vez** e rode de novo. Se a nota sobe, mantenha. Se cai ou fica igual, reverta ou investigue.
5. **Diagnostique falhas:** abra o campo `saida` de um caso em `results/` e veja o que o modelo gerou.

### Reduzindo o ruído

Durante os evals, use `temperature=0.1` e `do_sample=True` no `machine.py`. Com temperatura alta a nota oscila mesmo sem nenhuma mudança no código.

## Como ler os resultados

| O que você vê | Significa | Próximo passo |
|---|---|---|
| Muitos `erro_api` (parser, timeout) | O JSON gigante é frágil | Geração em etapas: plano em JSON, um arquivo por chamada |
| `python` baixo | O modelo erra sintaxe | Loop de reparo com `ast.parse` devolvendo o erro ao modelo |
| `consistencia` e `terraform` baixos | O modelo erra o Terraform | Terraform por template (Jinja) |
| Só os casos difíceis falham | O básico funciona | Ajustar o RAG (indexar `.tf`, excluir testes) |
| Nota igual com prompt antigo e novo | O prompt não é o gargalo | Não gastar mais tempo nele |

### Resultados observados no prompt manual

As execuções de `test_machine.py` retornaram HTTP `200` e salvaram o JSON. Os
validadores, porém, encontraram problemas diferentes em cada geração:

- geração inicial: imports ausentes (`os` e `logging`), uma Lambda para quatro
  arquivos Python e apenas uma rota;
- geração seguinte: cinco Lambdas, mas Terraform inválido por `output
  "api_url"` duplicado;
- geração seguinte: `stage_name` usado diretamente em
  `aws_api_gateway_deployment`, argumento não suportado;
- geração mais recente: consistência e rotas aprovadas, mas `terraform validate`
  falhou porque `lambda/create_task.zip` e outros artefatos referenciados por
  `filebase64sha256` não existem.

Isso significa que o request e os validadores estão executando; as reprovações
estão no Terraform e no código gerado. Antes de interpretar a nota, corrija o
erro reportado e execute a checagem novamente. O validador Terraform precisa de
Terraform instalado e dos arquivos `.zip` esperados pelo resultado.

Cuidado com leituras enganosas: uma coluna com 12/12 pode ser falso positivo (por exemplo, `regras_tf` aprova quando não há nenhuma Lambda no Terraform). Por isso existe o `tf_nao_vazio`. E uma coluna com 0/12 pode ser problema de ambiente (Terraform não instalado), não do modelo.

## Diagnóstico rápido de um resultado

Rode de dentro de `backend/`:

```python
import json
from pathlib import Path

arquivos = sorted(Path("evals/results").glob("*.json"))
dados = json.loads(arquivos[-1].read_text(encoding="utf-8"))

for r in dados:
    s = r.get("saida")
    if not s:
        print(r["id"], "| sem saída:", r["erro_api"])
        continue
    tf = s["generated_code"]["terraform"]
    py = s["generated_code"]["python"]
    todo = "\n".join(tf.values())
    print(
        r["id"],
        "| tf arquivos:", list(tf),
        "| resources:", todo.count('resource "'),
        "| py:", [n for n in py if n.endswith(".py")],
    )
```

## Registro de notas (`NOTAS.md`)

```markdown
| Data | Mudança | Aprovados | Python | TF vazio | Regras TF | Consistência | Terraform |
|------|---------|-----------|--------|----------|-----------|--------------|-----------|
|      | Linha de base (temp 0.1) | /12 | /12 | /12 | /12 | /12 | /12 |
```

Uma nota só serve como régua se foi medida com todos os validadores funcionando e o ambiente correto.

## Limitações conhecidos

- Os validadores checam estrutura e regras estáticas. Não executam as Lambdas nem fazem `terraform plan/apply`.
- `terraform validate` não detecta permissões excessivas nem más práticas. Para isso, considere adicionar `tflint` e `checkov`.
- A checagem por regex de recursos não entende módulos nem `count`/`for_each`.
- O modelo tem aleatoriedade: só considere melhoria o que passa da oscilação medida entre execuções idênticas.