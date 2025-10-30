import base64
import json
import logging
import re
import typing

from thoughtful_backend.utils.base_types import UserId

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
    return event.get("queryStringParameters", {})


def get_pagination_limit(query_params: typing.Optional[QueryParams]) -> int:
    limit = 50
    if query_params and "limit" in query_params:
        try:
            limit = int(query_params["limit"])
        except (ValueError, TypeError):
            _LOGGER.warning(f"Invalid limit query param: {query_params.get('limit')}")
    return limit


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
    Extracts user ID from the Lambda event context provided by the custom Lambda Authorizer.
    The authorizer places the decoded JWT payload into the 'lambda' key.
    """
    try:
        # Correct path for a Lambda Authorizer on an HTTP API
        user_id = event.get("requestContext", {}).get("authorizer", {}).get("lambda", {}).get("sub")
        if user_id:
            return UserId(str(user_id))

        _LOGGER.warning("User ID ('sub') not found in authorizer's lambda context.")
        return None
    except Exception as e:
        _LOGGER.error("Error extracting user_id from event: %s", str(e))
        return None


def get_allowed_origin(event: dict[str, typing.Any]) -> str:
    """
    Validates the Origin header against allowed patterns and returns it if valid.

    Allowed Origins:
    - localhost/127.0.0.1 (any port) - for local development
    - *.github.io - for GitHub Pages deployments (expected fork hosting)

    :returns: The origin if valid, otherwise "null" (which causes browser to deny the response)
    """
    origin = event.get("headers", {}).get("origin", "")

    # No origin header present (e.g., curl/Postman testing, direct API calls)
    if not origin:
        return "*"

    # Allow localhost for development (any port)
    if origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:"):
        return origin

    # Allow GitHub Pages (expected hosting for forks)
    allowed_patterns = [r"^https://.*\.github\.io$"]
    for pattern in allowed_patterns:
        if re.match(pattern, origin):
            return origin

    # Origin doesn't match allowed patterns - deny by returning "null"
    _LOGGER.warning(f"Origin not in allowed patterns: {origin}")
    return "null"


def format_lambda_response(
    status_code: int,
    body: typing.Any,
    *,
    event: typing.Optional[dict[str, typing.Any]] = None,
    additional_headers: typing.Optional[dict[str, str]] = None,
) -> dict[str, typing.Any]:
    """
    Formats API Gateway proxy responses with CORS headers.
    """
    # Determine allowed origin based on request origin
    allowed_origin = get_allowed_origin(event) if event else "*"

    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": allowed_origin,
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
