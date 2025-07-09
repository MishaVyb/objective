import logging
from typing import NotRequired, TypedDict


class RequestLoggerContext(TypedDict):
    request_id: NotRequired[str]


class RequestLoggerAdapter(logging.LoggerAdapter):
    logger: logging.Logger
    extra: RequestLoggerContext | None

    def __init__(
        self,
        logger: logging.Logger,
        extra: RequestLoggerContext | None = None,
    ) -> None:
        super().__init__(logger, extra)

    def process(self, msg, kwargs):
        return "[%s] %s" % (self.extra.get("request_id"), msg), kwargs

    @property
    def level(self):
        return self.logger.level
