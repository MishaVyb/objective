from abc import ABC, abstractmethod

from common.schemas.base import SchemaBase


class AbstractRepository(ABC):
    @abstractmethod
    async def get(self, pk: int, *args, **kwargs) -> SchemaBase:
        ...

    @abstractmethod
    async def create(self, payload: SchemaBase, *args, **kwargs) -> SchemaBase:
        ...

    @abstractmethod
    async def update(self, pk: int, payload: SchemaBase, *args, **kwargs) -> SchemaBase:
        ...

    @abstractmethod
    async def delete(self, pk: int, *args, **kwargs) -> None:
        ...


class ReadonlyAbstractRepository(AbstractRepository):
    async def create(self, **kwargs):
        raise NotImplementedError("Method not allowed: readonly repository. ")

    async def update(self, **kwargs):
        raise NotImplementedError("Method not allowed: readonly repository. ")

    async def delete(self, **kwargs):
        raise NotImplementedError("Method not allowed: readonly repository. ")
