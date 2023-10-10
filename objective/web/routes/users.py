from fastapi import APIRouter

from objective.schemas.users import UserCreateSchema, UserReadSchema, UserUpdateSchema
from objective.web.dependencies import api_users, auth_jwt

router = APIRouter()

router.include_router(
    api_users.get_register_router(UserReadSchema, UserCreateSchema),
    prefix="/auth",
    tags=["auth"],
)

router.include_router(
    api_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)

router.include_router(
    api_users.get_verify_router(UserReadSchema),
    prefix="/auth",
    tags=["auth"],
)

router.include_router(
    api_users.get_users_router(UserReadSchema, UserUpdateSchema),
    prefix="/users",
    tags=["users"],
)
router.include_router(
    api_users.get_auth_router(auth_jwt),
    prefix="/auth/jwt",
    tags=["auth"],
)
