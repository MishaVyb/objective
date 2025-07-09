from typing import Any

from starlette import status

from common.common._exceptions import ComprehensiveErrorDetails
from common.fastapi.exceptions import (
    BadRequest,
    BaseHTTPException,
    ConflictError,
    NotEnoughRights,
    NotFoundError,
    TokenError,
    ValidationError,
)

########################################################################################
# status code 4xx
########################################################################################

__all__ = [
    "BadRequest",
    "BaseHTTPException",
    "ConflictError",
    "NotEnoughRights",
    "NotFoundError",
    "TokenError",
    "ValidationError",
]


class NotFoundInstanceError(NotFoundError):
    pass


class DeletedInstanceError(NotFoundInstanceError):
    def __init__(
        self,
        instance: Any,
        detail: str | ComprehensiveErrorDetails | Any,
    ) -> None:
        self.instance = instance
        super().__init__(detail)


########################################################################################
# status code 5xx (internal)
########################################################################################


class ObjectiveInternalError(Exception):
    status_code: int
    msg: str

    def __str__(self) -> str:
        try:
            return self.msg.format(*self.args)
        except IndexError:
            return self.msg


class TimeWheelInternalError(ObjectiveInternalError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    msg = "Internal error. {}"


class RepositoryError(TimeWheelInternalError):
    msg = "Repository error"


class RefreshModifiedInstanceError(RepositoryError):
    msg = (
        "Trying to refresh modified instance: {} [id={}]. "
        "To persist all changes, `flush` should be called before. "
        "Otherwise call for `expire` explicitly. "
    )


class FlushMissingInstanceError(RepositoryError):
    msg = "Trying to flush instance that has not been queried before: {} [id={}]"


class ExpireMissingInstanceError(RepositoryError):
    msg = "Trying to expire instance that has not been queried before: {} [id={}]"


class MissingAttributesError(RepositoryError):
    msg = (
        "\n"
        "Fails on preparing result from database repository: {!r}\n"
        "If you got this error, there are might be several different reasons of that: \n"
        "\t1. Some model attributes were expired, 'refresh' option should be applied. \n"
        "\t2. Loading options does not match specified schema. "
        "Fix schema attributes or add relationship to loading options. \n"
    )
