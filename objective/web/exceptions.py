from typing import Any, Dict

from fastapi import HTTPException


class NotFoundError(HTTPException):
    message = "Not Found. "

    def __init__(
        self,
        detail: Any = None,
        headers: Dict[str, str] | None = None,
    ) -> None:
        super().__init__(404, detail or self.message, headers)


class ForbiddenError(HTTPException):
    message = "Access denied. User has not permissions to perform that action. "

    def __init__(
        self,
        detail: Any = None,
        headers: Dict[str, str] | None = None,
    ) -> None:
        super().__init__(403, detail or self.message, headers)


class NotAuthorizedError(HTTPException):
    message = "Not Authorized. "

    def __init__(
        self,
        detail: Any = None,
        headers: Dict[str, str] | None = None,
    ) -> None:
        super().__init__(401, detail or self.message, headers)
