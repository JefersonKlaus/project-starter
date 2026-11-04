def _job(ws_worker):
    return ws_worker.models.Job(
        connection_id="c1", callback_url="https://d/dev", request_id="r1", prompt="x"
    )


def test_completed(ws_worker):
    assert ws_worker.response.completed(_job(ws_worker), 2, 3) == {
        "status": "completed",
        "request_id": "r1",
        "connection_id": "c1",
        "messages_sent": 2,
        "messages_total": 3,
    }


def test_failed(ws_worker):
    assert ws_worker.response.failed(_job(ws_worker), "boom", False) == {
        "status": "failed",
        "request_id": "r1",
        "connection_id": "c1",
        "detail": "boom",
        "client_notified": False,
    }


def test_rejected(ws_worker):
    assert ws_worker.response.rejected("bad job") == {
        "status": "rejected",
        "detail": "bad job",
    }
