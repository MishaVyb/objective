"""Async request manager based on `Aiohttp` or `HTTPX` with `Pydantic` schemas. """

import sys

if sys.version_info < (3, 11):
    raise RuntimeError("Python>=3.11 required. ")


from ..common import (
    ComprehensiveErrorDetails,
    ErrorRequestInfo,
    ErrorResponseContent,
    ExceptionPydanticType,
    HeadersBase,
    HTTPAuthorizationCredentials,
    HTTPClientException,
    StrOrURL,
    TokenSchema,
)
from ._base import IClientBase, RequestOptions
from ._httpx import HTTPXClientBase
