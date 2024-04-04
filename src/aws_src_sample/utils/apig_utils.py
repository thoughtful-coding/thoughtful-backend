import base64


def get_event_body(event: dict) -> bytes:
    if "isBase64Encoded" in event and event["isBase64Encoded"]:
        return base64.b64decode(event["body"])
    else:
        return event["body"].encode("utf-8")
