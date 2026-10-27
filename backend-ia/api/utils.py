import json

from json_repair import repair_json


def escape_json_control_chars(text: str) -> str:
    """Escape literal line breaks inserted into strings by the model."""
    result = []
    inside_string = False
    escaped = False
    control_escapes = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}

    for character in text:
        if inside_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                inside_string = False
            elif character in control_escapes:
                character = control_escapes[character]
        elif character == '"':
            inside_string = True
        result.append(character)

    return "".join(result)


def decode_model_response(raw_response: str):
    """Decode JSON and apply automatic repairs if parsing fails."""
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError as error:
        repaired_response = escape_json_control_chars(raw_response)
        try:
            return json.loads(repaired_response)
        except json.JSONDecodeError as repair_error:
            try:
                return json.loads(repair_json(repaired_response))
            except (TypeError, ValueError, json.JSONDecodeError) as final_error:
                raise ValueError(
                    "The model returned invalid or incomplete JSON "
                    f"(original: {error}; after repairs: {repair_error})."
                ) from final_error
