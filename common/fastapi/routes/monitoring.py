import logging

from fastapi import APIRouter

router = APIRouter(
    prefix="/monitoring",
    tags=["Monitoring"],
)

logger = logging.getLogger(__name__)


class TestError(Exception):
    pass


@router.get("/health")
async def health_check() -> None:
    """Test service health."""

    logger.debug("Monitoring: health_check")


@router.get("/error")
async def error_check() -> None:
    """Test Sentry errors reporting."""

    logger.debug("Monitoring: error_check")
    raise TestError("Test raise exception report. Not an error. ")
