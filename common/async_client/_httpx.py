from copy import copy
from http import HTTPMethod
from json import JSONDecodeError

from httpx import AsyncClient, Response
from pydantic import BaseModel

from ._base import HTTPClientBase, HTTPContentError, StrOrURL, _TParams
from ._httpx_types import HeaderTypes, QueryParamTypes, RequestData, RequestFiles


class HTTPXClientBase(HTTPClientBase[AsyncClient]):
    def _use_params(self, params: BaseModel | _TParams | None):
        """It seems like httpx is way more flexible when it comes
        to parameter types, see QueryParamTypes in _httpx_types.py"""
        params = super()._use_params(params)
        if not params:
            return

        normalized_params = {}
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, bool):
                normalized_params[key] = "True" if value else "False"
            else:
                normalized_params[key] = value

        return normalized_params

    def _use_request_kwargs(self) -> dict:
        kwargs = copy(self._common_request_kwargs)

        # httpx uses different name for this option
        redirects_allowed = kwargs.pop("allow_redirects", None)
        if redirects_allowed is not None:
            return kwargs | {"follow_redirects": redirects_allowed}

        return kwargs

    async def _process_request(
        self,
        method: HTTPMethod,
        url: StrOrURL,
        *,
        response_with_content: bool,
        headers: HeaderTypes = None,
        params: QueryParamTypes = None,
        data: RequestData = None,
        files: RequestFiles = None,
        **kwargs,
    ) -> bytes | None:
        client: AsyncClient = self._session
        req = client.build_request(
            method,
            str(url),
            headers=headers,
            params=params,
            data=data,
            files=files,
        )

        response: Response = await client.send(req, **kwargs)

        # AsyncClient has already consumed the stream into content field at this point
        if response.is_success:
            if response_with_content:
                if not response.content:
                    raise HTTPContentError(
                        self._NO_CONTENT_ERROR_MESSAGE.format(
                            method=method,
                            url=self._use_url_full(url, params),
                            resp=response,
                        ),
                    )
                return response.content
            return

        try:
            body = response.json()
        except JSONDecodeError:
            details = response.reason_phrase
        else:
            details = self._get_error_details(body)

        self._raise_for_status(
            details,
            url=self._use_url_full(url, params),
            method=method,
            status=response.status_code,
            reason=response.reason_phrase,
        )
