import json
from pathlib import Path

from validators import VALIDADORES

esperado = {
    "lambdas": 5,
    "recursos": ["aws_dynamodb_table", "aws_api_gateway_rest_api"],
}

for arquivo in sorted((Path(__file__).parent / "baseline").glob("*.json")):
    baseline = json.loads(arquivo.read_text(encoding="utf-8"))
    print(f"\n=== {arquivo.name} ===")
    for nome, validador in VALIDADORES.items():
        erros = validador(baseline, esperado)
        print(f"[{nome}] {'OK' if not erros else 'FALHOU'}")
        for erro in erros:
            print("   -", erro)