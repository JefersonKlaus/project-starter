import json
import random
import string

import pytest


def test_encode_is_compact_ascii(ws_worker):
    encoded = ws_worker.messages.encode({"a": "çã", "b": [1, 2]})
    assert encoded == '{"a":"\\u00e7\\u00e3","b":[1,2]}'
    assert len(encoded) == len(encoded.encode("utf-8"))


def test_error_and_result_messages(ws_worker):
    assert ws_worker.messages.error_message("r1", "boom") == {
        "type": "error",
        "request_id": "r1",
        "detail": "boom",
    }
    assert ws_worker.messages.result_message("r1", {"a": 1}) == {
        "type": "result",
        "request_id": "r1",
        "result": {"a": 1},
    }


def test_result_messages_returns_one_message_when_it_fits(ws_worker):
    messages = ws_worker.messages.result_messages("r1", {"a": 1}, 1000)
    assert messages == [{"type": "result", "request_id": "r1", "result": {"a": 1}}]


def test_result_messages_chunks_large_results(ws_worker):
    result = {"code": "x" * 500}

    messages = ws_worker.messages.result_messages("r1", result, 200)

    assert len(messages) > 1
    assert [m["index"] for m in messages] == list(range(len(messages)))
    assert {m["total"] for m in messages} == {len(messages)}
    assert {m["type"] for m in messages} == {"result_chunk"}
    assert {m["request_id"] for m in messages} == {"r1"}
    assert all(len(ws_worker.messages.encode(m)) <= 200 for m in messages)
    assert json.loads("".join(m["data"] for m in messages)) == result


def test_result_messages_respects_the_limit_with_escaped_text(ws_worker):
    """Quotes, backslashes and non-ASCII grow when embedded in a JSON string."""
    random.seed(7)
    alphabet = string.ascii_letters + '"\\\n' + "çãé€"
    result = {"code": "".join(random.choice(alphabet) for _ in range(20_000))}

    for max_bytes in (128, 333, 4096):
        messages = ws_worker.messages.result_messages("r1", result, max_bytes)
        sizes = [len(ws_worker.messages.encode(m).encode("utf-8")) for m in messages]
        assert max(sizes) <= max_bytes
        assert json.loads("".join(m["data"] for m in messages)) == result


def test_result_messages_rejects_a_limit_with_no_room_for_data(ws_worker):
    with pytest.raises(ValueError, match="no room for chunk data"):
        ws_worker.messages.result_messages("r1", {"code": "x" * 100}, 40)


def test_split_for_json_keeps_pieces_under_budget(ws_worker):
    text = 'a"b\\c' * 10  # every quote/backslash costs two bytes once escaped

    pieces = ws_worker.messages.split_for_json(text, 7)

    assert "".join(pieces) == text
    assert all(ws_worker.messages.escaped_length(p) <= 7 for p in pieces)
    assert all(pieces)


def test_split_for_json_handles_empty_text_and_tiny_budgets(ws_worker):
    assert ws_worker.messages.split_for_json("", 10) == []
    assert ws_worker.messages.split_for_json('""', 2) == ['"', '"']
    with pytest.raises(ValueError, match="at least 2 bytes"):
        ws_worker.messages.split_for_json("abc", 1)
