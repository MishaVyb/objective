import logging
import traceback
from pprint import pformat
from typing import Any, Callable, Literal, Type

import httpx
import sentry_sdk
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from pydantic_core import PydanticUndefinedType
from starlette.exceptions import HTTPException as StarletteHTTPException

from common.async_client import (
    ComprehensiveErrorDetails,
    ErrorRequestInfo,
    ErrorResponseContent,
    HTTPClientException,
)

logger = logging.getLogger(__name__)


class ExceptionsHandlersBase:
    ERROR_DETAILS = {
        status.HTTP_500_INTERNAL_SERVER_ERROR: "Internal server error",
    }
    FORCE_NOTE_DEBUG_CODES = {
        # do not show traceback for not authenticated users
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }
    DEFAULT_ENCODER = {
        # Handle FastAPI issue: https://github.com/tiangolo/fastapi/issues/9920
        PydanticUndefinedType: lambda _: None,
    }

    def __init__(
        self,
        *,
        debug: bool,
        response_model: Type[ErrorResponseContent] = ErrorResponseContent,
        custom_encoder: dict[Any, Callable[[Any], Any]] | None = None,
        replace_uvicorn_error_log: bool = True,
        raise_server_exceptions: Literal["*"] | list[int] | bool | None = None,
        headers: httpx.Headers | dict = None,
        #
        # NOTE: it's better to use Sentry, but could be turned on, if needed:
        include_traceback: bool | None = False,
        traceback_limit: int | None = None,
    ) -> None:
        self.debug = debug
        self.response_model = response_model
        self.custom_encoder = self.DEFAULT_ENCODER | (custom_encoder or {})
        self.headers = headers

        self.raise_server_exceptions: Literal["*"] | list[int]
        if raise_server_exceptions is True:
            self.raise_server_exceptions = "*"
        else:
            self.raise_server_exceptions = raise_server_exceptions or []

        if not include_traceback and traceback_limit:
            raise ValueError

        self.include_traceback = include_traceback
        self.traceback_limit = traceback_limit
        self.replace_uvicorn_error_log = replace_uvicorn_error_log

    def get_logger(self, request: Request) -> logging.Logger:
        """Get logger attached to current request. By default return global module logger."""
        return getattr(request.state, "logger", logger)

    def setup(self, app: FastAPI):
        app.add_exception_handler(ExceptionGroup, self.exception_group_handler)
        app.add_exception_handler(StarletteHTTPException, self.http_exception_handler)
        app.add_exception_handler(
            HTTPClientException,
            self.http_client_exception_handler,
        )
        app.add_exception_handler(
            RequestValidationError,
            self.request_validation_exception_handler,
        )
        app.add_exception_handler(
            ResponseValidationError,
            self.response_validation_exception_handler,
        )
        app.add_exception_handler(Exception, self.exception_handler)

    async def exception_group_handler(self, request: Request, exc: ExceptionGroup):
        logger = self.get_logger(request)
        http_exc, other_exc = exc.split(HTTPException)
        http_exc = http_exc.exceptions if http_exc else []
        other_exc = other_exc.exceptions if other_exc else []
        if http_exc:
            exc = http_exc[0]
            if len(http_exc) > 1 or other_exc:
                logger.exception(
                    "More then one exception found in ExceptionGroup. "
                    "Respond with first HTTPException. Full exception traceback: \n",
                    exc_info=exc,
                )

            return await self.http_exception_handler(request, exc)
        return await self.exception_handler(request, exc)

    async def http_exception_handler(
        self,
        request: Request,
        exc: StarletteHTTPException,
    ):
        return await self.exception_handler(
            request,
            exc,
            status_code=exc.status_code,
            detail=exc.detail,
        )

    async def http_client_exception_handler(
        self,
        request: Request,
        exc: HTTPClientException,
    ):
        """Rebuild HTTPClientException to FastAPI based exception."""
        # It's done this way because base http client raise custom Exception and
        # should not require FastAPI as import dependency
        fastapi_exc = BaseHTTPException(exc.status_code, exc.detail, exc.headers)
        return await self.http_exception_handler(request, fastapi_exc)

    async def request_validation_exception_handler(
        self,
        request: Request,
        exc: RequestValidationError,
    ):
        exc.add_note(pformat(exc.errors()))
        return await self.exception_handler(
            request,
            exc,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=jsonable_encoder(exc.errors(), custom_encoder=self.custom_encoder),
        )

    async def response_validation_exception_handler(
        self,
        request: Request,
        exc: ResponseValidationError,
    ):
        exc.add_note(pformat(exc.errors()))
        return await self.exception_handler(
            request,
            exc,
            detail=ComprehensiveErrorDetails(
                msg=str(exc) or str(exc.__class__.__name__),
                items=jsonable_encoder(
                    exc.errors(),
                    custom_encoder=self.custom_encoder,
                ),
            ),
        )

    async def exception_handler(
        self,
        request: Request,
        exc: Exception,
        *,
        status_code: int | None = None,
        detail: ComprehensiveErrorDetails | dict | str | list | None = None,
        # log
    ):
        logger = self.get_logger(request)
        debug = self.debug
        if status_code in self.FORCE_NOTE_DEBUG_CODES:
            debug = False

        # NOTE:
        # traceback in most cases are omitted, as it listed at logs and available via Sentry/Graylog
        exc_info = (
            traceback.format_exception(exc, limit=self.traceback_limit)
            if debug and self.include_traceback
            else None
        )

        # NOTE:
        # detail/status_code might be taken from function arguments, if it was prepared
        # before at another special exception handler. Or it would be taken from
        # exception itself, if its base FastAPI HTTPException.
        # Otherwise, simple error string used as detail and default 500 status code is used.
        if not detail:
            if isinstance(exc, HTTPException):
                detail = exc.detail
            elif debug:
                detail = str(exc) or repr(exc)
            else:
                detail = self.ERROR_DETAILS.get(status_code)

        if not status_code:
            if isinstance(exc, HTTPException):
                status_code = exc.status_code
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR  # default

        # raise exc as it is on tests / debugging
        if self.raise_server_exceptions == "*":
            raise exc
        if status_code in self.raise_server_exceptions:
            raise exc

        # log internal server error traceback
        if (
            self.replace_uvicorn_error_log
            and status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR
        ):
            logger.exception(
                "Exception in ASGI application: \n",
                exc_info=exc,
            )

            # HACK
            # replace uvicorn.error default logging
            # (uvicorn uses this logger in deferent places and it cannot be disabled
            # completely, therefore patch and mute only one next error logging call,
            # which is duplicate for our custom log above)
            def muted_error_call(*args, **kwargs):
                uvicorn_logger.error = uvicorn_logger_error_call  # revert original impl

            uvicorn_logger = logging.getLogger("uvicorn.error")
            uvicorn_logger_error_call = uvicorn_logger.error
            uvicorn_logger.error = muted_error_call

        content = self.response_model(
            detail=detail,
            exception=exc_info,
            request=self.get_request_info(request),
        )
        return await self.finalize_response(content, status_code, debug=debug)

    def get_request_info(self, request: Request):
        try:
            request_id = request.state.request_id
        except AttributeError:
            request_id = None

        return ErrorRequestInfo(
            id=request_id,
            method=request.method,
            uri=str(request.url.include_query_params(**request.query_params)),
            headers=None,  # Omit this. Too much information.
            data=None,  # Omit this. Too much information.
        )

    async def finalize_response(
        self,
        content: ErrorResponseContent,
        status_code: int,
        debug: bool,
    ):
        return JSONResponse(
            jsonable_encoder(
                content,
                by_alias=True,
                exclude_none=True,
                custom_encoder=self.custom_encoder,
            ),
            status_code,
            headers=dict(self.headers) if self.headers else None,
        )


class SentryExceptionsHandlers(ExceptionsHandlersBase):
    """Integrates error response with Tracing context."""

    def __init__(
        self,
        *,
        debug: bool,
        dashboard_url: str,
        response_model: type[ErrorResponseContent] = ErrorResponseContent,
        custom_encoder: dict[Any, Callable[[Any], Any]] | None = None,
        headers: httpx.Headers | dict = None,
        replace_uvicorn_error_log: bool = True,
        raise_server_exceptions: Literal["*"] | list[int] | bool | None = None,
        include_traceback: bool | None = False,
        traceback_limit: int | None = None,
    ) -> None:
        self.dashboard_url = dashboard_url
        super().__init__(
            debug=debug,
            response_model=response_model,
            custom_encoder=custom_encoder,
            replace_uvicorn_error_log=replace_uvicorn_error_log,
            raise_server_exceptions=raise_server_exceptions,
            include_traceback=include_traceback,
            traceback_limit=traceback_limit,
            headers=headers,
        )

    async def finalize_response(
        self,
        content: ErrorResponseContent,
        status_code: int,
        debug: bool,
    ):
        span = sentry_sdk.get_current_span()
        if span and debug:
            content.trace_id = span.trace_id
            content.trace_url = (
                f"{self.dashboard_url}/performance/trace/{span.trace_id}"
            )
            if content.request:
                content.request.id = content.request.id or span.trace_id

        sentry_sdk.set_context(
            # By default, Sentry propagates only Response status, but not Response body.
            # So, add error response details for context:
            "Response Extra",
            {
                "status_code": status_code,
                "detail": jsonable_encoder(
                    content.detail,
                    by_alias=True,
                    exclude_none=True,
                    custom_encoder=self.custom_encoder,
                ),
            },
        )
        return await super().finalize_response(content, status_code, debug=debug)


class BaseHTTPException(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: ComprehensiveErrorDetails | Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        if isinstance(detail, ComprehensiveErrorDetails):
            detail = detail.model_dump(exclude_unset=True)
            detail = {k: v for k, v in detail.items() if v}  # exclude empty fields

        super().__init__(status_code, detail, headers)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.status_code=} {self.detail=})"

    def __str__(self) -> str:
        return self.__repr__()


class BadRequest(BaseHTTPException):
    def __init__(self, msg: str | ComprehensiveErrorDetails):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


class TokenError(BaseHTTPException):
    def __init__(self, msg: str | ComprehensiveErrorDetails):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token error: {msg}" if isinstance(msg, str) else msg,
            headers={"WWW-Authenticate": 'Bearer realm="token"'},
        )


class NotEnoughRights(BaseHTTPException):
    def __init__(self, detail: str | ComprehensiveErrorDetails | Any):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotFoundError(BaseHTTPException):
    def __init__(self, detail: str | ComprehensiveErrorDetails | Any):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictError(BaseHTTPException):
    def __init__(self, detail: str | ComprehensiveErrorDetails | Any):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class ValidationError(BaseHTTPException):
    def __init__(self, detail: str | ComprehensiveErrorDetails | Any):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )
