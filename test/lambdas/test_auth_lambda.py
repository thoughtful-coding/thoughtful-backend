import json
from unittest.mock import Mock, patch

from thoughtful_backend.dynamodb.refresh_token_table import RefreshTokenTable
from thoughtful_backend.dynamodb.user_permissions_table import UserPermissionsTable
from thoughtful_backend.dynamodb.user_profile_table import UserProfileTable
from thoughtful_backend.lambdas.auth_lambda import AuthApiHandler, DEMO_SAMPLE_STUDENTS
from thoughtful_backend.utils.base_types import RefreshTokenId, UserId
from thoughtful_backend.utils.jwt_utils import JwtWrapper

MOCK_SECRET_KEY = "test-secret-key-for-jwt"
MOCK_GOOGLE_CLIENT_ID = "test-google-client-id.apps.googleusercontent.com"
MOCK_USER_ID = UserId("12345_google_user_sub")


def create_auth_api_handler(
    token_table=Mock(spec=RefreshTokenTable),
    secrets_repo=Mock(),
    google_client_id=MOCK_GOOGLE_CLIENT_ID,
    jwt_wrapper=JwtWrapper(),
    metrics_manager=Mock(),
    user_profile_table=Mock(spec=UserProfileTable),
    user_permissions_table=Mock(spec=UserPermissionsTable),
    enable_demo_permissions=False,
) -> AuthApiHandler:
    """Creates an instance of the handler with mocked dependencies."""
    auth_handler = AuthApiHandler(
        token_table=token_table,
        secrets_repo=secrets_repo,
        google_client_id=google_client_id,
        jwt_wrapper=jwt_wrapper,
        metrics_manager=metrics_manager,
        user_profile_table=user_profile_table,
        user_permissions_table=user_permissions_table,
        enable_demo_permissions=enable_demo_permissions,
    )
    assert auth_handler.token_table == token_table
    assert auth_handler.secrets_repo == secrets_repo
    assert auth_handler.google_client_id == google_client_id
    assert auth_handler.jwt_wrapper == jwt_wrapper
    assert auth_handler.metrics_manager == metrics_manager
    assert auth_handler.user_profile_table == user_profile_table
    assert auth_handler.user_permissions_table == user_permissions_table
    assert auth_handler.enable_demo_permissions == enable_demo_permissions
    return auth_handler


def create_mock_event(method: str, path: str, body: dict | None = None) -> dict:
    """Creates a mock API Gateway event dictionary."""
    return {
        "requestContext": {"http": {"method": method, "path": path}},
        "body": json.dumps(body) if body is not None else None,
    }


def test_handle_login_success():
    """Tests a successful user login with a valid Google token."""
    mock_token_table = Mock(spec=RefreshTokenTable)
    mock_token_table.save_token.return_value = True

    mock_secret_repo = Mock()
    mock_secret_repo.get_jwt_secret_key.return_value = "hey"

    handler = create_auth_api_handler(token_table=mock_token_table, secrets_repo=mock_secret_repo)

    with patch("thoughtful_backend.lambdas.auth_lambda.requests.get") as mock_requests_get:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "aud": MOCK_GOOGLE_CLIENT_ID,
            "sub": MOCK_USER_ID,
            "email": "test@example.com",
            "email_verified": True,
        }
        mock_requests_get.return_value = mock_response

        event = create_mock_event("POST", "/auth/login", {"googleIdToken": "valid_google_token"})
        response = handler.handle(event)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "accessToken" in body
        assert "refreshToken" in body

        mock_token_table.save_token.assert_called_once()


def test_handle_login_google_token_invalid():
    """Tests login failure when Google token has the wrong audience."""
    mock_secret_repo = Mock()
    mock_secret_repo.get_jwt_secret_key.return_value = "hey"

    handler = create_auth_api_handler(secrets_repo=mock_secret_repo)

    with patch("thoughtful_backend.lambdas.auth_lambda.requests.get") as mock_requests_get:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"aud": "wrong-audience-id", "sub": MOCK_USER_ID}
        mock_requests_get.return_value = mock_response

        event = create_mock_event("POST", "/auth/login", {"googleIdToken": "some_token"})

        response = handler.handle(event)

        assert response["statusCode"] == 401
        assert "Invalid Google token" in json.loads(response["body"])["message"]


def test_handle_refresh_success():
    """Tests a successful token refresh with a valid refresh token."""
    mock_token_table = Mock(spec=RefreshTokenTable)

    mock_secret_repo = Mock()
    mock_secret_repo.get_jwt_secret_key.return_value = "hey"

    handler = create_auth_api_handler(token_table=mock_token_table, secrets_repo=mock_secret_repo)

    refresh_token, token_id, _ = JwtWrapper().create_refresh_token(MOCK_USER_ID, mock_secret_repo)
    mock_token_table.get_token.return_value = {"userId": MOCK_USER_ID, "tokenId": token_id}

    event = create_mock_event("POST", "/auth/refresh", {"refreshToken": refresh_token})
    response = handler.handle(event)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "accessToken" in body
    assert body["refreshToken"] == refresh_token  # Refresh token is returned unchanged

    mock_token_table.get_token.assert_called_once_with(MOCK_USER_ID, token_id)


def test_handle_refresh_token_not_in_db():
    """Tests refresh failure when a valid token is not found in the database (e.g., logged out)."""
    mock_token_table = Mock(spec=RefreshTokenTable)
    mock_token_table.get_token.return_value = None  # Simulate token not found

    mock_secret_repo = Mock()
    mock_secret_repo.get_jwt_secret_key.return_value = "hey"

    handler = create_auth_api_handler(token_table=mock_token_table, secrets_repo=mock_secret_repo)

    refresh_token, _, _ = JwtWrapper().create_refresh_token(MOCK_USER_ID, mock_secret_repo)
    event = create_mock_event("POST", "/auth/refresh", {"refreshToken": refresh_token})

    response = handler.handle(event)

    assert response["statusCode"] == 401
    assert "Refresh token not found or expired" in json.loads(response["body"])["message"]


def test_handle_logout_success():
    """Tests a successful logout which should delete the refresh token."""
    mock_token_table = Mock(spec=RefreshTokenTable)

    mock_secret_repo = Mock()
    mock_secret_repo.get_jwt_secret_key.return_value = "hey"

    handler = create_auth_api_handler(token_table=mock_token_table, secrets_repo=mock_secret_repo)

    refresh_token, token_id, _ = JwtWrapper().create_refresh_token(MOCK_USER_ID, mock_secret_repo)

    event = create_mock_event("POST", "/auth/logout", {"refreshToken": refresh_token})

    response = handler.handle(event)

    assert response["statusCode"] == 200
    assert "Successfully logged out" in json.loads(response["body"])["message"]
    mock_token_table.delete_token.assert_called_once_with(MOCK_USER_ID, RefreshTokenId(token_id))


def test_handle_logout_with_invalid_token():
    """Tests that logout still returns a success code even if the token is invalid."""
    mock_token_table = Mock(spec=RefreshTokenTable)

    mock_secret_repo = Mock()
    mock_secret_repo.get_jwt_secret_key.return_value = "hey"

    handler = create_auth_api_handler(token_table=mock_token_table, secrets_repo=mock_secret_repo)

    event = create_mock_event("POST", "/auth/logout", {"refreshToken": "this.is.a.bad.token"})
    response = handler.handle(event)

    assert response["statusCode"] == 200
    assert "Successfully logged out" in json.loads(response["body"])["message"]
    mock_token_table.delete_token.assert_not_called()


def test_handle_unknown_auth_path():
    """Tests that an unknown path within the auth handler returns a 404."""
    handler = create_auth_api_handler()
    event = create_mock_event("POST", "/auth/some-unknown-path")

    response = handler.handle(event)

    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "Auth route not found" in body["message"]


def test_new_user_initialization_with_demo_permissions_enabled():
    """Tests that a new user gets demo permissions when demo mode is enabled."""
    mock_token_table = Mock(spec=RefreshTokenTable)
    mock_token_table.save_token.return_value = True

    mock_user_profile_table = Mock(spec=UserProfileTable)
    mock_user_profile_table.is_user_initialized.return_value = False
    mock_user_profile_table.mark_user_initialized.return_value = True
    mock_user_profile_table.update_last_login.return_value = True

    mock_user_permissions_table = Mock(spec=UserPermissionsTable)

    mock_secret_repo = Mock()
    mock_secret_repo.get_jwt_secret_key.return_value = "test-key"

    mock_metrics_manager = Mock()

    handler = create_auth_api_handler(
        token_table=mock_token_table,
        secrets_repo=mock_secret_repo,
        user_profile_table=mock_user_profile_table,
        user_permissions_table=mock_user_permissions_table,
        metrics_manager=mock_metrics_manager,
        enable_demo_permissions=True,
    )

    with patch("thoughtful_backend.lambdas.auth_lambda.requests.get") as mock_requests_get:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "aud": MOCK_GOOGLE_CLIENT_ID,
            "email": "newuser@example.com",
            "email_verified": True,
        }
        mock_requests_get.return_value = mock_response

        event = create_mock_event("POST", "/auth/login", {"googleIdToken": "valid_token"})
        response = handler.handle(event)

        # Verify login succeeded
        assert response["statusCode"] == 200

        # Verify last login was updated
        mock_user_profile_table.update_last_login.assert_called_once_with(UserId("newuser@example.com"))

        # Verify initialization was checked
        mock_user_profile_table.is_user_initialized.assert_called_once_with(UserId("newuser@example.com"))

        # Verify user was marked as initialized
        mock_user_profile_table.mark_user_initialized.assert_called_once_with(UserId("newuser@example.com"))

        # Verify demo permissions were granted (3 sample students + self)
        assert mock_user_permissions_table.grant_permission.call_count == 4

        # Verify permissions granted to sample students
        for student_id in DEMO_SAMPLE_STUDENTS:
            mock_user_permissions_table.grant_permission.assert_any_call(
                granter_user_id=UserId(student_id),
                grantee_user_id=UserId("newuser@example.com"),
                permission_type="VIEW_STUDENT_DATA_FULL",
            )

        # Verify permission granted to view own data
        mock_user_permissions_table.grant_permission.assert_any_call(
            granter_user_id=UserId("newuser@example.com"),
            grantee_user_id=UserId("newuser@example.com"),
            permission_type="VIEW_STUDENT_DATA_FULL",
        )

        # Verify metric was emitted
        mock_metrics_manager.put_metric.assert_any_call("NewUserInitialized", 1)


def test_new_user_initialization_with_demo_permissions_disabled():
    """Tests that a new user does NOT get demo permissions when demo mode is disabled."""
    mock_token_table = Mock(spec=RefreshTokenTable)
    mock_token_table.save_token.return_value = True

    mock_user_profile_table = Mock(spec=UserProfileTable)
    mock_user_profile_table.is_user_initialized.return_value = False
    mock_user_profile_table.mark_user_initialized.return_value = True
    mock_user_profile_table.update_last_login.return_value = True

    mock_user_permissions_table = Mock(spec=UserPermissionsTable)

    mock_secret_repo = Mock()
    mock_secret_repo.get_jwt_secret_key.return_value = "test-key"

    handler = create_auth_api_handler(
        token_table=mock_token_table,
        secrets_repo=mock_secret_repo,
        user_profile_table=mock_user_profile_table,
        user_permissions_table=mock_user_permissions_table,
        enable_demo_permissions=False,  # Demo disabled
    )

    with patch("thoughtful_backend.lambdas.auth_lambda.requests.get") as mock_requests_get:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "aud": MOCK_GOOGLE_CLIENT_ID,
            "email": "newuser@example.com",
            "email_verified": True,
        }
        mock_requests_get.return_value = mock_response

        event = create_mock_event("POST", "/auth/login", {"googleIdToken": "valid_token"})
        response = handler.handle(event)

        # Verify login succeeded
        assert response["statusCode"] == 200

        # Verify last login was updated
        mock_user_profile_table.update_last_login.assert_called_once_with(UserId("newuser@example.com"))

        # Verify initialization was checked
        mock_user_profile_table.is_user_initialized.assert_called_once_with(UserId("newuser@example.com"))

        # Verify user was marked as initialized
        mock_user_profile_table.mark_user_initialized.assert_called_once_with(UserId("newuser@example.com"))

        # Verify NO permissions were granted (demo disabled)
        mock_user_permissions_table.grant_permission.assert_not_called()


def test_existing_user_not_re_initialized():
    """Tests that an already initialized user does not get re-initialized."""
    mock_token_table = Mock(spec=RefreshTokenTable)
    mock_token_table.save_token.return_value = True

    mock_user_profile_table = Mock(spec=UserProfileTable)
    mock_user_profile_table.is_user_initialized.return_value = True  # Already initialized
    mock_user_profile_table.update_last_login.return_value = True

    mock_user_permissions_table = Mock(spec=UserPermissionsTable)

    mock_secret_repo = Mock()
    mock_secret_repo.get_jwt_secret_key.return_value = "test-key"

    handler = create_auth_api_handler(
        token_table=mock_token_table,
        secrets_repo=mock_secret_repo,
        user_profile_table=mock_user_profile_table,
        user_permissions_table=mock_user_permissions_table,
        enable_demo_permissions=True,  # Demo enabled but user already initialized
    )

    with patch("thoughtful_backend.lambdas.auth_lambda.requests.get") as mock_requests_get:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "aud": MOCK_GOOGLE_CLIENT_ID,
            "email": "existinguser@example.com",
            "email_verified": True,
        }
        mock_requests_get.return_value = mock_response

        event = create_mock_event("POST", "/auth/login", {"googleIdToken": "valid_token"})
        response = handler.handle(event)

        # Verify login succeeded
        assert response["statusCode"] == 200

        # Verify last login was updated
        mock_user_profile_table.update_last_login.assert_called_once_with(UserId("existinguser@example.com"))

        # Verify initialization was checked
        mock_user_profile_table.is_user_initialized.assert_called_once_with(UserId("existinguser@example.com"))

        # Verify user was NOT marked as initialized again
        mock_user_profile_table.mark_user_initialized.assert_not_called()

        # Verify NO permissions were granted
        mock_user_permissions_table.grant_permission.assert_not_called()
