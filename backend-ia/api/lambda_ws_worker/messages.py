"""Messages pushed to the client, and how a large result is split to fit the WebSocket limit.

Every message is a JSON object with a "type" and the "request_id" of the prompt:

    {"type": "result",       "request_id": ..., "result": {...}}
    {"type": "result_chunk", "request_id": ..., "index": i, "total": n, "data": "..."}
    {"type": "error",        "request_id": ..., "detail": "..."}

API Gateway rejects WebSocket messages above 128 KB. When the encoded "result"
message is bigger than the limit, the JSON text of the result is split into
"result_chunk" messages; concatenating "data" in "index" order (0..total-1)
gives the JSON back.
"""

import json

RESULT = "result"
RESULT_CHUNK = "result_chunk"
ERROR = "error"

# Room reserved for the "index" and "total" digits when sizing chunks
COUNTER_DIGITS_MARGIN = 20


def encode(message) -> str:
    """Wire format. ensure_ascii keeps it one byte per character, so len() == bytes."""
    return json.dumps(message, ensure_ascii=True, default=str, separators=(",", ":"))


def error_message(request_id, detail):
    return {"type": ERROR, "request_id": request_id, "detail": detail}


def result_message(request_id, result):
    return {"type": RESULT, "request_id": request_id, "result": result}


def chunk_message(request_id, index, total, data):
    return {
        "type": RESULT_CHUNK,
        "request_id": request_id,
        "index": index,
        "total": total,
        "data": data,
    }


def escaped_length(text) -> int:
    """Bytes `text` occupies once embedded in a JSON string (quotes/backslashes are escaped)."""
    return len(json.dumps(text, ensure_ascii=True)) - 2


# Largest escaped size of one character of JSON text: `"` and `\` become two bytes
MAX_ESCAPED_CHAR = 2


def split_for_json(text, budget) -> list:
    """Split `text` into pieces whose escaped length never exceeds `budget`."""
    if budget < MAX_ESCAPED_CHAR:
        raise ValueError(f"budget must be at least {MAX_ESCAPED_CHAR} bytes")
    pieces = []
    start = 0
    while start < len(text):
        end = min(len(text), start + budget)
        # Every character costs at least one byte, so trimming the excess converges;
        # a piece is never empty because one character always fits (budget >= 2).
        while (excess := escaped_length(text[start:end]) - budget) > 0:
            end = max(start + 1, end - excess)
        pieces.append(text[start:end])
        start = end
    return pieces


def result_messages(request_id, result, max_bytes) -> list:
    """One "result" message when it fits in max_bytes, otherwise "result_chunk" messages."""
    whole = result_message(request_id, result)
    if len(encode(whole)) <= max_bytes:
        return [whole]

    overhead = len(encode(chunk_message(request_id, 0, 0, ""))) + COUNTER_DIGITS_MARGIN
    budget = max_bytes - overhead
    if budget < 1:
        raise ValueError(f"max_bytes={max_bytes} leaves no room for chunk data")

    text = json.dumps(result, ensure_ascii=True, default=str, separators=(",", ":"))
    pieces = split_for_json(text, budget)
    return [
        chunk_message(request_id, index, len(pieces), piece)
        for index, piece in enumerate(pieces)
    ]
