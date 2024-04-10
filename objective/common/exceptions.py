# type: ignore

import logging
import traceback
from typing import Annotated, Any, Type

import httpx
import sentry_sdk
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pydantic_core import PydanticUndefinedType, core_schema
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class _ExceptionPydanticSchema:
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        def validate_from_str(value: str):
            raise ValueError("Validation from string to Exception is not supported. ")

        def serialize_to_str(value: BaseException | str):
            if isinstance(value, BaseException):
                if not str(value):
                    return value.__class__.__name__
                return f"{value.__class__.__name__}: {value}"

            if isinstance(value, str):
                return value

            return str(value)

        from_str_schema = core_schema.chain_schema(
            [
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(validate_from_str),
            ],
        )

        return core_schema.json_or_python_schema(
            json_schema=from_str_schema,
            python_schema=core_schema.union_schema(
                [
                    # check if it's an instance first before doing any further work
                    core_schema.is_instance_schema(BaseException),
                    from_str_schema,
                ],
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize_to_str,
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, _core_schema, handler):
        return handler(core_schema.str_schema())


ExceptionPydanticType = Annotated[BaseException, _ExceptionPydanticSchema]
"""Exception type with Pydantic support. Serializable. """


class ErrorDetails(BaseModel):
    msg: str | Any
    """verbose error message. """
    items: list | dict | Any | None = None
    """Items causing this error. """
    original: str | dict | ExceptionPydanticType | None = None
    """Any error original reason or extra information. """


class ErrorResponseContent(BaseModel):
    detail: ErrorDetails | str | dict | Any
    trace_id: str | None = None
    trace_url: str | None = None
    exception: list[str] | None = None  # `exc_info`


class ExceptionsHandlersBase:
    ERROR_DETAILS = {
        status.HTTP_500_INTERNAL_SERVER_ERROR: "Internal server error",
    }
    FORCE_NOTE_DEBUG_CODES = {
        # do not show traceback for not authenticated users
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    }

    def __init__(
        self,
        *,
        debug: bool,
        response_model: Type[ErrorResponseContent] = ErrorResponseContent,
        traceback_limit: int | None = None,
        headers: httpx.Headers | dict = None,
    ) -> None:
        self.debug = debug
        self.response_model = response_model
        self.traceback_limit = traceback_limit
        self.headers = headers

    def setup(self, app: FastAPI):
        app.add_exception_handler(ExceptionGroup, self.exception_group_handler)
        app.add_exception_handler(StarletteHTTPException, self.http_exception_handler)
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

        # Sentry and Uvicorn do not perform logging for ExceptionGroup errors, so do it here:
        logger.exception(
            "Exception in ASGI application: \n",
            exc_info=exc,
        )
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

    async def request_validation_exception_handler(
        self,
        request: Request,
        exc: RequestValidationError,
    ):
        return await self.exception_handler(
            request,
            exc,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=jsonable_encoder(
                exc.errors(),
                # Handle FastAPI issue: https://github.com/tiangolo/fastapi/issues/9920
                custom_encoder={
                    PydanticUndefinedType: lambda _: None,
                },
            ),
        )

    async def response_validation_exception_handler(
        self,
        request: Request,
        exc: ResponseValidationError,
    ):
        return await self.exception_handler(
            request,
            exc,
            detail=ErrorDetails(
                msg=str(exc) or str(exc.__class__.__name__),
                items=exc.errors(),
            ),
        )

    async def exception_handler(
        self,
        request: Request,
        exc: Exception,
        *,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: ErrorDetails | str | list | None = None,
        # log
    ):
        debug = self.debug
        if status_code in self.FORCE_NOTE_DEBUG_CODES:
            debug = False

        exc_info = (
            traceback.format_exception(exc, limit=self.traceback_limit)
            if debug
            else None
        )
        if not detail and debug:
            detail = str(exc)
        elif not detail:
            detail = self.ERROR_DETAILS.get(status_code)

        content = self.response_model(detail=detail, exception=exc_info)
        return await self.finalize_response(content, status_code, debug=debug)

    async def finalize_response(
        self,
        content: ErrorResponseContent,
        status_code: int,
        debug: bool,
    ):
        return JSONResponse(
            jsonable_encoder(content, by_alias=True, exclude_none=True),
            status_code,
            headers=self.headers,
        )


class SentryExceptionsHandlers(ExceptionsHandlersBase):
    """Integrates error response with Tracing context."""

    # Only 3 last calls is more than enough, as full tb available at Sentry:
    _DEFAULT_TB_LIMIT = -3

    def __init__(
        self,
        *,
        debug: bool,
        dashboard_url: str,
        response_model: type[ErrorResponseContent] = ErrorResponseContent,
        traceback_limit: int | None = _DEFAULT_TB_LIMIT,
        headers: httpx.Headers | dict = None,
    ) -> None:
        self.dashboard_url = dashboard_url
        super().__init__(
            debug=debug,
            response_model=response_model,
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
                ),
            },
        )
        return await super().finalize_response(content, status_code, debug=debug)


class BaseHTTPException(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: ErrorDetails | Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        if isinstance(detail, ErrorDetails):
            detail = detail.model_dump(exclude_unset=True)
            detail = {k: v for k, v in detail.items() if v}  # exclude empty fields

        super().__init__(status_code, detail, headers)


class BadRequest(BaseHTTPException):
    def __init__(self, msg: str | ErrorDetails):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


class TokenError(BaseHTTPException):
    def __init__(self, msg: str | ErrorDetails):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token error: {msg}" if isinstance(msg, str) else msg,
            headers={"WWW-Authenticate": 'Bearer realm="token"'},
        )


class NotEnoughRights(BaseHTTPException):
    def __init__(self, detail: str | ErrorDetails):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotFoundError(BaseHTTPException):
    def __init__(self, detail: str | ErrorDetails):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictError(BaseHTTPException):
    def __init__(self, detail: str | ErrorDetails):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class ValidationError(BaseHTTPException):
    def __init__(self, detail: str | ErrorDetails):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )
