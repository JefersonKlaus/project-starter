import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
API_SECRET = os.environ.get("API_SECRET")

url = "http://127.0.0.1:8000/create"

headers = {"X-API-Key": API_SECRET, "Content-Type": "application/json"}

payload = {
    "prompt": "To-do list application. The user can create a task, list all tasks, retrieve a task by ID, update a task, and remove a task."
}

print("Sending request to the API...")

try:
    response = requests.post(url, headers=headers, json=payload)

    print(f"Status Code: {response.status_code}\n")

    if response.status_code == 200:
        response_json = response.json()
        file_name = "resultado_arquitetura.json"

        with open(file_name, "w", encoding="utf-8") as file:
            json.dump(response_json, file, indent=2, ensure_ascii=False)

        print(
            f"Success! The architecture response was saved to the file: {file_name}"
        )
    else:
        print("API error:")
        print(response.text)

except Exception as e:
    print(f"Connection error: {e}")
