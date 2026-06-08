"""Integration tests for authentication routes."""

import pytest
from faker import Faker
from flask.testing import FlaskClient
from sqlmodel import Session, select

from app.models import User


@pytest.mark.integration
@pytest.mark.auth
def test_signup_creates_user_and_sets_cookies(
    client: FlaskClient, sample_user_data: dict, db_session: Session
):
    """Test POST /auth/signup creates a user and sets JWT cookies."""
    response = client.post("/auth/signup", json=sample_user_data)

    assert response.status_code == 201

    # Check response JSON contains user data
    json_data = response.get_json()
    assert json_data is not None
    assert "id" in json_data
    assert json_data["email"] == sample_user_data["email"]
    assert json_data["username"] == sample_user_data["username"]
    assert json_data["name"] == sample_user_data["name"]
    assert "password" not in json_data
    assert "hashedPassword" not in json_data

    # Check JWT cookies are set
    cookies = response.headers.getlist("Set-Cookie")
    cookie_names = [cookie.split("=")[0] for cookie in cookies]
    assert "access_token_cookie" in cookie_names
    assert "refresh_token_cookie" in cookie_names

    # Verify user exists in database
    statement = select(User).where(User.email == sample_user_data["email"])
    user = db_session.exec(statement).first()
    assert user is not None
    assert user.email == sample_user_data["email"]
    assert user.username == sample_user_data["username"]


@pytest.mark.integration
@pytest.mark.auth
def test_signup_duplicate_email(client: FlaskClient, created_user, faker_instance: Faker):
    """Test POST /auth/signup with duplicate email returns 400."""
    duplicate_data = {
        "name": faker_instance.name(),
        "username": faker_instance.user_name()
        + faker_instance.random_int(min=1000, max=9999).__str__(),
        "email": created_user.email,  # Use existing user's email
        "password": faker_instance.password(length=12),
    }

    response = client.post("/auth/signup", json=duplicate_data)

    assert response.status_code == 400

    json_data = response.get_json()
    assert json_data is not None
    assert "message" in json_data
    assert json_data["message"] == "A user with this email already exists"
    assert json_data["code"] == "BAD_REQUEST"


@pytest.mark.integration
@pytest.mark.auth
def test_signup_duplicate_username(client: FlaskClient, created_user, faker_instance: Faker):
    """Test POST /auth/signup with duplicate username returns 400."""
    duplicate_data = {
        "name": faker_instance.name(),
        "username": created_user.username,  # Use existing user's username
        "email": faker_instance.email(),
        "password": faker_instance.password(length=12),
    }

    response = client.post("/auth/signup", json=duplicate_data)

    assert response.status_code == 400

    json_data = response.get_json()
    assert json_data is not None
    assert "message" in json_data
    assert json_data["message"] == "A user with this username already exists"
    assert json_data["code"] == "BAD_REQUEST"


@pytest.mark.integration
@pytest.mark.auth
def test_signup_validation_error_does_not_expose_input(client: FlaskClient, sample_user_data: dict):
    """Test validation errors do not expose raw input values such as passwords."""
    signup_data = {
        **sample_user_data,
        "password": "weakpassword",
    }

    response = client.post("/auth/signup", json=signup_data)

    assert response.status_code == 422

    json_data = response.get_json()
    assert json_data is not None
    assert json_data["message"] == "Validation failed"
    assert json_data["code"] == "VALIDATION_ERROR"
    assert "details" in json_data
    assert json_data["details"]
    assert all("input" not in error for error in json_data["details"])
    assert signup_data["password"] not in str(json_data)


@pytest.mark.integration
@pytest.mark.auth
def test_login_success(client: FlaskClient, created_user, sample_user_data: dict):
    """Test POST /auth/login with valid credentials returns 200 and sets cookies."""
    login_data = {
        "email": sample_user_data["email"],
        "password": sample_user_data["password"],
    }

    response = client.post("/auth/login", json=login_data)

    assert response.status_code == 200

    # Check response JSON contains user data
    json_data = response.get_json()
    assert json_data is not None
    assert "id" in json_data
    assert json_data["email"] == sample_user_data["email"]
    assert json_data["username"] == sample_user_data["username"]
    assert "password" not in json_data
    assert "hashedPassword" not in json_data

    # Check JWT cookies are set
    cookies = response.headers.getlist("Set-Cookie")
    cookie_names = [cookie.split("=")[0] for cookie in cookies]
    assert "access_token_cookie" in cookie_names
    assert "refresh_token_cookie" in cookie_names


@pytest.mark.integration
@pytest.mark.auth
def test_login_invalid_email(client: FlaskClient, created_user, faker_instance: Faker):
    """Test POST /auth/login with unknown email returns 400."""
    login_data = {
        "email": faker_instance.email(),  # Non-existent email
        "password": faker_instance.password(length=12),
    }

    response = client.post("/auth/login", json=login_data)

    assert response.status_code == 400

    json_data = response.get_json()
    assert json_data is not None
    assert "message" in json_data
    assert json_data["message"] == "Invalid email or password"


@pytest.mark.integration
@pytest.mark.auth
def test_login_invalid_password(
    client: FlaskClient, created_user, sample_user_data: dict, faker_instance: Faker
):
    """Test POST /auth/login with wrong password returns 400."""
    login_data = {
        "email": sample_user_data["email"],
        "password": faker_instance.password(length=12),  # Wrong password
    }

    response = client.post("/auth/login", json=login_data)

    assert response.status_code == 400

    json_data = response.get_json()
    assert json_data is not None
    assert "message" in json_data
    assert json_data["message"] == "Invalid email or password"


@pytest.mark.integration
@pytest.mark.auth
def test_refresh_success(client: FlaskClient, created_user, auth_tokens_for_user):
    """Test POST /auth/refresh with valid refresh token returns 200 and new tokens."""
    tokens = auth_tokens_for_user(created_user)

    # Set refresh token cookie
    client.set_cookie(
        key="refresh_token_cookie",
        value=tokens["refresh_token_cookie"],
        domain="localhost",
    )

    response = client.post("/auth/refresh")

    assert response.status_code == 200

    # Check response JSON contains user data
    json_data = response.get_json()
    assert json_data is not None
    assert "id" in json_data
    assert json_data["email"] == created_user.email
    assert json_data["username"] == created_user.username

    # Check new JWT cookies are set
    cookies = response.headers.getlist("Set-Cookie")
    cookie_names = [cookie.split("=")[0] for cookie in cookies]
    assert "access_token_cookie" in cookie_names
    assert "refresh_token_cookie" in cookie_names


@pytest.mark.integration
@pytest.mark.auth
def test_refresh_invalid_token(client: FlaskClient):
    """Test POST /auth/refresh without valid refresh token returns 401."""
    # Set an invalid refresh token
    client.set_cookie(
        key="refresh_token_cookie",
        value="invalid_token_value",
        domain="localhost",
    )

    response = client.post("/auth/refresh")

    assert response.status_code == 401

    json_data = response.get_json()
    assert json_data is not None
    assert "message" in json_data
    assert "Error verifying JWT: Refresh required" in json_data["message"]
    assert json_data["code"] == "UNAUTHORIZED"


@pytest.mark.integration
@pytest.mark.auth
def test_logout_clears_jwt_cookies(client: FlaskClient, created_user, auth_tokens_for_user):
    """Test POST /auth/logout clears JWT cookies."""
    tokens = auth_tokens_for_user(created_user)

    # Set both access and refresh token cookies
    client.set_cookie(
        key="access_token_cookie",
        value=tokens["access_token_cookie"],
        domain="localhost",
    )
    client.set_cookie(
        key="refresh_token_cookie",
        value=tokens["refresh_token_cookie"],
        domain="localhost",
    )

    response = client.post("/auth/logout")

    assert response.status_code == 204

    # Check that cookies are being cleared/expired
    cookies = response.headers.getlist("Set-Cookie")
    cookie_strings = " ".join(cookies)

    # The unset_jwt_cookies function should set cookies with empty values or Max-Age=0
    assert "access_token_cookie" in cookie_strings
    assert "refresh_token_cookie" in cookie_strings
