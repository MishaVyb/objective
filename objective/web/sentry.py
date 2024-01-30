import logging

import sentry_sdk
from fastapi import Request
from fastapi.params import Depends

logger = logging.getLogger(__name__)


class SentryTracingContextDepends(Depends):
    def __init__(self, *, dashboard_url: str | None = None):
        self.dashboard_url = dashboard_url
        super().__init__(self, use_cache=True)

    async def __call__(self, request: Request):
        trace_url = ""
        trace_id = None
        span = sentry_sdk.get_current_span()
        if span:
            trace_id = span.trace_id
            if self.dashboard_url:
                trace_url = f"{self.dashboard_url}/performance/trace/{span.trace_id}"

        if request.headers.get("sentry-trace"):
            logger.debug("Tracing: %s. Continue parent trace. %s", trace_id, trace_url)
        else:
            logger.debug("Tracing: %s. Starting new trace. %s", trace_id, trace_url)
