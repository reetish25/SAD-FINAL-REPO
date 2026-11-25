class ApiError(Exception):
    """A business or access error. It becomes an HTTP reply with a stable error code."""

    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
