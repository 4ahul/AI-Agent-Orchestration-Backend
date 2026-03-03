"""
Custom exception hierarchy.
Ensures NO raw tracebacks are ever returned to clients.
"""


class AppBaseError(Exception):
    """Base for all application errors."""
    status_code: int = 500
    detail: str = "An unexpected error occurred"

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


class AuthenticationError(AppBaseError):
    status_code = 401
    detail = "Authentication failed"


class AuthorizationError(AppBaseError):
    status_code = 403
    detail = "Not authorized"


class NotFoundError(AppBaseError):
    status_code = 404
    detail = "Resource not found"


class ValidationError(AppBaseError):
    status_code = 422
    detail = "Validation failed"


class PDFProcessingError(AppBaseError):
    status_code = 422
    detail = "PDF processing failed"


class AgentExecutionError(AppBaseError):
    status_code = 500
    detail = "Agent execution failed"


class EmailDeliveryError(AppBaseError):
    status_code = 502
    detail = "Email delivery failed"


class DuplicateJobError(AppBaseError):
    status_code = 409
    detail = "Job already processing for this document"


class FileSizeError(AppBaseError):
    status_code = 413
    detail = "File exceeds maximum allowed size"


class InvalidFileTypeError(AppBaseError):
    status_code = 415
    detail = "Only PDF files are accepted"
