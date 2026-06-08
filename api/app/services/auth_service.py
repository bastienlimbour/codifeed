from argon2 import exceptions as argon_exceptions
from sqlmodel import Session, or_, select
from werkzeug.exceptions import BadRequest, InternalServerError

from app.models import Profile, User, UserCreate
from app.utils.password import hash_password, verify_password


class AuthService:
    """Service responsible for all authentication-related business logic."""

    @staticmethod
    def create_user(session: Session, user_data: UserCreate) -> User:
        """Create a new user account and return user data."""
        statement = select(User).where(
            or_(User.email == user_data.email, User.username == user_data.username)
        )
        existing_user = session.exec(statement).first()

        if existing_user and existing_user.email == user_data.email:
            raise BadRequest(description="A user with this email already exists")

        if existing_user and existing_user.username == user_data.username:
            raise BadRequest(description="A user with this username already exists")

        profile = Profile()
        user = User.model_validate(
            user_data,
            update={
                "profile": profile,
                "hashed_password": hash_password(user_data.password),
            },
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        if not user or not user.id:
            raise InternalServerError(description="Failed to create user")

        return user

    @staticmethod
    def authenticate_user(session: Session, email: str, password: str) -> User:
        """Authenticate a user with email and password."""
        try:
            statement = select(User).where(User.email == email)
            user = session.exec(statement).first()

            if not user or not verify_password(password, user.hashed_password):
                raise BadRequest(description="Invalid email or password")

            if not user.id:
                raise InternalServerError(description="Failed to login user")

            return user

        except (
            argon_exceptions.VerifyMismatchError,
            argon_exceptions.InvalidHashError,
            argon_exceptions.VerificationError,
        ) as error:
            raise BadRequest(description="Invalid email or password") from error
