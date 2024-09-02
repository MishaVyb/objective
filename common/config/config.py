from enum import StrEnum
from typing import Any, Callable

from pydantic import BaseModel


class VerboseModel(BaseModel):
    """Prints out only overridden field values."""

    def model_verbose_representation(self, *, formatter: Callable[[Any], str] = str):
        fields_not_default = self.model_dump(exclude_unset=True)
        fields_repr = {k for k, v in self.model_fields.items() if v.repr}
        use_fields = [k for k in fields_not_default if k in fields_repr]
        kw = [f"{f}={formatter(getattr(self, f))}" for f in use_fields]
        overrides = "\n\t".join(kw)
        return f"{self.__class__.__name__}(\n\t{overrides}\n)"

    def __repr__(self) -> str:
        return self.model_verbose_representation(formatter=repr)

    def __str__(self) -> str:
        return self.model_verbose_representation(formatter=str)


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
