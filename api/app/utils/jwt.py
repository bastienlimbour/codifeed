from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable
from uuid import UUID

from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    verify_jwt_in_request,
)
from werkzeug.exceptions import Unauthorized


def login_required(func) -> Callable:
    """Decorator to check if the user is logged in with a valid access token"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        _verify_jwt_or_raise(refresh=False)
        return func(*args, **kwargs)

    return wrapper


def refresh_required(func) -> Callable:
    """Decorator to check if the user is logged in with a valid refresh token"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        _verify_jwt_or_raise(refresh=True)
        return func(*args, **kwargs)

    return wrapper


def _verify_jwt_or_raise(refresh: bool) -> None:
    try:
        verify_jwt_in_request(refresh=refresh)
    except Exception as e:
        description = (
            "Error verifying JWT: Refresh required"
            if refresh
            else "Error verifying JWT: Login required"
        )
        raise Unauthorized(description=description) from e


def get_current_user_id() -> UUID:
    """Get the current user ID from the JWT"""
    user_id = get_jwt_identity()
    if not user_id or not isinstance(user_id, str):
        raise Unauthorized("No valid token found")
    return UUID(user_id)


def create_tokens(user_id: UUID) -> tuple[str, str]:
    """Create a new access and refresh token for a user"""
    access_token = create_access_token(identity=user_id)
    refresh_token = create_refresh_token(identity=user_id)
    return access_token, refresh_token


def should_auto_refresh_token() -> bool:
    """Check if the token should be auto-refreshed (within 15 minutes of expiry)"""
    try:
        jwt = get_jwt()

        if not jwt:
            return False

        now = datetime.now(timezone.utc)
        exp_time = datetime.fromtimestamp(jwt["exp"], timezone.utc)
        time_until_expiry = exp_time - now

        return time_until_expiry <= timedelta(minutes=15)
    except (RuntimeError, KeyError):
        # Case where there is not a valid JWT. Just return False so the token is not auto-refreshed
        return False
