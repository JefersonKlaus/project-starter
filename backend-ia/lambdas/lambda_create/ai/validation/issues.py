"""Problems found in the generated project."""

from dataclasses import asdict, dataclass

ERROR = "error"  # the project would not work: the model is asked to fix it
WARNING = "warning"  # works, but breaks a rule or could not be verified


@dataclass(frozen=True)
class Issue:
    check: str  # python, terraform, layout or deployment
    severity: str
    message: str
    file: str = None  # project path, when the problem is in one file

    def __str__(self):
        where = f"{self.file}: " if self.file else ""
        return f"[{self.check}] {where}{self.message}"

    def to_dict(self):
        return {key: value for key, value in asdict(self).items() if value is not None}


def error(check, message, file=None):
    return Issue(check, ERROR, message, file)


def warning(check, message, file=None):
    return Issue(check, WARNING, message, file)


def summarize(issues):
    """Errors and warnings, without duplicates, in the order they were found."""
    unique = list(dict.fromkeys(issues))
    return (
        [i for i in unique if i.severity == ERROR],
        [i for i in unique if i.severity == WARNING],
    )
