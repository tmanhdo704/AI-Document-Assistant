class ApplicationError(Exception):
    """Base class for stable, application-level errors."""

    code = "APPLICATION_ERROR"
