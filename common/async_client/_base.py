import asyncio
import http
import logging
import time
from enum import StrEnum
from http import HTTPMethod
from typing import (
    Generic,
    NotRequired,
    Protocol,
    Type,
    TypedDict,
    TypeVar,
    Unpack,
    overload,
)

from pydantic import BaseModel, TypeAdapter
from yarl import URL

from common.common import (
    HeadersBase,
    HTTPClientBaseMethodsMixin,
    HTTPClientException,
    StrOrURL,
    get_error_details,
)

_T = TypeVar("_T")
_TQueryPrimitive = int | bool | str | float | StrEnum | None
_TParamsPrimetime = dict[str, _TQueryPrimitive | list[_TQueryPrimitive | StrEnum]]
_TParams = _TParamsPrimetime | BaseModel
_TSchema = TypeVar("_TSchema", bound=BaseModel)
_HTTPSession = TypeVar("_HTTPSession")
_TYPE_ADAPTERS = {}  # allows response_schema be Union/List/etc


class IClientBase(Protocol):
    """
    Interface to support typing for any generic HTTP client class, that could be used
    either with `aiohttp` or `httpx` session.
    """

    @overload
    async def _call_service(
        self,
        method: HTTPMethod,
        url: StrOrURL,
        *,
        params: _TParams | None = None,
        payload: BaseModel | None = None,
        response_schema: Type[_TSchema],
    ) -> _TSchema:
        """Normalize request options. Parse response."""
        ...

    @overload
    async def _call_service(
        self,
        method: HTTPMethod,
        url: StrOrURL,
        *,
        params: _TParams | None = None,
        payload: BaseModel | None = None,
        response_schema: None = None,
    ) -> None:
        """Normalize request options. No content response."""
        ...

    async def _call_service(
        self,
        method: HTTPMethod,
        url: StrOrURL,
        *,
        params: _TParams | None = None,
        payload: BaseModel | None = None,
        response_schema: Type[_TSchema] | None = None,
    ) -> _TSchema | None:
        ...


class RequestOptions(TypedDict):
    allow_redirects: NotRequired[bool]


class HTTPContentError(ValueError):
    pass


class HTTPClientBase(IClientBase, HTTPClientBaseMethodsMixin, Generic[_HTTPSession]):
    """Async request manager with Pydantic supports."""

    _REQUEST_MESSAGE = "Starting new HTTP request. {method} {url}"
    _REQUEST_MESSAGE_END = "End HTTP request. {method} {url} [{time:.3f} sec]"
    _ERROR_MESSAGE = "HTTP Request failed: bad status code received. {method} {url} {status} {reason}"
    _TIMEOUT_ERROR_MESSAGE = "HTTP Request failed: takes too long. {method} {url}"
    _REDIRECT_WARN_MESSAGE = "Redirect status received: {method} {url} {resp}"
    _NO_CONTENT_ERROR_MESSAGE = (
        "HTTP Request failed: "
        "response with content was expected, but got no content. {method} {url} {resp}"
    )

    # class level configuration:
    _truncate_msg_len: int = 1_000
    _exc: Type[HTTPClientException] = HTTPClientException
    """Common options for each request, like headers, cookies, etc. """

    def __init__(
        self,
        session: _HTTPSession,
        *,
        base_url: StrOrURL | None = None,
        headers: HeadersBase | dict | None = None,
        logger: logging.Logger = logging.getLogger(__name__),
        **common_request_kwargs: Unpack[RequestOptions],
    ):
        """
        :param session: **opened** http session.
            NOTE: `HTTPClientBase` is implemented to describe an API interface to make
            a requests to any service, but it does not handle async HTTP sessions lifecycle.
            As it depends on usage case, you should open/close session properly by your own.
        :param base_url: absolute service url. Not compatible with `session.base_url`
        :param common_request_kwargs: common request preferences for each request.
            For options reference see `aiohttp.ClientSession._request`.
            Merged with class level `common_request_kwargs`.
        """
        self._session = session
        self._base_url = base_url
        self._headers = headers or {}
        self._common_request_kwargs = (
            self._common_request_kwargs or {}
        ) | common_request_kwargs
        self._logger = logger

    @overload
    async def _call_service(
        self,
        method: HTTPMethod,
        url: StrOrURL,
        *,
        params: _TParams | None = None,
        payload: BaseModel | None = None,
        response_schema: Type[_TSchema],
    ) -> _TSchema:
        """Normalize request options. Parse response."""
        ...

    @overload
    async def _call_service(
        self,
        method: HTTPMethod,
        url: StrOrURL,
        *,
        params: _TParams | None = None,
        payload: BaseModel | None = None,
        response_schema: Type[_T],
    ) -> _T:
        """Normalize request options. Parse response."""
        ...

    @overload
    async def _call_service(
        self,
        method: HTTPMethod,
        url: StrOrURL,
        *,
        params: _TParams | None = None,
        payload: BaseModel | None = None,
        response_schema: TypeAdapter[_T],
    ) -> _T:
        """Normalize request options. Parse response."""
        ...

    @overload
    async def _call_service(
        self,
        method: HTTPMethod,
        url: StrOrURL,
        *,
        params: _TParams | None = None,
        payload: BaseModel | None = None,
        response_schema: None = None,
    ) -> None:
        """Normalize request options. No content response."""
        ...

    async def _call_service(
        self,
        method: HTTPMethod,
        url: StrOrURL,
        *,
        params: _TParams | None = None,
        payload: BaseModel | None = None,
        response_schema: Type[_TSchema] | TypeAdapter[_T] | Type[_T] | None = None,
    ) -> _TSchema | _T | None:
        response_with_content = True if response_schema else False

        url = self._use_url(url)
        json = self._use_json(payload)
        params = self._use_params(params)
        headers = self._use_headers(self._headers)
        common_request_kwargs = self._use_request_kwargs()

        url_full = self._use_url_full(url, params)  # for log messages only
        self._logger.info(self._REQUEST_MESSAGE.format(method=method, url=url_full))

        try:
            start_time = time.time()
            content = await self._process_request(
                method,
                url,
                response_with_content=response_with_content,
                params=params,
                headers=headers,
                data=json,
                **common_request_kwargs,
            )
        except asyncio.TimeoutError:
            message = self._TIMEOUT_ERROR_MESSAGE.format(
                method=method,
                url=self._use_url_full(url, params),
            )
            exc = self._exc(http.HTTPStatus.GATEWAY_TIMEOUT.value, message)
            exc.add_note(message)
            raise exc
        finally:
            msg = self._REQUEST_MESSAGE_END.format(
                method=method,
                url=url_full,
                time=time.time() - start_time,
            )
            self._logger.debug(msg)

        if response_with_content:
            if isinstance(response_schema, TypeAdapter):
                return response_schema.validate_json(content)
            if not (adapter := _TYPE_ADAPTERS.get(response_schema)):
                # avoid recreating pydantic core schema every call, cache adapters
                adapter = _TYPE_ADAPTERS[response_schema] = TypeAdapter(response_schema)
            return adapter.validate_json(content)
        return None

    async def _process_request(
        self,
        method: HTTPMethod,
        url: StrOrURL,
        *,
        response_with_content: bool,
        params: _TParams | None = None,
        headers: dict | None = None,
        data: str | bytes | None = None,
        **other_kwargs,
    ) -> bytes | None:
        """
        Implements raw request call and return **not parsed** content.

        :param response_with_content: internal flag to read response content or not
        """

        raise NotImplementedError

    def _raise_for_status(
        self,
        details: BaseModel | str,
        *,
        method: str,
        url: URL | str,
        status: int,
        reason: str,
    ):
        """Raise called service HTTP error."""

        details_message = (
            details.model_dump_json(indent=4)
            if isinstance(details, BaseModel)
            else str(details)
        )
        log_message = self._ERROR_MESSAGE.format(
            method=method,
            url=url,
            status=status,
            reason=reason,
        )
        self._logger.warning(log_message)

        exc = self._exc(status_code=status, detail=details)
        exc.add_note(log_message[: self._truncate_msg_len])
        exc.add_note(details_message[: self._truncate_msg_len])

        raise exc

    def _get_error_details(self, data: dict | str):
        return get_error_details(data)
