import json

from json_repair import repair_json


def escape_json_control_chars(texto: str) -> str:
    """Escape literal line breaks inserted into strings by the model."""
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
    """Decode JSON and apply automatic repairs if parsing fails."""
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
                    "The model returned invalid or incomplete JSON "
                    f"(original: {erro}; after repairs: {erro_reparacao})."
                ) from erro_final
