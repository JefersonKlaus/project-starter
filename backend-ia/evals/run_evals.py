import json
import os
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

from validators import VALIDADORES

load_dotenv()
URL = os.getenv("EVAL_URL", "http://localhost:8000/analisar")
API_KEY = os.getenv("API_SECRET")
PASTA = Path(__file__).parent


def rodar_caso(caso):
    registro = {"id": caso["id"], "erro_api": None, "erros": {}}
    try:
        r = requests.post(
            URL,
            json={"prompt": caso["prompt"]},
            headers={"X-API-Key": API_KEY},
            timeout=600,
        )
        r.raise_for_status()
        saida = r.json()
    except Exception as e:
        registro["erro_api"] = str(e)
        registro["passou"] = False
        return registro

    registro["saida"] = saida
    for nome, validador in VALIDADORES.items():
        try:
            registro["erros"][nome] = validador(saida, caso["esperado"])
        except Exception as e:
            registro["erros"][nome] = [f"validador quebrou: {e!r}"]

    registro["passou"] = all(not erros for erros in registro["erros"].values())
    return registro


def main():
    casos = json.loads((PASTA / "prompts.json").read_text(encoding="utf-8"))
    resultados = []

    for caso in casos:
        print(f"Rodando {caso['id']}...", flush=True)
        registro = rodar_caso(caso)
        resultados.append(registro)
        print("  ->", "PASSOU" if registro["passou"] else "FALHOU")
        if registro["erro_api"]:
            print("     erro da API:", registro["erro_api"])
        for nome, erros in registro["erros"].items():
            for erro in erros:
                print(f"     [{nome}] {erro}")

    total = len(resultados)
    aprovados = sum(r["passou"] for r in resultados)
    print(f"\nCasos aprovados: {aprovados}/{total}")
    for nome in VALIDADORES:
        ok = sum(1 for r in resultados if r["erros"].get(nome) == [])
        print(f"  {nome}: {ok}/{total}")

    pasta_saida = PASTA / "results"
    pasta_saida.mkdir(exist_ok=True)
    arquivo = pasta_saida / f"{datetime.now():%Y-%m-%d_%H%M}.json"
    arquivo.write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nDetalhes salvos em {arquivo}")


if __name__ == "__main__":
    main()