#!/usr/bin/env python3
from unittest.mock import Mock

from thoughtful_backend.lambdas.authorizer_lambda import AuthorizerLambda
from thoughtful_backend.utils.base_types import UserId
from thoughtful_backend.utils.jwt_utils import JwtWrapper

MOCK_USER_ID = UserId("12345_google_user_sub")


def create_authorizer_lambda(
    secrets_table=Mock(),
    jwt_wrapper=JwtWrapper(),
    metrics_manager=Mock(),
) -> AuthorizerLambda:
    authorizer_handler = AuthorizerLambda(
        secrets_table=secrets_table,
        jwt_wrapper=jwt_wrapper,
        metrics_manager=metrics_manager,
    )
    assert authorizer_handler.secrets_table == secrets_table
    assert authorizer_handler.jwt_wrapper == jwt_wrapper
    assert authorizer_handler.metrics_manager == metrics_manager
    return authorizer_handler


def test_authorizer_lambda_handler_1() -> None:
    mock_secrets_table = Mock()
    mock_secrets_table.get_jwt_secret_key.return_value = "hey"

    refresh_token, _, _ = JwtWrapper().create_refresh_token(MOCK_USER_ID, mock_secrets_table)

    event = {
        "version": "1.0",
        "type": "REQUEST",
        "methodArn": "arn:aws:execute-api:us-west-1:598791268315:k3txasuuei/$default/PUT/progress",
        "identitySource": f"Bearer {refresh_token}",
        "authorizationToken": f"Bearer {refresh_token}",
        "resource": "",
        "path": "/progress",
        "httpMethod": "PUT",
        "headers": {
            "authorization": f"Bearer {refresh_token}",
        },
        "queryStringParameters": {},
        "requestContext": {
            "apiId": "k3txasuuei",
            "domainName": "k3txasuuei.execute-api.us-west-1.amazonaws.com",
            "domainPrefix": "k3txasuuei",
            "extendedRequestId": "MlOm4gNjiYcEMbg=",
            "httpMethod": "PUT",
            "path": "/progress",
            "protocol": "HTTP/1.1",
            "requestId": "MlOm4gNjiYcEMbg=",
            "requestTime": "22/Jun/2025:19:48:59 +0000",
            "requestTimeEpoch": 1750621739676,
            "resourceId": "PUT /progress",
            "resourcePath": "/progress",
            "stage": "$default",
        },
    }

    authorizer_lambda = create_authorizer_lambda(secrets_table=mock_secrets_table)
    result = authorizer_lambda.handle(event)
    assert result["principalId"] == "12345_google_user_sub"
    assert result["policyDocument"]["Statement"][0]["Action"] == "execute-api:Invoke"
    assert (
        result["policyDocument"]["Statement"][0]["Resource"]
        == "arn:aws:execute-api:us-west-1:598791268315:k3txasuuei/$default/*"
    )
