import pytest


@pytest.fixture
def models(status):
    return status.models


def test_check_result_ok(models):
    result = models.CheckResult.ok("fine")

    assert result.passed
    assert result.to_dict() == {"status": "ok", "detail": "fine"}


def test_check_result_error(models):
    result = models.CheckResult.error("nope")

    assert not result.passed
    assert result.to_dict() == {"status": "error", "detail": "nope"}


def test_check_result_is_immutable(models):
    with pytest.raises(AttributeError):
        models.CheckResult.ok("fine").status = "error"


def test_health_report_is_healthy_only_when_every_check_passed(models):
    healthy = models.HealthReport({"a": models.CheckResult.ok("x")})
    unhealthy = models.HealthReport(
        {"a": models.CheckResult.ok("x"), "b": models.CheckResult.error("y")}
    )

    assert healthy.healthy and healthy.failed == []
    assert not unhealthy.healthy and unhealthy.failed == ["b"]


def test_empty_health_report_is_healthy(models):
    assert models.HealthReport({}).healthy


def test_health_report_to_dict_keeps_check_order(models):
    report = models.HealthReport(
        {"first": models.CheckResult.ok("1"), "second": models.CheckResult.error("2")}
    )

    assert report.to_dict() == {
        "status": "error",
        "message": "One or more dependencies are unavailable",
        "checks": {
            "first": {"status": "ok", "detail": "1"},
            "second": {"status": "error", "detail": "2"},
        },
    }
    assert list(report.to_dict()["checks"]) == ["first", "second"]


def test_healthy_report_message(models):
    assert models.HealthReport({"a": models.CheckResult.ok("x")}).to_dict() == {
        "status": "ok",
        "message": "Service is up and running",
        "checks": {"a": {"status": "ok", "detail": "x"}},
    }
