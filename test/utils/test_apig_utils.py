from thoughtful_backend.utils.apig_utils import (
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
