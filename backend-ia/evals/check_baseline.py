import json
from pathlib import Path

from validators import VALIDATORS

expected = {
    "lambdas": 5,
    "recursos": ["aws_dynamodb_table", "aws_api_gateway_rest_api"],
}

for file in sorted((Path(__file__).parent / "baseline").glob("*.json")):
    baseline = json.loads(file.read_text(encoding="utf-8"))
    print(f"\n=== {file.name} ===")
    for name, validator in VALIDATORS.items():
        errors = validator(baseline, expected)
        print(f"[{name}] {'OK' if not errors else 'FAILED'}")
        for error in errors:
            print("   -", error)
