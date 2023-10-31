from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> None:
    """
    Checks the health of a project.

    It returns 200 if the project is healthy.
    """


@router.get("/error")
def error_check() -> None:
    raise RuntimeError("Not real error! Triggered by `error_check` handler. ")
