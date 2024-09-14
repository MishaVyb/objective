from fastapi import APIRouter

from app.schemas import schemas

from ...dependencies.users import fastapi_users_api, fastapi_users_backend

router = APIRouter()

router.include_router(
    fastapi_users_api.get_register_router(schemas.User, schemas.UserCreate),
    prefix="/auth",
    tags=["Auth"],
)

router.include_router(
    fastapi_users_api.get_reset_password_router(),
    prefix="/auth",
    tags=["Auth"],
)

router.include_router(
    fastapi_users_api.get_verify_router(schemas.User),
    prefix="/auth",
    tags=["Auth"],
)

router.include_router(
    fastapi_users_api.get_auth_router(fastapi_users_backend),
    prefix="/auth/jwt",
    tags=["Auth"],
)


router.include_router(
    fastapi_users_api.get_users_router(schemas.User, schemas.UserUpdate),
    prefix="/users",
    tags=["Users"],
)
