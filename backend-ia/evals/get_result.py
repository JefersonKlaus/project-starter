import sys
from pathlib import Path
import json

from validators import VALIDATORS

results_dir = Path(__file__).parent / "results"
result_file = sorted(results_dir.glob("*.json"))[-1]
results = json.loads(result_file.read_text(encoding="utf-8"))

change = " ".join(sys.argv[1:]) or "(describe the change)"
total = len(results)
passed = sum(result["passou"] for result in results)
columns = [
    f"{sum(1 for result in results if result['erros'].get(name) == [])}/{total}"
    for name in VALIDATORS
]

date = result_file.stem[:10]
print(f"| {date} | {change} ({result_file.name}) | {passed}/{total} | " + " | ".join(columns) + " |")