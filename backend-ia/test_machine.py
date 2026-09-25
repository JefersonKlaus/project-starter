import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
API_SECRET = os.environ.get("API_SECRET")

url = "http://127.0.0.1:8000/analisar"

headers = {"X-API-Key": API_SECRET, "Content-Type": "application/json"}

# Usamos um dicionário nativo do Python, então não precisamos brigar com aspas!
payload = {
    "prompt": "Gere a infraestrutura Terraform e o código Python para esta arquitetura para um projeto to do list"
}

print("Enviando requisição para a API...")

try:
    # O parâmetro 'json=' cuida de toda a conversão e formatação perfeitamente
    resposta = requests.post(url, headers=headers, json=payload)

    print(f"Status Code: {resposta.status_code}\n")

    if resposta.status_code == 200:
        # Pega a resposta JSON da API
        dados_json = resposta.json()

        # Define o nome do arquivo de saída
        nome_arquivo = "resultado_arquitetura.json"

        # Abre (ou cria) o arquivo e salva os dados com formatação identada e suporte a UTF-8
        with open(nome_arquivo, "w", encoding="utf-8") as arquivo:
            json.dump(dados_json, arquivo, indent=2, ensure_ascii=False)

        print(
            f"Sucesso! A resposta da arquitetura foi salva no arquivo: {nome_arquivo}"
        )
    else:
        print("Erro na API:")
        print(resposta.text)

except Exception as e:
    print(f"Erro de conexão: {e}")
