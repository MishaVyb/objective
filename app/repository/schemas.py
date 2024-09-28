from __future__ import annotations

from typing import Any

from app.repository import models
from app.schemas.base import *  # TMP
from app.schemas.schemas import *  # TMP

# internal Repository schemas:


class SceneExtendedInternal(SceneExtended):
    elements: list[ElementInternal]


class ElementInternal(Element):
    @model_validator(mode="before")
    def model_validator(cls, obj: Any):
        if isinstance(obj, models.Element):
            return obj.json
        return obj
