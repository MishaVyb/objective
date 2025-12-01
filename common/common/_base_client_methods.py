import warnings
from typing import Dict, Optional, TypeVar, Union

from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, SecretStr, field_serializer
from pydantic_core.core_schema import FieldSerializationInfo
from typing_extensions import TypeAlias
from yarl import URL

StrOrURL = Union[str, URL]
TokenSchema: TypeAlias = HTTPAuthorizationCredentials
_TQueryPrimitive = Union[int, bool, str, float]
QueryParams = Union[
    Dict[str, Union[_TQueryPrimitive, list[_TQueryPrimitive]]],
    BaseModel,
]
ResponseSchema = TypeVar("ResponseSchema", bound=BaseModel)


def _header_alias_gen(string: str) -> str:
    return "-".join(word.capitalize() for word in string.split("_"))


# TODO case insensitive implementation required
class HeadersBase(BaseModel):
    """Commonly used Headers."""

    authorization: Optional[Union[SecretStr, TokenSchema]] = None
    content_type: Optional[str] = None

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        alias_generator=_header_alias_gen,
        extra="forbid",
    )

    @field_serializer("authorization")
    def _authorization_serializer(
        self,
        v: Union[SecretStr, TokenSchema, None],
        info: FieldSerializationInfo,
    ) -> str:
        if isinstance(v, TokenSchema):
            return f"{v.scheme} {v.credentials}"
        if isinstance(v, SecretStr):
            credentials = v.get_secret_value()
            if "Bearer" not in credentials:
                return f"Bearer {credentials}"
            return credentials

        return v


class HTTPClientBaseMethodsMixin:

    _base_url: Optional[str] = None
    _api_prefix: Optional[StrOrURL] = None
    _common_request_kwargs: Optional[dict] = dict(
        allow_redirects=False,
    )

    def _use_url(self, url: StrOrURL) -> str:
        """Build request URL."""
        base = URL(self._base_url or "")

        # path part should not begin with `/`
        prefix = str(self._api_prefix or "").lstrip("/")
        url = str(url or "").lstrip("/")

        if url.endswith("/"):
            warnings.warn(f"Trailing slash in URL: {url}", UserWarning, stacklevel=2)
            result = str(base / prefix / url)

            # ensure trailing slash in url, because it could be omitted by yarl.URL
            if not result.endswith("/"):
                return result + "/"
            return result

        return str(base / prefix / url)

    def _use_url_full(self, url: StrOrURL, params: Optional[QueryParams] = None) -> URL:
        """Build full URL for verbose log messages."""
        return URL(url) % (params or {})

    def _use_headers(self, headers: Union[BaseModel, dict]) -> dict:
        """Build request Headers."""
        if isinstance(headers, BaseModel):
            headers = headers.model_dump(exclude_unset=True, by_alias=True)

        return headers

    def _use_params(self, params: Optional[QueryParams] = None) -> dict:
        """Build request Params."""
        if isinstance(params, BaseModel):
            return params.model_dump(exclude_unset=True, by_alias=True, mode="json")
        return params

    def _use_json(self, payload: Optional[BaseModel] = None) -> Optional[str]:
        """Build request Body."""
        if not payload:
            return None

        return payload.model_dump_json(exclude_unset=True, by_alias=True)

    def _use_request_kwargs(self) -> dict:
        """Build common request kwargs"""
        return self._common_request_kwargs
