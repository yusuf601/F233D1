"""Sanitized errors raised at the OpenAQ boundary."""

from typing import NoReturn, Protocol


class OpenAQError(Exception):
    """Base class for OpenAQ boundary failures."""


class AuthenticationError(OpenAQError):
    """The API rejected the configured OpenAQ credentials."""


class SchemaError(OpenAQError):
    """An OpenAQ response did not match the expected response envelope."""


class GlobalInventoryUnavailableError(OpenAQError):
    """A fresh global inventory was unavailable, so this run cannot publish."""


class GlobalCache(Protocol):
    def read_global(self) -> object: ...


def abort_global_inventory_refresh(
    error: OpenAQError, cache: GlobalCache
) -> NoReturn:
    """Confirm cache state, then abort rather than publishing an empty inventory."""
    cache.read_global()
    raise GlobalInventoryUnavailableError(
        "global inventory refresh failed; publication is aborted"
    ) from error


def non_retryable_authentication_failure(
    error: AuthenticationError, failure_type: type[Exception]
) -> Exception:
    """Adapt sanitized authentication errors to the scheduler's fail-fast type."""
    return failure_type("OpenAQ authentication failed")
