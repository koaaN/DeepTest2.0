class DeepTestingError(RuntimeError):
    """Base error raised by this package."""


class ProtocolError(DeepTestingError):
    """The remote response does not match the reverse-engineered protocol."""


class AuthenticationError(DeepTestingError):
    """A usable DeepTesting business token is unavailable."""


class HeyTapApiError(AuthenticationError):
    """HeyTap rejected an account or authorization request."""

    def __init__(self, code: int, message: str, error_data: object = None):
        super().__init__(f"HeyTap request failed: {code} {message}".rstrip())
        self.code = code
        self.message = message
        self.error_data = error_data
