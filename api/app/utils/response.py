from typing import Optional

from flask import Response, make_response
from flask_openapi3.types import ResponseDict
from pydantic import Field, ValidationError

from app.models import ApiBaseModel


class ValidationErrorDetail(ApiBaseModel):
    """Safe validation error detail exposed to API clients."""

    type: str | None = None
    loc: list[str | int] = Field(default_factory=list)
    msg: str
    url: str | None = None


# Standard API error models
class ErrorResponse(ApiBaseModel):
    """Standard error response format"""

    message: str = Field(description="Main error message")
    code: Optional[str] = Field(default=None, description="Error code for programmatic handling")
    details: Optional[list[ValidationErrorDetail]] = Field(description="Detailed validation errors")


class ErrorResponseWithDefaultDetailsNone(ErrorResponse):
    details: Optional[list[ValidationErrorDetail]] = Field(
        default=None, description="Detailed validation errors"
    )


# Error codes for programmatic error handling
class ErrorCodes:
    # Authentication (401)
    UNAUTHORIZED = "UNAUTHORIZED"
    EXPIRED_TOKEN = "EXPIRED_TOKEN"
    INVALID_TOKEN = "INVALID_TOKEN"

    # Authorization (403)
    FORBIDDEN = "FORBIDDEN"

    # Client errors (400, 404, 409, 422)
    BAD_REQUEST = "BAD_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    CONFLICT = "CONFLICT"

    # Server errors (500, 503)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    INTEGRITY_ERROR = "INTEGRITY_ERROR"

    # Other
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


abp_responses = ResponseDict(
    {
        "4XX": ErrorResponseWithDefaultDetailsNone,
        "5XX": ErrorResponseWithDefaultDetailsNone,
        "422": ErrorResponse,
    }
)


def success_response(
    data: dict | list,
    status: int = 200,
) -> Response:
    """Create a standardized success response"""
    return make_response(data, status)


def error_response(
    message: str = "An error occurred",
    status: int = 500,
    code: Optional[str] = None,
    details: Optional[list[ValidationErrorDetail]] = None,
) -> Response:
    """Create a standardized error response"""
    response = ErrorResponse(
        message=message,
        code=code or None,
        details=details,
    )
    return make_response(response.model_dump(exclude_none=True), status)


def validation_error_response(validation_error: ValidationError) -> Response:
    """Convert Pydantic ValidationError to ErrorResponse format"""
    # Convert ErrorDetails to JSON-serializable dicts
    # by keeping only the safe serializable fields. Do not expose input values:
    # they can contain passwords, tokens, or other user-provided secrets.
    errors = [
        ValidationErrorDetail(
            type=error.get("type"),
            loc=list(error.get("loc") or []),
            msg=error.get("msg"),
            url=error.get("url") or "",
        )
        for error in validation_error.errors()
    ]

    return error_response(
        message="Validation failed",
        status=422,
        code=ErrorCodes.VALIDATION_ERROR,
        details=errors,
    )
