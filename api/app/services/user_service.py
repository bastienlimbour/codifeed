from typing import Tuple
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
from sqlmodel import Session, and_, case, col, func, or_, select
from sqlmodel.sql.expression import Select
from werkzeug.exceptions import BadRequest, Forbidden, NotFound

from app.models import (
    PaginationMeta,
    PaginationQuery,
    User,
    UserDetail,
    UserFollow,
    UserPublic,
)
from app.utils.pagination import paginate_query


class UserService:
    """Service responsible for all user-related business logic."""

    @staticmethod
    def get_by_id(session: Session, user_id: UUID) -> User:
        """Get user by ID."""
        user = session.get(User, user_id)

        if not user:
            raise NotFound(description="User not found")

        if user.is_deleted:
            raise NotFound(
                description="This account has been deleted. "
                "Please contact support if you believe this is an error."
            )

        return user

    @staticmethod
    def get_by_username(session: Session, username: str) -> User:
        """Get user by username."""
        user = session.exec(select(User).where(col(User.username) == username)).first()

        if not user:
            raise NotFound(description=f"User {username} not found")

        if user.is_deleted:
            raise NotFound(description=f"This account ({username}) has been deleted.")

        return user

    @staticmethod
    def delete_by_id(session: Session, user_id: UUID, username: str) -> User:
        """Delete user account by ID."""

        user = session.get(User, user_id)

        if not user:
            raise NotFound(description="User not found")

        if user.username != username:
            raise Forbidden(description="You are not allowed to delete this user")

        user.soft_delete()
        session.commit()

        return user

    @staticmethod
    def _select_users_with_follow_data(
        current_user_id: UUID,
    ) -> Select[Tuple[User, int, int, bool, bool]]:
        """Select users with follow data."""
        uf_followers = aliased(UserFollow)
        uf_following = aliased(UserFollow)

        return (
            select(  # pyright: ignore[reportCallIssue]
                User,
                func.count(func.distinct(uf_followers.follower_id)).label("followers_count"),
                func.count(func.distinct(uf_following.following_id)).label("following_count"),
                func.coalesce(
                    func.bool_or(uf_followers.follower_id == current_user_id), False
                ).label("is_following"),
                func.coalesce(
                    func.bool_or(uf_following.following_id == current_user_id), False
                ).label("is_followed_by"),
            )
            .join(uf_followers, uf_followers.following_id == col(User.id), isouter=True)
            .join(uf_following, uf_following.follower_id == col(User.id), isouter=True)
            .where(col(User.deleted_at).is_(None))
            .group_by(col(User.id))
        )

    @staticmethod
    def get_detail_by_username(
        session: Session,
        current_user_id: UUID,
        username: str,
    ) -> UserDetail:
        """Get a user's detail by username."""

        statement = UserService._select_users_with_follow_data(current_user_id).where(
            col(User.username) == username
        )

        result = session.exec(statement).first()
        if not result:
            raise NotFound(description=f"User {username} not found")

        user, followers_count, following_count, is_following, is_followed_by = result

        if user.deleted_at:
            raise NotFound(
                description=f"This account ({username}) has been deleted. "
                "Please contact support if you believe this is an error."
            )

        return UserDetail.model_validate(user).model_copy(
            update={
                "followers_count": int(followers_count or 0),
                "following_count": int(following_count or 0),
                "is_following": bool(is_following),
                "is_followed_by": bool(is_followed_by),
            }
        )

    @staticmethod
    def follow_by_username(
        session: Session,
        current_user_id: UUID,
        username: str,
    ) -> UserDetail:
        """Follow a user idempotently and return updated detail."""
        target = UserService.get_by_username(session, username)
        if not target.id:
            raise NotFound(description="User not found")
        if current_user_id == target.id:
            raise BadRequest(description="You cannot follow yourself")

        follow = UserFollow(follower_id=current_user_id, following_id=target.id)
        try:
            session.add(follow)
            session.commit()
        except IntegrityError:
            session.rollback()

        return UserService.get_detail_by_username(session, current_user_id, username)

    @staticmethod
    def unfollow_by_username(
        session: Session,
        current_user_id: UUID,
        username: str,
    ) -> UserDetail:
        """Unfollow a user and return updated detail; raise 404 if not following."""
        target = UserService.get_by_username(session, username)
        if not target.id:
            raise NotFound(description="User not found")

        follow = select(UserFollow).where(
            UserFollow.follower_id == current_user_id,
            UserFollow.following_id == target.id,
        )
        follow = session.exec(follow).first()

        if not follow:
            raise NotFound(description="You are not following this user")

        session.delete(follow)
        session.commit()

        return UserService.get_detail_by_username(session, current_user_id, username)

    @staticmethod
    def get_followers_by_username(
        session: Session,
        current_user_id: UUID,
        username: str,
        pagination: PaginationQuery,
    ) -> tuple[list[UserPublic], PaginationMeta]:
        """List followers (active users) of a target user with pagination."""

        user_follow = aliased(UserFollow)
        target_user = aliased(User)

        statement = (
            UserService._select_users_with_follow_data(current_user_id)
            .join(user_follow, col(user_follow.follower_id) == col(User.id))
            .join(
                target_user,
                and_(
                    col(target_user.id) == col(user_follow.following_id),
                    col(target_user.username) == username,
                ),
            )
        )

        result, meta = paginate_query(session=session, statement=statement, pagination=pagination)

        users = [
            UserPublic.model_validate(user).model_copy(
                update={
                    "followers_count": followers_count,
                    "following_count": following_count,
                    "is_following": is_following,
                    "is_followed_by": is_followed_by,
                }
            )
            for user, followers_count, following_count, is_following, is_followed_by in result
        ]

        return users, meta

    @staticmethod
    def get_following_by_username(
        session: Session,
        current_user_id: UUID,
        username: str,
        pagination: PaginationQuery,
    ) -> tuple[list[UserPublic], PaginationMeta]:
        """List users (active) that the target user is following with pagination."""

        user_follow = aliased(UserFollow)
        target_user = aliased(User)

        statement = (
            UserService._select_users_with_follow_data(current_user_id)
            .join(user_follow, col(user_follow.following_id) == col(User.id))
            .join(
                target_user,
                and_(
                    col(target_user.id) == col(user_follow.follower_id),
                    col(target_user.username) == username,
                ),
            )
        )

        result, meta = paginate_query(session=session, statement=statement, pagination=pagination)

        users = [
            UserPublic.model_validate(user).model_copy(
                update={
                    "is_following": is_following,
                    "is_followed_by": is_followed_by,
                }
            )
            for user, followers_count, following_count, is_following, is_followed_by in result
        ]

        return users, meta

    @staticmethod
    def search(
        session: Session,
        current_user_id: UUID,
        query: str,
        pagination: PaginationQuery,
    ) -> tuple[list[UserPublic], PaginationMeta]:
        """Search users by name/username, ordered by a relevance score."""
        search_term = query.strip()
        if not search_term:
            raise BadRequest(description="Search query is required")

        MIN_SIMILARITY_THRESHOLD = 0.3
        RELEVANCE_SCORES = {
            "EXACT_USERNAME": 100,
            "EXACT_NAME": 95,
            "PREFIX_USERNAME": 80,
            "PREFIX_NAME": 70,
            "SIMILARITY_MULTIPLIER": 40,
        }

        exact_username_condition = User.username == search_term
        exact_name_condition = User.name == search_term
        prefix_username_condition = col(User.username).ilike(search_term + "%")
        prefix_name_condition = col(User.name).ilike(search_term + "%")
        similarity_username_condition = (
            func.similarity(User.username, search_term) > MIN_SIMILARITY_THRESHOLD
        )
        similarity_name_condition = (
            func.similarity(User.name, search_term) > MIN_SIMILARITY_THRESHOLD
        )

        # TODO: Try to use this instead of the similarity function
        # similarity_username_condition = col(User.username).op("%")(search_term)
        # similarity_name_condition = col(User.name).op("%")(search_term)

        relevance_score = case(
            (exact_username_condition, RELEVANCE_SCORES["EXACT_USERNAME"]),
            (exact_name_condition, RELEVANCE_SCORES["EXACT_NAME"]),
            (prefix_username_condition, RELEVANCE_SCORES["PREFIX_USERNAME"]),
            (prefix_name_condition, RELEVANCE_SCORES["PREFIX_NAME"]),
            (
                similarity_username_condition,
                func.similarity(User.username, search_term)
                * RELEVANCE_SCORES["SIMILARITY_MULTIPLIER"],
            ),
            (
                similarity_name_condition,
                func.similarity(User.name, search_term) * RELEVANCE_SCORES["SIMILARITY_MULTIPLIER"],
            ),
            else_=func.greatest(
                func.similarity(User.username, search_term)
                * RELEVANCE_SCORES["SIMILARITY_MULTIPLIER"],
                func.similarity(User.name, search_term) * RELEVANCE_SCORES["SIMILARITY_MULTIPLIER"],
            ),
        ).label("relevance_score")

        statement = (
            UserService._select_users_with_follow_data(current_user_id)
            .where(
                or_(
                    exact_username_condition,
                    exact_name_condition,
                    prefix_username_condition,
                    prefix_name_condition,
                    similarity_username_condition,
                    similarity_name_condition,
                )
            )
            .order_by(relevance_score.desc(), col(User.username).asc())
        )

        users, meta = paginate_query(session=session, statement=statement, pagination=pagination)
        users = [
            UserPublic.model_validate(user).model_copy(
                update={
                    "followers_count": followers_count,
                    "following_count": following_count,
                    "is_following": is_following,
                    "is_followed_by": is_followed_by,
                }
            )
            for user, followers_count, following_count, is_following, is_followed_by in users
        ]

        return users, meta
