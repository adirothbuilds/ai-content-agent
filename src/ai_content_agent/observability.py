import contextvars
import json
import logging
import logging.config
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import Request, Response

from ai_content_agent.settings import Settings


REQUEST_ID_HEADER = "X-Request-ID"
TRACE_ID_HEADER = "X-Trace-ID"
RUN_ID_HEADER = "X-Run-ID"

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)
trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id",
    default=None,
)
run_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "run_id",
    default=None,
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_var.get()),
            "trace_id": getattr(record, "trace_id", trace_id_var.get()),
            "run_id": getattr(record, "run_id", run_id_var.get()),
        }

        if hasattr(record, "event"):
            payload["event"] = record.event
        if hasattr(record, "path"):
            payload["path"] = record.path
        if hasattr(record, "method"):
            payload["method"] = record.method
        if hasattr(record, "status_code"):
            payload["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            payload["duration_ms"] = record.duration_ms

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, sort_keys=True)


def configure_logging(settings: Settings) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                }
            },
            "root": {
                "handlers": ["default"],
                "level": settings.log_level.upper(),
            },
        }
    )


def _request_id_from_headers(request: Request) -> str:
    return request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())


def _new_trace_id() -> str:
    return uuid.uuid4().hex


def get_request_context() -> dict[str, str | None]:
    return {
        "request_id": request_id_var.get(),
        "trace_id": trace_id_var.get(),
        "run_id": run_id_var.get(),
    }


async def observability_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = _request_id_from_headers(request)
    trace_id = _new_trace_id()
    run_id = _new_trace_id()

    request_id_token = request_id_var.set(request_id)
    trace_id_token = trace_id_var.set(trace_id)
    run_id_token = run_id_var.set(run_id)

    logger = logging.getLogger("ai_content_agent.http")
    started_at = time.perf_counter()

    logger.info(
        "Request started",
        extra={
            "event": "request.started",
            "method": request.method,
            "path": request.url.path,
            "request_id": request_id,
            "trace_id": trace_id,
            "run_id": run_id,
        },
    )

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception(
            "Request failed",
            extra={
                "event": "request.failed",
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "duration_ms": duration_ms,
                "request_id": request_id,
                "trace_id": trace_id,
                "run_id": run_id,
            },
        )
        raise
    else:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[TRACE_ID_HEADER] = trace_id
        response.headers[RUN_ID_HEADER] = run_id
        logger.info(
            "Request completed",
            extra={
                "event": "request.completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "request_id": request_id,
                "trace_id": trace_id,
                "run_id": run_id,
            },
        )
        return response
    finally:
        run_id_var.reset(run_id_token)
        trace_id_var.reset(trace_id_token)
        request_id_var.reset(request_id_token)
