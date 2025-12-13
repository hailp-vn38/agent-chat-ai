# ruff: noqa
from fastcrud.exceptions.http_exceptions import (
    CustomException,
    BadRequestException,
    NotFoundException,
    ForbiddenException,
    UnauthorizedException,
    UnprocessableEntityException,
    DuplicateValueException,
    RateLimitException,
)


class ServiceUnavailableException(CustomException):
    """Exception for 503 Service Unavailable errors."""

    def __init__(self, detail: str = "Service temporarily unavailable"):
        super().__init__(status_code=503, detail=detail)
