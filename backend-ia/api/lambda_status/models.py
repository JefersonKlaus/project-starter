"""Result models: one CheckResult per dependency, aggregated into a HealthReport."""

from dataclasses import dataclass

OK = "ok"
ERROR = "error"

HEALTHY_MESSAGE = "Service is up and running"
UNHEALTHY_MESSAGE = "One or more dependencies are unavailable"


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single dependency check."""

    status: str
    detail: str

    @classmethod
    def ok(cls, detail):
        return cls(OK, detail)

    @classmethod
    def error(cls, detail):
        return cls(ERROR, detail)

    @property
    def passed(self):
        return self.status == OK

    def to_dict(self):
        return {"status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class HealthReport:
    """All check results, keyed by check name, in the order they ran."""

    checks: dict

    @property
    def healthy(self):
        return all(result.passed for result in self.checks.values())

    @property
    def failed(self):
        return [name for name, result in self.checks.items() if not result.passed]

    def to_dict(self):
        return {
            "status": OK if self.healthy else ERROR,
            "message": HEALTHY_MESSAGE if self.healthy else UNHEALTHY_MESSAGE,
            "checks": {name: result.to_dict() for name, result in self.checks.items()},
        }
