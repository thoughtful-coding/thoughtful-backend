import json

from thoughtful_backend.utils.apig_utils import (
    ErrorCode,
    create_error_response,
    format_lambda_response,
    get_event_body,
    get_method,
    get_user_id_from_event,
)


def test_get_event_body_1() -> None:
    event_body = {"body": "hello everyone"}
    assert get_event_body(event_body) == b"hello everyone"


def test_get_event_body_2() -> None:
    event_body = {
        "body": "aGVsbG8gZXZlcnlvbmU=",
        "isBase64Encoded": True,
    }
    assert get_event_body(event_body) == b"hello everyone"


def test_get_method_1() -> None:
    event = {"requestContext": {"http": {"method": "PUT"}}}
    assert get_method(event) == "PUT"


def test_get_method_2() -> None:
    event = {"requestContext": {}}
    assert get_method(event) == "UNKNOWN"


def test_get_user_id_from_event_1() -> None:
    event = {
        "requestContext": {
            "authorizer": {"lambda": {"email": "erizzi@ucls.uchicago.edu", "email_verified": "true", "sub": "1234"}}
        }
    }

    assert get_user_id_from_event(event) == "1234"


def test_get_user_id_from_event_2() -> None:
    event = {"requestContext": {}}

    assert get_user_id_from_event(event) == None


def test_format_lambda_response_1() -> None:
    ret = format_lambda_response(200, {"hey": "there"})
    assert ret["statusCode"] == 200
    assert len(ret["headers"]) == 4
    assert ret["headers"]["Content-Type"] == "application/json"
    assert ret["headers"]["Access-Control-Allow-Origin"] == "*"
    assert (
        ret["headers"]["Access-Control-Allow-Headers"]
        == "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token"
    )
    assert ret["headers"]["Access-Control-Allow-Methods"] == "OPTIONS,GET,PUT"
    assert ret["body"] == '{"hey": "there"}'


def test_format_lambda_response_2() -> None:
    ret = format_lambda_response(200, None, additional_headers={"hi": "you"})
    assert ret["statusCode"] == 200
    assert len(ret["headers"]) == 5
    assert ret["headers"]["Content-Type"] == "application/json"
    assert ret["headers"]["Access-Control-Allow-Origin"] == "*"
    assert (
        ret["headers"]["Access-Control-Allow-Headers"]
        == "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token"
    )
    assert ret["headers"]["Access-Control-Allow-Methods"] == "OPTIONS,GET,PUT"
    assert ret["headers"]["hi"] == "you"
    assert ret["body"] == None


def test_format_lambda_response_3() -> None:
    ret = format_lambda_response(200, {"hey": "there"}, event={"headers": {"origin": "evil.com"}})
    assert ret["statusCode"] == 200
    assert len(ret["headers"]) == 4
    assert ret["headers"]["Content-Type"] == "application/json"
    assert ret["headers"]["Access-Control-Allow-Origin"] == "null"
    assert (
        ret["headers"]["Access-Control-Allow-Headers"]
        == "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token"
    )
    assert ret["headers"]["Access-Control-Allow-Methods"] == "OPTIONS,GET,PUT"
    assert ret["body"] == '{"hey": "there"}'


def test_format_lambda_response_4() -> None:
    ret = format_lambda_response(200, {"hey": "there"}, event={"headers": {"origin": "https://example.github.io"}})
    assert ret["statusCode"] == 200
    assert len(ret["headers"]) == 4
    assert ret["headers"]["Content-Type"] == "application/json"
    assert ret["headers"]["Access-Control-Allow-Origin"] == "https://example.github.io"
    assert (
        ret["headers"]["Access-Control-Allow-Headers"]
        == "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token"
    )
    assert ret["headers"]["Access-Control-Allow-Methods"] == "OPTIONS,GET,PUT"
    assert ret["body"] == '{"hey": "there"}'


def test_create_error_response_1() -> None:
    response = create_error_response(ErrorCode.VALIDATION_ERROR)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["message"] == "Invalid request data"
    assert body["errorCode"] == "VALIDATION_ERROR"
    assert "details" not in body
    assert "Access-Control-Allow-Origin" in response["headers"]


def test_create_error_response_2() -> None:
    response = create_error_response(ErrorCode.AUTHENTICATION_FAILED, "Invalid token provided")

    assert response["statusCode"] == 401
    body = json.loads(response["body"])
    assert body["message"] == "Invalid token provided"
    assert body["errorCode"] == "AUTHENTICATION_FAILED"
    assert "details" not in body


def test_create_error_response_3() -> None:
    validation_errors = [
        {"loc": ["body", "email"], "msg": "field required", "type": "value_error.missing"},
        {"loc": ["body", "password"], "msg": "field required", "type": "value_error.missing"}
    ]
    response = create_error_response(ErrorCode.VALIDATION_ERROR, details=validation_errors)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["message"] == "Invalid request data"
    assert body["errorCode"] == "VALIDATION_ERROR"
    assert body["details"] == validation_errors


def test_create_error_response_4() -> None:
    event = {"headers": {"origin": "https://test.github.io"}}
    response = create_error_response(ErrorCode.AUTHORIZATION_FAILED, event=event)

    assert response["statusCode"] == 403
    assert response["headers"]["Access-Control-Allow-Origin"] == "https://test.github.io"
    body = json.loads(response["body"])
    assert body["message"] == "Access denied"
    assert body["errorCode"] == "AUTHORIZATION_FAILED"


def test_create_error_response_5() -> None:
    test_cases = [
        (ErrorCode.VALIDATION_ERROR, 400, "VALIDATION_ERROR"),
        (ErrorCode.AUTHENTICATION_FAILED, 401, "AUTHENTICATION_FAILED"),
        (ErrorCode.AUTHORIZATION_FAILED, 403, "AUTHORIZATION_FAILED"),
        (ErrorCode.RESOURCE_NOT_FOUND, 404, "RESOURCE_NOT_FOUND"),
        (ErrorCode.METHOD_NOT_ALLOWED, 405, "METHOD_NOT_ALLOWED"),
        (ErrorCode.RATE_LIMIT_EXCEEDED, 429, "RATE_LIMIT_EXCEEDED"),
        (ErrorCode.AI_SERVICE_UNAVAILABLE, 503, "AI_SERVICE_UNAVAILABLE"),
        (ErrorCode.INTERNAL_ERROR, 500, "INTERNAL_ERROR"),
    ]

    for error_code, expected_status, expected_code_string in test_cases:
        response = create_error_response(error_code)
        assert response["statusCode"] == expected_status
        body = json.loads(response["body"])
        assert body["errorCode"] == expected_code_string
        assert body["message"] == error_code.default_message


def test_create_error_response_6() -> None:
    details = {"field": "email", "error": "Invalid email format"}
    response = create_error_response(ErrorCode.VALIDATION_ERROR, "Request validation failed", details=details)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["message"] == "Request validation failed"
    assert body["errorCode"] == "VALIDATION_ERROR"
    assert body["details"] == details


def test_create_error_response_7() -> None:
    response = create_error_response(ErrorCode.RATE_LIMIT_EXCEEDED)

    assert response["statusCode"] == 429
    body = json.loads(response["body"])
    assert body["message"] == "Rate limit exceeded"
    assert body["errorCode"] == "RATE_LIMIT_EXCEEDED"


def test_create_error_response_8() -> None:
    response = create_error_response(ErrorCode.METHOD_NOT_ALLOWED)

    assert response["statusCode"] == 405
    body = json.loads(response["body"])
    assert body["message"] == "Method not allowed"
    assert body["errorCode"] == "METHOD_NOT_ALLOWED"
