import logging
import typing

import boto3
from botocore.exceptions import ClientError

_LOGGER = logging.getLogger(__name__)


class SecretsTable:
    """
    DynamoDB table for storing application secrets (read-only with caching).

    Schema:
        - PK: secretKey (String) - e.g., "JWT_SECRET", "CHATBOT_API_KEY"
        - Attributes:
            - secretValue (String) - The actual secret value
            - description (String) - Optional description
            - updatedAt (String) - ISO timestamp of last update

    Note: Secrets are populated via infrastructure/migration scripts, not through this class.
    Secrets are cached in memory for the lifetime of the Lambda container.
    """

    _cache: typing.ClassVar[dict[str, str]] = {}

    def __init__(self, table_name: str):
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)

    def __get_secret(self, secret_key: str) -> str:
        """
        Retrieve a secret value from the table or cache.

        Secrets are cached in memory for the lifetime of the Lambda container
        to avoid repeated DynamoDB calls.

        Args:
            secret_key: The key identifying the secret (e.g., "JWT_SECRET")

        Returns:
            The secret value

        Raises:
            KeyError: If the secret is not found in the table
        """
        if secret_key in self._cache:
            _LOGGER.debug(f"Returning secret '{secret_key}' from cache.")
            return self._cache[secret_key]

        try:
            _LOGGER.info(f"Fetching secret '{secret_key}' from DynamoDB.")
            response = self.table.get_item(Key={"secretKey": secret_key})
            item = response.get("Item")
            if not item:
                _LOGGER.error(f"Secret not found: {secret_key}")
                raise KeyError(f"Secret '{secret_key}' not found in secrets table")

            secret_value = item.get("secretValue")
            if not secret_value:
                _LOGGER.error(f"Secret '{secret_key}' has no secretValue field")
                raise KeyError(f"Secret '{secret_key}' has no value in secrets table")

            self._cache[secret_key] = secret_value
            return secret_value
        except ClientError as e:
            _LOGGER.error(f"Error retrieving secret {secret_key}: {e}")
            raise KeyError(f"Failed to retrieve secret '{secret_key}' from DynamoDB") from e

    def get_chatbot_api_key(self) -> str:
        """
        Gets the ChatBot API key from DynamoDB.

        Returns:
            The ChatBot API key

        Raises:
            KeyError: If the secret is not found
        """
        return self.__get_secret("CHATBOT_API_KEY")

    def get_jwt_secret_key(self) -> str:
        """
        Gets the JWT secret key from DynamoDB.

        Returns:
            The JWT secret key

        Raises:
            KeyError: If the secret is not found
        """
        return self.__get_secret("JWT_SECRET")
