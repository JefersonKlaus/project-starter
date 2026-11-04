import pytest
from botocore.exceptions import ClientError


def test_send_posts_the_encoded_message(ws_worker, fake_connections):
    publisher = ws_worker.service_publisher.ConnectionPublisher(fake_connections)

    assert publisher.send("c1", {"type": "result", "a": "ç"}) is True
    assert fake_connections.posted == [("c1", {"type": "result", "a": "ç"})]


def test_send_returns_false_when_the_connection_is_gone(
    ws_worker, fake_connections, caplog
):
    fake_connections.gone_after = 0
    publisher = ws_worker.service_publisher.ConnectionPublisher(fake_connections)

    with caplog.at_level("WARNING"):
        assert publisher.send("c1", {"type": "result"}) is False

    assert "Connection c1 is gone" in caplog.text


def test_send_propagates_other_client_errors(ws_worker, fake_connections):
    fake_connections.exception = ClientError(
        {"Error": {"Code": "ForbiddenException", "Message": "no"}}, "PostToConnection"
    )
    publisher = ws_worker.service_publisher.ConnectionPublisher(fake_connections)

    with pytest.raises(ClientError, match="ForbiddenException"):
        publisher.send("c1", {"type": "result"})


def test_send_all_delivers_in_order_and_stops_when_gone(ws_worker, fake_connections):
    fake_connections.gone_after = 2
    publisher = ws_worker.service_publisher.ConnectionPublisher(fake_connections)
    messages = [{"index": i} for i in range(5)]

    assert publisher.send_all("c1", messages) == 2
    assert [m["index"] for _, m in fake_connections.posted] == [0, 1]


def test_get_publisher_is_cached_per_callback_url(ws_worker, fake_connections):
    get_publisher = ws_worker.service_publisher.get_publisher

    first = get_publisher("https://a.example.com/dev")

    assert first is get_publisher("https://a.example.com/dev")
    assert first is not get_publisher("https://b.example.com/dev")
    assert fake_connections.endpoints == [
        "https://a.example.com/dev",
        "https://b.example.com/dev",
    ]


def test_build_client_targets_the_callback_url(ws_worker, monkeypatch):
    captured = {}

    def _client(service, **kwargs):
        captured["service"] = service
        captured["endpoint_url"] = kwargs["endpoint_url"]
        return "client"

    monkeypatch.setattr(ws_worker.service_publisher.boto3, "client", _client)

    assert (
        ws_worker.service_publisher.build_client("https://d.example.com/dev")
        == "client"
    )
    assert captured == {
        "service": "apigatewaymanagementapi",
        "endpoint_url": "https://d.example.com/dev",
    }
