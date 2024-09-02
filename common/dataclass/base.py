from dataclasses import Field, dataclass, fields
from typing import Generic, TypeVar

_T = TypeVar("_T")


@dataclass
class DataclassBase(Generic[_T]):
    @classmethod
    def fields(cls) -> tuple[Field[_T], ...]:
        return fields(cls)

    @classmethod
    def fieldnames(cls) -> tuple[str, ...]:
        return tuple(f.name for f in fields(cls))

    def asdict(self) -> dict[str, _T]:
        return {k.name: getattr(self, k.name) for k in self.fields()}

    def astuple(self) -> tuple[_T, ...]:
        return tuple(getattr(self, k.name) for k in self.fields())
