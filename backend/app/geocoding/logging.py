"""Redact Geoapify's query-string credentials from HTTP client log records."""
import logging
import re


class CredentialFilter(logging.Filter):
    def filter(self, record):
        record.msg = re.sub(r"(?i)(apiKey=)[^&\s'\"]+", r"\1[REDACTED]", record.getMessage())
        record.args = ()
        return True


def protect_http_logs():
    for name in ("httpx", "httpcore.connection", "httpcore.http11", "httpcore.http2", "httpcore.proxy"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, CredentialFilter) for f in logger.filters):
            logger.addFilter(CredentialFilter())
