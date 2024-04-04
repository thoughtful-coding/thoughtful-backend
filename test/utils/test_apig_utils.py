from aws_src_sample.utils.apig_utils import get_event_body


def test_get_event_body_1() -> None:
    event_body = {"body": "hello everyone"}
    assert get_event_body(event_body) == b"hello everyone"


def test_get_event_body_2() -> None:
    event_body = {
        "body": "aGVsbG8gZXZlcnlvbmU=",
        "isBase64Encoded": True,
    }
    assert get_event_body(event_body) == b"hello everyone"
