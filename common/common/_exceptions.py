from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, BeforeValidator, Field, ValidationError
from pydantic_core import core_schema
from typing_extensions import Annotated

try:
    from fastapi.encoders import jsonable_encoder as jsonable_encoder_stub
except ImportError:

    def jsonable_encoder_stub(v):
        return v


class _ExceptionPydanticSchema:
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        def validate_from_str(value: str):
            raise ValueError("Validation from string to Exception is not supported. ")

        def serialize_to_str(value: Union[BaseException, str]):
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

DETAIL_ITEM_TYPE = Annotated[
    Union[list, dict, Any, None],
    BeforeValidator(lambda v: jsonable_encoder_stub(v)),
]


class ErrorDetails(BaseModel):
    msg: Union[str, Any] = Field(description="Verbose error message")
    # warning: default http exception handler (fastapi.exception_handlers.http_exception_handler)
    # uses plain json.dumps() to serialize the response
    items: DETAIL_ITEM_TYPE = Field(None, description="Items causing this error")
    original: Union[str, dict, ExceptionPydanticType, None] = Field(
        None,
        description="Any error original reason or error source",
    )


class ErrorRequestInfo(BaseModel):
    method: str
    uri: str

    id: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    data: Optional[str] = None


class ErrorResponseContent(BaseModel):
    detail: Union[ErrorDetails, str, dict, Any]
    trace_id: Optional[str] = None
    trace_url: Optional[str] = None
    exception: Optional[list[str]] = None  # `exc_info`
    request: Optional[ErrorRequestInfo] = None


class HTTPClientException(Exception):
    def __init__(
        self,
        status_code: int,
        detail: Union[ErrorDetails, Any, None] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        if isinstance(detail, ErrorDetails):
            detail = detail.model_dump(exclude_unset=True)
            detail = {k: v for k, v in detail.items() if v}  # exclude empty fields

        self.status_code = status_code
        self.detail = detail
        self.headers = headers

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.status_code=})"

    def __str__(self) -> str:
        return self.__repr__()


def get_error_details(data: Union[dict, str]) -> Union[ErrorDetails, Union[dict, str]]:
    """Extract error details to use it from scratch in raised exception."""
    try:
        schema = ErrorResponseContent.model_validate(data)
    except ValidationError:
        # got error content not satisfied common error response schema
        # return as it is without manipulation
        return data

    # extract verbose message from error content schema
    if isinstance(schema.detail, ErrorDetails):
        return ErrorDetails(
            msg=schema.detail.msg,
            original=schema.model_dump(exclude_none=True),
        )
    return ErrorDetails(
        msg=schema.detail,
        original=schema.model_dump(exclude_none=True),
    )
