import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal, TypeVar

import yarl
from fastapi.encoders import jsonable_encoder
from pydantic import (
    AfterValidator,
    AwareDatetime,
    BeforeValidator,
    ConfigDict,
    PlainSerializer,
    RootModel,
    TypeAdapter,
)
from pydantic_core import core_schema
from typing_extensions import Annotated

from .constructor import ModelConstructor


class BaseSchema(ModelConstructor):

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        populate_by_name=True,
        use_attribute_docstrings=True,
    )

    def __str__(self) -> str:
        data = self.model_dump(exclude_none=True, exclude_unset=True)
        return f"{self.__class__.__name__}({data})"


class DictModel(RootModel):
    root: dict[str, Any]

    def __init__(self, *args, **kwargs):
        return super().__init__(root=dict(*args, **kwargs))


def _get_id(item: Any):
    if isinstance(item, dict):
        if "id" in item:
            return item["id"]
    if hasattr(item, "id"):
        return item.id
    return item


ITEM_PG_ID = Annotated[uuid.UUID, BeforeValidator(_get_id)]
"""Helper Pydantic type with validator to extract `id` from dict or arbitrary type. """


def _datetime_check_timezone(v: datetime | None):
    if not v:
        return v

    # normalize utc timezone
    if v.tzinfo and v.tzinfo.utcoffset(None) == timedelta(seconds=0):
        v = v.replace(tzinfo=timezone.utc)

    # validate
    if v.tzinfo != timezone.utc:
        raise ValueError(f"expecting UTC timezone, but got {v.tzinfo}")
    return v


def _datetime_check_microseconds(v: datetime | None):
    # rrule does not support microseconds by design, therefore it's forbidden globally
    if not v:
        return v
    if v.microsecond:
        raise ValueError("Microseconds is not allowed. ")
    return v


DatetimeUTC = Annotated[
    AwareDatetime,
    AfterValidator(_datetime_check_timezone),
    AfterValidator(_datetime_check_microseconds),
]
DatetimeUTCAdapter: TypeAdapter[DatetimeUTC] = TypeAdapter(DatetimeUTC)
DatetimeUTCOptionalAdapter: TypeAdapter[DatetimeUTC | None] = TypeAdapter(
    DatetimeUTC | None,
)

_T = TypeVar("_T")
JsonSerializable = Annotated[_T, PlainSerializer(lambda v: jsonable_encoder(v))]

NullValue = Literal[""]
"""None value compatible with FastAPI Query params. """


class _YarlURLPydanticSchema:
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        def validate_from_str(value: str):
            return yarl.URL(value)

        def serialize_to_str(value: yarl.URL):
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
                    core_schema.is_instance_schema(yarl.URL),
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


URL = Annotated[yarl.URL, _YarlURLPydanticSchema]
"""`yarl.URL` with Pydantic support. """
