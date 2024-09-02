import logging
from types import ModuleType
from typing import TypedDict

import sentry_sdk
from fastapi import Request
from fastapi.params import Depends
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from .base import LoggerMiddleware


def init_sentry(
    settings: ModuleType,
    version: str = None,
    logger: logging.Logger = logging.getLogger(__name__),
):
    if not getattr(settings, "SENTRY_DSN", None):
        raise ValueError("Sentry DSN is required. ")

    logger.info("Setup Sentry. Environment: %s", settings.SENTRY_ENVIRONMENT)
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        ca_certs=settings.SENTRY_CA_CERTS,
        release=f"{settings.APP_NAME}@{version}" if version else settings.APP_NAME,
        environment=settings.SENTRY_ENVIRONMENT,
        enable_tracing=settings.SENTRY_TRACING,
        attach_stacktrace=True,
        integrations=[StarletteIntegration(), FastApiIntegration()],
    )


class UserInfo(TypedDict):
    id: int
    username: str | None


class SentryLoggerMiddleware(LoggerMiddleware):
    # many request may have common trace_id, if parent trace_id reused,
    # but request_id is always uniq for single request,
    # therefore do not replace request_id with trace_id
    pass


# this should be a middleware too, but it was implemented as dependency already, anyway
# in that case there are no much deference
class SentryTracingContextDepends(Depends):
    """
    Sentry Tracing helper dependence.

    Distributed tracing works out of the box. Add logging and populate context with
    extra information.

    https://docs.sentry.io/platforms/python/usage/distributed-tracing/custom-instrumentation/
    """

    def __init__(self, *, dashboard_url: str | None = None):
        self.dashboard_url = dashboard_url
        super().__init__(self, use_cache=True)

    async def __call__(self, request: Request):
        trace_url = ""
        trace_id = None
        if span := sentry_sdk.get_current_span():
            trace_id = span.trace_id
            if self.dashboard_url:
                trace_url = f"{self.dashboard_url}/performance/trace/{span.trace_id}"

        request.state.trace_id = trace_id
        logger = self.get_transaction_logger(request)
        if request.headers.get("sentry-trace"):
            logger.debug("Tracing: %s. Continue parent trace. %s", trace_id, trace_url)
        else:
            logger.debug("Tracing: %s. Starting new trace. %s", trace_id, trace_url)

        try:
            yield
        finally:
            if user := self.get_transaction_user(request):
                sentry_sdk.set_user(user)

    def get_transaction_logger(self, request: Request):
        """Get logger attached to current request. By default return global module logger."""
        return getattr(request.state, "logger", logging.getLogger(__name__))

    def get_transaction_user(self, request: Request) -> UserInfo | None:
        """Get user associated with current request. Supports both dict and arbitrary User types"""
        try:
            user = request.state.user
            if not user:
                return None

            user_info = {}
            if isinstance(user, dict):
                if id := user.get("id") or user.get("user_id"):
                    user_info["id"] = id
                if username := user.get("username"):
                    user_info["username"] = username
                return user_info or None

            # from attributes (arbitrary type):
            if id := getattr(user, "id", None) or getattr(user, "user_id", None):
                user_info["id"] = id
            if username := getattr(user, "username", None):
                user_info["username"] = username

            return user_info or None

        except AttributeError:
            return None
