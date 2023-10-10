import uuid

from fastapi_users import schemas

from objective.schemas.base import BaseSchema


class UserMixinSchema(BaseSchema):
    username: str | None
    role: str | None


class UserReadSchema(schemas.BaseUser[uuid.UUID], UserMixinSchema):
    pass


class UserCreateSchema(schemas.BaseUserCreate, UserMixinSchema):
    pass


class UserUpdateSchema(schemas.BaseUserUpdate, UserMixinSchema):
    pass
