import json
from json_repair import repair_json


def escape_json_control_chars(texto: str) -> str:
    """Escapa quebras de linha literais inseridas em strings pelo modelo."""
    resultado = []
    dentro_string = False
    escapado = False
    escapes_controle = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}

    for caractere in texto:
        if dentro_string:
            if escapado:
                escapado = False
            elif caractere == "\\":
                escapado = True
            elif caractere == '"':
                dentro_string = False
            elif caractere in escapes_controle:
                caractere = escapes_controle[caractere]
        elif caractere == '"':
            dentro_string = True
        resultado.append(caractere)

    return "".join(resultado)


def decodificar_resposta_modelo(resposta_util: str):
    """Tenta decodificar o JSON e aplica reparos automáticos em caso de falha."""
    try:
        return json.loads(resposta_util)
    except json.JSONDecodeError as erro:
        resposta_reparada = escape_json_control_chars(resposta_util)
        try:
            return json.loads(resposta_reparada)
        except json.JSONDecodeError as erro_reparacao:
            try:
                return json.loads(repair_json(resposta_reparada))
            except (TypeError, ValueError, json.JSONDecodeError) as erro_final:
                raise ValueError(
                    "O modelo retornou JSON inválido ou incompleto "
                    f"(original: {erro}; após reparos: {erro_reparacao})."
                ) from erro_final
