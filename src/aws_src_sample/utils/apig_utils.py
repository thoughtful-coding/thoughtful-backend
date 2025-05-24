import base64
import json
import logging
import typing

_LOGGER = logging.getLogger(__name__)


def get_event_body(event: dict) -> bytes:
    if "isBase64Encoded" in event and event["isBase64Encoded"]:
        return base64.b64decode(event["body"])
    else:
        return event["body"].encode("utf-8")


def get_method(event: dict) -> str:
    return event.get("requestContext", {}).get("http", {}).get("method", "UNKNOWN")


def get_user_id_from_event(event: dict[str, typing.Any]) -> typing.Optional[str]:
    """
    Extracts user ID from Lambda event context (adapt to your authorizer).
    """
    try:
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {}).get("email")
        if user_id:
            return str(user_id)
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("principalId")
        if user_id:
            return str(user_id)
        _LOGGER.warning("User ID not found in authorizer context.")
        return None
    except Exception as e:
        _LOGGER.error("Error extracting user_id from event: %s", str(e))
        return None


def format_lambda_response(
    status_code: int,
    body: typing.Any,
    *,
    additional_headers: typing.Optional[dict[str, str]] = None,
) -> dict[str, typing.Any]:
    """
    Formats API Gateway proxy responses.
    """
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",  # FIXME: Restrict in production
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "OPTIONS,GET,PUT",
    }
    if additional_headers:
        headers.update(additional_headers)
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(body) if body is not None else None,
    }
