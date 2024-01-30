import sentry_sdk
import uvicorn
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from objective.settings import settings

if settings.sentry_dns:
    sentry_sdk.init(
        dsn=settings.sentry_dns,
        environment=settings.sentry_env,
        # release= # TODO...
        enable_tracing=settings.sentry_tracing,
        attach_stacktrace=True,
        integrations=[StarletteIntegration(), FastApiIntegration()],
    )


def main() -> None:
    """Entrypoint of the application."""

    uvicorn.run(
        "objective.web.application:get_app",
        workers=settings.workers_count,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level,
        factory=True,
    )


if __name__ == "__main__":
    main()
