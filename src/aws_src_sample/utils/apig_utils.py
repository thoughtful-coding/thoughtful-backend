import base64
import json
import logging
import typing

from aws_src_sample.utils.base_types import UserId

_LOGGER = logging.getLogger(__name__)


PathParams = typing.NewType("PathParams", dict[str, str])
QueryParams = typing.NewType("QueryParams", dict[str, str])


def get_event_body(event: dict) -> bytes:
    if "isBase64Encoded" in event and event["isBase64Encoded"]:
        return base64.b64decode(event["body"])
    else:
        return event["body"].encode("utf-8")


def get_method(event: dict) -> str:
    return event.get("requestContext", {}).get("http", {}).get("method", "UNKNOWN")


def get_path(event: dict) -> str:
    return event.get("requestContext", {}).get("http", {}).get("path", "")


def get_path_parameters(event: dict) -> dict[str, str]:
    return event.get("pathParameters", {})


def get_query_string_parameters(event: dict) -> QueryParams:
    return event.get("requestContext", {}).get("http", {}).get("queryStringParameters", {})


def get_last_evaluated_key(query_params: typing.Optional[QueryParams]) -> typing.Optional[dict[str, typing.Any]]:
    if not query_params:
        return None

    if "lastEvaluatedKey" in query_params:
        try:
            return json.loads(query_params["lastEvaluatedKey"])
        except json.JSONDecodeError:
            _LOGGER.warning("Invalid lastEvaluatedKey query param.")

    return None


def get_user_id_from_event(event: dict[str, typing.Any]) -> typing.Optional[UserId]:
    """
    Extracts user ID from Lambda event context (adapt to your authorizer).
    """
    try:
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {}).get("email")
        if user_id:
            return UserId(str(user_id))
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("principalId")
        if user_id:
            return UserId(str(user_id))
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
