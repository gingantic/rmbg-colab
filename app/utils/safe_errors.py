"""User-safe messages for server errors (no raw trace internals in production).

See :func:`app.config.expose_error_details` for ``DEBUG`` / ``WEBBRIA_DEBUG``.
"""

from app.config import expose_error_details


def internal_error_message(exc: BaseException) -> str:
    """Return text for 5xx JSON ``error`` fields.

    When debug is off (default), returns a generic message. When ``DEBUG`` or
    ``WEBBRIA_DEBUG`` enables debug mode, returns ``str(exc)`` for troubleshooting.
    """
    if expose_error_details():
        return str(exc)
    return "An internal error occurred. Please try again later."
