from flask import Response, request
from flask_jwt_extended.exceptions import JWTExtendedException
from sqlalchemy import exc as sa_exception
from werkzeug import exceptions

from app.utils.logging import logger
from app.utils.response import ErrorCodes, error_response


def register_error_handlers(app):
    """Register error handlers - all return ErrorResponse format"""

    # Note: Validation errors (422) are handled by Flask-OpenAPI3's validation_error_callback

    # Authentication errors (401)
    @app.errorhandler(JWTExtendedException)
    def handle_jwt_error(e):
        """Handle JWT authentication errors"""
        error_message = str(e) or "Authentication failed"
        logger.warning(
            "JWT error: %s | method=%s path=%s origin=%s user_agent=%s",
            error_message,
            request.method,
            request.path,
            request.headers.get("Origin"),
            request.user_agent.string,
        )

        # Determine specific error type
        if "expired" in error_message.lower():
            code = ErrorCodes.EXPIRED_TOKEN
        elif "invalid" in error_message.lower() or "decode" in error_message.lower():
            code = ErrorCodes.INVALID_TOKEN
        else:
            code = ErrorCodes.UNAUTHORIZED

        return error_response(message="Authentication failed", status=401, code=code)

    # Database errors
    @app.errorhandler(sa_exception.IntegrityError)
    def handle_integrity_error(e):
        """Handle database integrity errors (unique, foreign key, etc.)"""
        logger.error(
            "Database integrity error: %s | method=%s path=%s origin=%s user_agent=%s",
            str(e),
            request.method,
            request.path,
            request.headers.get("Origin"),
            request.user_agent.string,
        )
        error_str = str(e).lower()

        if "unique constraint" in error_str or "duplicate" in error_str:
            return error_response(
                message="Resource already exists",
                status=409,
                code=ErrorCodes.ALREADY_EXISTS,
            )

        return error_response(
            message="Database integrity error",
            status=409,
            code=ErrorCodes.INTEGRITY_ERROR,
        )

    @app.errorhandler(sa_exception.SQLAlchemyError)
    def handle_database_error(e):
        """Handle general database errors"""
        logger.error(
            "Database error: %s | method=%s path=%s origin=%s user_agent=%s",
            str(e),
            request.method,
            request.path,
            request.headers.get("Origin"),
            request.user_agent.string,
        )
        return error_response(
            message="Database error occurred",
            status=500,
            code=ErrorCodes.DATABASE_ERROR,
        )

    # HTTP exceptions
    @app.errorhandler(exceptions.HTTPException)
    def handle_http_exception(e: exceptions.HTTPException) -> Response:
        """Handle standard HTTP exceptions"""
        status_code = e.code or 500

        cause = e.__cause__
        cause_details = f" | cause={type(cause).__name__}: {cause}" if cause is not None else ""
        logger.warning(
            "HTTP %s: %s%s | method=%s path=%s origin=%s user_agent=%s",
            status_code,
            e.description,
            cause_details,
            request.method,
            request.path,
            request.headers.get("Origin"),
            request.user_agent.string,
        )

        return error_response(
            message=str(e.description) if e.description else "Request failed",
            status=status_code,
            code=_error_code_for_status(status_code),
        )

    # Generic fallback
    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        """Handle any unexpected errors"""
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)

        # Don't expose internal details in production
        message = (
            f"Unexpected error: {str(e)}"
            if app.config.get("DEBUG", False)
            else "An unexpected error occurred"
        )

        return error_response(
            message=message,
            status=500,
            code=ErrorCodes.INTERNAL_ERROR,
        )


def _error_code_for_status(status_code: int) -> str | None:
    return {
        400: ErrorCodes.BAD_REQUEST,
        401: ErrorCodes.UNAUTHORIZED,
        403: ErrorCodes.FORBIDDEN,
        404: ErrorCodes.NOT_FOUND,
        405: ErrorCodes.METHOD_NOT_ALLOWED,
        409: ErrorCodes.CONFLICT,
        429: ErrorCodes.RATE_LIMIT_EXCEEDED,
        500: ErrorCodes.INTERNAL_ERROR,
        503: ErrorCodes.DATABASE_ERROR,
    }.get(status_code)
