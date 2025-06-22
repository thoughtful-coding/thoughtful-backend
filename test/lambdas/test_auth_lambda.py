import json
from unittest.mock import Mock

from aws_src_sample.lambdas.auth_lambda import AuthApiHandler


def create_auth_api_handler() -> AuthApiHandler:
    """
    Helper function to create an instance of the AuthApiHandler with mocked dependencies.
    """
    # Currently, AuthApiHandler has no dependencies, but this is a good pattern for the future.
    handler = AuthApiHandler()
    return handler


def create_event(method: str, path: str) -> dict:
    """
    Creates a mock API Gateway event.
    """
    return {
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
            }
        },
    }


def test_auth_api_handler_1():
    """
    Tests that the AuthApiHandler can be instantiated.
    """
    create_auth_api_handler()


def test_auth_api_handler_handle_unsupported_path():
    """
    Tests that the handler returns a 501 Not Implemented for an undefined path.
    """
    handler = create_auth_api_handler()
    event = create_event("POST", "/auth/some-unknown-path")

    response = handler.handle(event)

    assert response["statusCode"] == 501
    body = json.loads(response["body"])
    assert "not implemented yet" in body["message"].lower()
