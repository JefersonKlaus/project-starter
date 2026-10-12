import sys
from pathlib import Path
import json

from validators import VALIDADORES

pasta = Path(__file__).parent / "results"
arquivo = sorted(pasta.glob("*.json"))[-1]
dados = json.loads(arquivo.read_text(encoding="utf-8"))

mudanca = " ".join(sys.argv[1:]) or "(descreva a mudança)"
total = len(dados)
aprovados = sum(r["passou"] for r in dados)
colunas = [
    f"{sum(1 for r in dados if r['erros'].get(n) == [])}/{total}"
    for n in VALIDADORES
]

data = arquivo.stem[:10]
print(f"| {data} | {mudanca} ({arquivo.name}) | {aprovados}/{total} | " + " | ".join(colunas) + " |")