import logging
import time
import uuid
from pprint import pformat
from typing import Annotated, Awaitable, Callable

import fastapi
from fastapi import HTTPException, Request
from fastapi.params import Depends
from starlette.middleware.base import BaseHTTPMiddleware, DispatchFunction
from starlette.responses import Response
from starlette.types import ASGIApp

from common.common import HTTPClientException
from common.logging.logging import RequestLoggerAdapter, RequestLoggerContext

logger = logging.getLogger(__name__)


# implement this as middleware (not a dependency) in case logger is required at
# any other middleware, which always called before any deps
class LoggerMiddleware(BaseHTTPMiddleware):
    """Populate request state with corelation logger."""

    def __init__(
        self,
        app: ASGIApp,
        dispatch: DispatchFunction | None = None,
        *,
        name: str = __name__,
    ) -> None:
        self.name = name
        super().__init__(app, dispatch)

    def build_request_id(self, request: Request) -> str:
        return uuid.uuid4().hex

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            req_id = request.state.request_id
        except AttributeError:
            req_id = request.state.request_id = self.build_request_id(request)

        request.state.logger = RequestLoggerAdapter(
            logger,
            RequestLoggerContext(request_id=req_id),
        )
        return await call_next(request)


def get_logger(request: Request):
    try:
        return request.state.logger
    except AttributeError:
        raise RuntimeError(f"Make sure {LoggerMiddleware} has applied. ")


LoggerDepends = Annotated[logging.Logger, Depends(get_logger)]
"""Dependency annotation to get logger attached to current request. """


class JournalRecordMiddleware(BaseHTTPMiddleware):
    """
    Log request information.
    Also could be used ad replacement for default `uvicorn.access` log.
    """

    # Commonly, Sentry is used as full tracing aggregation service.
    # This is complement solution in case of Sentry downtime or ony other tracing issues.
    # All request information might be found by request_id both at Sentry and Greylog.

    def __init__(
        self,
        app: ASGIApp,
        dispatch: DispatchFunction | None = None,
        *,
        access_log: bool = False,
        max_body_len: int = 1024,
    ) -> None:
        if fastapi.__version__ < "0.108.0":
            # Issue: https://github.com/tiangolo/fastapi/discussions/8187
            raise RuntimeError("FastAPI>=0.108.0 is required. ")

        self.access_log = access_log
        self.max_body_len = max_body_len
        super().__init__(app, dispatch)

    def get_logger(self, request: Request) -> logging.Logger:
        """Get logger attached to current request. By default return global module logger."""
        return getattr(request.state, "logger", logger)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        logger = self.get_logger(request)

        if logger.level <= logging.DEBUG:
            try:
                decoded = (await request.body()).decode()
            except UnicodeDecodeError:
                decoded = None
            else:
                if len(decoded) > self.max_body_len:
                    decoded = decoded[: self.max_body_len] + " [truncated]..."

            journal_data = dict(
                client=request.client,
                method=request.method,
                url=request.url,
                query_params=request.query_params,
                body=decoded,
            )
            logger.debug(
                "Journal: %s",
                pformat(journal_data, sort_dicts=False, width=150),
            )

        try:
            start_time = time.time()
            response = await call_next(request)
        except (HTTPException, HTTPClientException) as e:
            response_result = f"{e.status_code} {e.__class__.__name__}"
            raise e
        except Exception as e:
            # in case of any exception, final response status_code is unknown, because
            # error response will be prepared later at internal FastAPI exception handlers
            response_result = e.__class__.__name__
            raise e
        else:
            response_result = response.status_code

        finally:
            # replacement for starlette `access_log` with extra information
            if self.access_log:
                logger.info(
                    '%s - "%s %s HTTP/%s" %s [%3f]',
                    (
                        f"{request.client.host}:{request.client.port}"
                        if request.client
                        else ""
                    ),
                    request.method,
                    request.url,
                    request.scope.get("http_version", ""),
                    response_result,
                    time.time() - start_time,
                )

        return response
