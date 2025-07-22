import logging
import os
import typing

from aws_src_sample.cloudwatch.metrics import MetricsManager
from aws_src_sample.secrets_manager.secrets_repository import SecretsRepository
from aws_src_sample.utils.apig_utils import format_lambda_response
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


class AuthorizerLambda:
    def __init__(
        self,
        jwt_wrapper: JwtWrapper,
        secrets_repo: SecretsRepository,
        metrics_manager: MetricsManager,
    ) -> None:
        self.jwt_wrapper = jwt_wrapper
        self.secrets_repo = secrets_repo
        self.metrics_manager = metrics_manager

    def handle(self, event: dict) -> dict:
        try:
            # These context variables are provided by the Lambda runtime environment
            region = os.environ.get("AWS_REGION")
            aws_account_id = event["methodArn"].split(":")[4]
            api_id = event["requestContext"]["apiId"]
            stage = event["requestContext"]["stage"]

            # Construct a wildcard resource ARN
            resource_arn = f"arn:aws:execute-api:{region}:{aws_account_id}:{api_id}/{stage}/*"

        except (KeyError, IndexError):
            _LOGGER.error("Could not construct resource ARN from event/context.", exc_info=True)
            # If we can't build the ARN, we must deny access.
            # We provide a placeholder ARN in the deny policy.
            return _generate_iam_policy("user", "Deny", "arn:aws:execute-api:*:*:*/*/*", {})

        try:
            token = event["headers"]["authorization"].split(" ")[1]
        except (KeyError, IndexError):
            _LOGGER.warning("Authorization token missing or malformed.")
            self.metrics_manager.put_metric("AuthorizationFailure", 1)
            return _generate_iam_policy("user", "Deny", resource_arn, {})

        try:
            payload = self.jwt_wrapper.verify_token(token, self.secrets_repo)

            if payload and "sub" in payload:
                user_id = payload["sub"]
                _LOGGER.info(f"Token validated successfully for user: {user_id}")
                self.metrics_manager.put_metric("AuthorizationSuccess", 1)
                # The context object passes the decoded payload to the downstream lambda
                # The downstream lambda can access it via event['requestContext']['authorizer']
                return _generate_iam_policy(user_id, "Allow", resource_arn, payload)
            else:
                _LOGGER.warning("Token is invalid or expired.")
                self.metrics_manager.put_metric("AuthorizationFailure", 1)
                return _generate_iam_policy("user", "Deny", resource_arn, {})

        except Exception as e:
            _LOGGER.error(f"Error during token validation: {e}", exc_info=True)
            self.metrics_manager.put_metric("AuthorizationFailure", 1)
            return _generate_iam_policy("user", "Deny", resource_arn, {})


def authorizer_lambda_handler(event: dict, context: typing.Any) -> dict:
    """
    This function is a Lambda Authorizer for API Gateway. It validates the custom
    access token provided in the Authorization header.
    """
    # Format: arn:aws:execute-api:region:account-id:api-id/stage/METHOD/route
    _LOGGER.info("Auth lambda handler invoked.")
    metrics_manager = MetricsManager("ThoughtfulPython/Authentication")

    try:
        handler = AuthorizerLambda(
            metrics_manager=MetricsManager("ThoughtfulPython/Authentication"),
            jwt_wrapper=JwtWrapper(),
            secrets_repo=SecretsRepository(),
        )
        return handler.handle(event)
    except Exception as e:
        _LOGGER.critical(f"Critical error in auth_lambda_handler: {e}", exc_info=True)
        return format_lambda_response(500, {"message": "Internal Server Error in Auth Handler"})
    finally:
        metrics_manager.flush()
