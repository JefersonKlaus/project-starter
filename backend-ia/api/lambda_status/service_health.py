"""Service: runs every dependency check and aggregates the results into a HealthReport.

This is the only place that knows which checks exist and how they are wired to
the configuration; the checks themselves are plain functions of their inputs.
"""

import logging

import config
from checks import groq_api_key, groq_hello, rag_index
from models import CheckResult, HealthReport

logger = logging.getLogger(__name__)

# Name -> zero-argument callable. Config is read at call time so a warm container
# still reflects the function configuration that was active when it started.
CHECKS = {
    "rag_index": lambda: rag_index.check(config.RAG_S3_BUCKET, config.RAG_S3_KEY),
    "groq_api_key": lambda: groq_api_key.check(config.GROQ_API_KEY),
    "groq_hello": lambda: groq_hello.check(
        config.GROQ_API_KEY, config.GROQ_MODEL, config.GROQ_TIMEOUT_SECONDS
    ),
}


def run_check(name, check) -> CheckResult:
    """A crashing check is reported as an error; it must never hide the other results."""
    try:
        return check()
    except Exception as e:
        logger.exception("Health check %s crashed", name)
        return CheckResult.error(f"unexpected error: {e}")


def check_health() -> HealthReport:
    return HealthReport(
        {name: run_check(name, check) for name, check in CHECKS.items()}
    )
