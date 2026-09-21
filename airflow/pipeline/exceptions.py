"""Sanitized errors raised at the OpenAQ boundary."""


class OpenAQError(Exception):
    """Base class for OpenAQ boundary failures."""


class AuthenticationError(OpenAQError):
    """The API rejected the configured OpenAQ credentials."""


class SchemaError(OpenAQError):
    """An OpenAQ response did not match the expected response envelope."""
