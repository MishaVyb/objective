import uuid

from fastapi_users import schemas

from objective.schemas.base import BaseSchema


# NOTE
# User is allowed to be updated PARTIALLY, so there are all fields are optional
class UserMixinSchema(BaseSchema):
    username: str | None = None
    role: str | None = None


class UserReadSchema(schemas.BaseUser[uuid.UUID], UserMixinSchema):
    pass


class UserCreateSchema(schemas.BaseUserCreate, UserMixinSchema):
    pass


class UserUpdateSchema(schemas.BaseUserUpdate, UserMixinSchema):
    pass
