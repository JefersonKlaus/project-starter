import json
import os
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

from validators import VALIDATORS

load_dotenv()
URL = os.getenv("EVAL_URL", "http://localhost:8000/create")
API_KEY = os.getenv("API_SECRET")
EVALS_DIR = Path(__file__).parent


def run_case(case):
    record = {"id": case["id"], "erro_api": None, "erros": {}}
    try:
        response = requests.post(
            URL,
            json={"prompt": case["prompt"]},
            headers={"X-API-Key": API_KEY},
            timeout=600,
        )
        response.raise_for_status()
        output = response.json()
    except Exception as e:
        record["erro_api"] = str(e)
        record["passou"] = False
        return record

    record["saida"] = output
    for name, validator in VALIDATORS.items():
        try:
            record["erros"][name] = validator(output, case["esperado"])
        except Exception as e:
            record["erros"][name] = [f"validator failed: {e!r}"]

    record["passou"] = all(not errors for errors in record["erros"].values())
    return record


def main():
    cases = json.loads((EVALS_DIR / "prompts.json").read_text(encoding="utf-8"))
    results = []

    for case in cases:
        print(f"Running {case['id']}...", flush=True)
        record = run_case(case)
        results.append(record)
        print("  ->", "PASSED" if record["passou"] else "FAILED")
        if record["erro_api"]:
            print("     API error:", record["erro_api"])
        for name, errors in record["erros"].items():
            for error in errors:
                print(f"     [{name}] {error}")

    total = len(results)
    passed = sum(result["passou"] for result in results)
    print(f"\nPassed cases: {passed}/{total}")
    for name in VALIDATORS:
        ok = sum(1 for result in results if result["erros"].get(name) == [])
        print(f"  {name}: {ok}/{total}")

    results_dir = EVALS_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    result_file = results_dir / f"{datetime.now():%Y-%m-%d_%H%M}.json"
    result_file.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nDetails saved to {result_file}")


if __name__ == "__main__":
    main()
