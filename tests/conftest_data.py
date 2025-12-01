import random
import time
from typing import TYPE_CHECKING, Self

from pydantic import Field, model_validator

from app.schemas.schemas import Element, ElementID


def _get_element_version_nonce():
    return random.randint(0, 999_999)


class ExcalidrawElement(Element):
    id: ElementID
    is_deleted: bool = False

    version: int = 1
    version_nonce: int = Field(default_factory=_get_element_version_nonce)
    updated: float = Field(default_factory=time.time)

    @model_validator(mode="after")
    def _model_validator(self):
        self.__pydantic_fields_set__ |= {
            "is_deleted",
            "version",
            "version_nonce",
            "updated",
        }

    def update(self, **kw) -> Self:
        self.version += 1
        self.version_nonce = _get_element_version_nonce()
        self.updated = time.time()
        for k, v in kw.items():
            setattr(self, k, v)
        return self

    if TYPE_CHECKING:
        key: str | None = None  # test field value
