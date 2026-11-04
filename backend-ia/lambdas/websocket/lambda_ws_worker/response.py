"""Output: summary returned by the handler.

Nobody waits for it (the function is invoked asynchronously), but it is what the
tests assert on and what Lambda destinations would receive if configured.
"""

COMPLETED = "completed"
FAILED = "failed"
REJECTED = "rejected"


def completed(job, sent, total):
    return {
        "status": COMPLETED,
        "request_id": job.request_id,
        "connection_id": job.connection_id,
        "messages_sent": sent,
        "messages_total": total,
    }


def failed(job, detail, notified):
    return {
        "status": FAILED,
        "request_id": job.request_id,
        "connection_id": job.connection_id,
        "detail": detail,
        "client_notified": notified,
    }


def rejected(detail):
    return {"status": REJECTED, "detail": detail}
