"""Validadores: cada um recebe (resultado, esperado) e devolve uma lista de erros.
Lista vazia = passou.

Para adicionar um validador novo: escreva a função e registre em VALIDADORES.
"""
import ast
import io
import re
import subprocess
import tempfile
from pathlib import Path

from pyflakes import api as pyflakes_api
from pyflakes import reporter as pyflakes_reporter


# ---------------------------------------------------------------- helpers
def _terraform(resultado):
    return "\n".join(resultado["generated_code"]["terraform"].values())


def _arquivos_py(resultado):
    return {
        nome: codigo
        for nome, codigo in resultado["generated_code"]["python"].items()
        if nome.endswith(".py")
    }


# ---------------------------------------------------------------- python
def validar_python(resultado, esperado=None):
    """Sintaxe válida e regras do prompt (sem roteamento interno, retorno em dict,
    configuração via os.environ)."""
    erros = []
    for nome, codigo in _arquivos_py(resultado).items():
        try:
            ast.parse(codigo)
        except SyntaxError as e:
            erros.append(f"{nome}: erro de sintaxe na linha {e.lineno}")
            continue
        if "httpMethod" in codigo:
            erros.append(f"{nome}: roteamento interno (regra 2)")
        if re.search(r"return\s+json\.dumps\(", codigo):
            erros.append(f"{nome}: retorna string em vez de dict (API Gateway proxy)")
        if re.search(r"event\[\s*['\"](region|table_name)['\"]\s*\]", codigo):
            erros.append(f"{nome}: lê region/table_name do event (use os.environ)")
    return erros


def validar_pyflakes(resultado, esperado=None):
    """Pega nomes indefinidos (ex: os/logging sem import), que passam no ast.parse
    mas quebram com NameError na primeira invocação."""
    erros = []
    for nome, codigo in _arquivos_py(resultado).items():
        try:
            ast.parse(codigo)
        except SyntaxError:
            continue  # já reportado por validar_python
        saida = io.StringIO()
        rep = pyflakes_reporter.Reporter(saida, saida)
        pyflakes_api.check(codigo, nome, rep)
        for linha in saida.getvalue().splitlines():
            if "undefined name" in linha:
                erros.append(linha)
    return erros


# ------------------------------------------------------------- terraform
def validar_terraform_nao_vazio(resultado, esperado=None):
    """Evita que os outros validadores aprovem 'no vazio'."""
    n = len(re.findall(r'^\s*resource\s+"', _terraform(resultado), re.M))
    return [] if n >= 3 else [f"terraform tem só {n} recursos"]


def validar_terraform_regras(resultado, esperado=None):
    tf = _terraform(resultado)
    erros = []
    if re.search(r'source_arn\s*=\s*"\*"', tf):
        erros.append('source_arn = "*" (permissão aberta demais)')
    runtimes = set(re.findall(r'runtime\s*=\s*"python([\d.]+)"', tf))
    for runtime in sorted(runtimes):
        versao = tuple(int(x) for x in runtime.split("."))
        if versao < (3, 10):
            erros.append(f"runtime python{runtime} descontinuado")
    return erros


def validar_consistencia(resultado, esperado):
    tf = _terraform(resultado)
    n_py = len(_arquivos_py(resultado))
    n_tf = len(re.findall(r'resource\s+"aws_lambda_function"', tf))
    n_roles = len(re.findall(r'resource\s+"aws_iam_role"', tf))
    n_perm = len(re.findall(r'resource\s+"aws_lambda_permission"', tf))
    erros = []
    if n_py != n_tf:
        erros.append(f"{n_py} arquivos .py mas {n_tf} aws_lambda_function")
    if n_tf != esperado["lambdas"]:
        erros.append(f"esperava {esperado['lambdas']} Lambdas, veio {n_tf}")
    if n_roles < n_tf:
        erros.append(f"{n_roles} roles para {n_tf} Lambdas (regra 4)")
    if n_perm < n_tf:
        erros.append(f"{n_perm} permissions para {n_tf} Lambdas (regra 4)")
    for recurso in esperado.get("recursos", []):
        if f'"{recurso}"' not in tf:
            erros.append(f"falta o recurso {recurso}")
    return erros


def validar_rotas(resultado, esperado):
    """Cada rota do API Gateway precisa de method + integration apontando para uma
    Lambda. Só roda quando o caso espera aws_api_gateway_rest_api.

    Use "rotas" em prompts.json quando nem toda Lambda tem rota
    (ex: consumidor de fila). Padrão: nº de Lambdas esperadas."""
    if "aws_api_gateway_rest_api" not in esperado.get("recursos", []):
        return []
    tf = _terraform(resultado)
    rotas_esperadas = esperado.get("rotas", esperado["lambdas"])
    n_methods = len(re.findall(r'resource\s+"aws_api_gateway_method"', tf))
    n_integ = len(re.findall(r'resource\s+"aws_api_gateway_integration"', tf))
    lambdas_ligadas = set(
        re.findall(r"uri\s*=\s*aws_lambda_function\.(\w+)\.invoke_arn", tf)
    )
    erros = []
    if n_methods < rotas_esperadas:
        erros.append(f"{n_methods} aws_api_gateway_method para {rotas_esperadas} rotas")
    if n_integ < rotas_esperadas:
        erros.append(
            f"{n_integ} aws_api_gateway_integration para {rotas_esperadas} rotas"
        )
    if len(lambdas_ligadas) < rotas_esperadas:
        erros.append(
            f"só {len(lambdas_ligadas)} Lambdas ligadas ao API Gateway "
            f"(esperava {rotas_esperadas})"
        )
    return erros


def validar_terraform_cli(resultado, esperado=None):
    """terraform init + validate numa pasta temporária. Exige Terraform instalado."""
    with tempfile.TemporaryDirectory() as pasta:
        for nome, conteudo in resultado["generated_code"]["terraform"].items():
            (Path(pasta) / Path(nome).name).write_text(conteudo)
        comandos = [
            ["terraform", "init", "-backend=false", "-input=false", "-no-color"],
            ["terraform", "validate", "-no-color"],
        ]
        for cmd in comandos:
            try:
                r = subprocess.run(
                    cmd, cwd=pasta, capture_output=True, text=True, timeout=180
                )
            except FileNotFoundError:
                return ["terraform não instalado"]
            except subprocess.TimeoutExpired:
                return [f"terraform {cmd[1]} estourou o tempo"]
            if r.returncode != 0:
                return [
                    f"terraform {cmd[1]} falhou: {(r.stderr or r.stdout).strip()[:500]}"
                ]
    return []


# -------------------------------------------------------------- registro
VALIDADORES = {
    "python": validar_python,
    "pyflakes": validar_pyflakes,
    "tf_nao_vazio": validar_terraform_nao_vazio,
    "regras_tf": validar_terraform_regras,
    "consistencia": validar_consistencia,
    "rotas": validar_rotas,
    "terraform": validar_terraform_cli,
}