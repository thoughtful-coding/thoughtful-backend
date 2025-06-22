import logging
import typing

from aws_src_sample.secrets_manager.secrets_repository import SecretsRepository
from aws_src_sample.utils.jwt_utils import JwtWrapper

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


def _generate_iam_policy(principal_id: str, effect: str, resource: str, context: dict) -> dict:
    """
    Generates the IAM policy required by API Gateway Lambda authorizers.
    The 'resource' should be the ARN of the API Gateway endpoint.
    """
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{"Action": "execute-api:Invoke", "Effect": effect, "Resource": resource}],
        },
        "context": context,
    }


def authorizer_lambda_handler(event: dict, context: typing.Any) -> dict:
    """
    This function is a Lambda Authorizer for API Gateway. It validates the custom
    access token provided in the Authorization header.
    """
    _LOGGER.info(f"Global handler. Method: {event.get('httpMethod')}, Path: {event.get('path')}")
    _LOGGER.warning(event)

    try:
        # The token is passed as 'Bearer <token>'
        token = event["headers"]["authorization"].split(" ")[1]
    except (KeyError, IndexError):
        _LOGGER.warning("Authorization token missing or malformed.")
        # According to AWS docs, you should return "Unauthorized" for missing tokens,
        # but API Gateway v2 requires an IAM policy, so we return Deny.
        return _generate_iam_policy("user", "Deny", event["routeArn"], {})

    try:
        payload = JwtWrapper().verify_token(token, SecretsRepository())

        if payload and "sub" in payload:
            user_id = payload["sub"]
            _LOGGER.info(f"Token validated successfully for user: {user_id}")
            # The context object passes the decoded payload to the downstream lambda
            return _generate_iam_policy(user_id, "Allow", event["routeArn"], payload)
        else:
            _LOGGER.warning("Token is invalid or expired.")
            return _generate_iam_policy("user", "Deny", event["routeArn"], {})

    except Exception as e:
        _LOGGER.error(f"Error during token validation: {e}", exc_info=True)
        # In case of any error, deny access.
        return _generate_iam_policy("user", "Deny", event["routeArn"], {})
