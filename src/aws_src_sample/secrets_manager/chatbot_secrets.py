import json
import logging
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Global cache for secrets within the Lambda execution environment
# For more advanced caching (e.g., with TTL), consider libraries or more complex logic.
_secrets_cache: Dict[str, Any] = {}


class ChatBotSecrets:
    """
    A repository class to abstract interactions with AWS Secrets Manager,
    including caching of secrets.
    """

    def __init__(self, region_name: Optional[str] = None, secretsmanager_client=None):
        """
        Initializes the Secrets Manager client.
        :param region_name: Optional AWS region name. Defaults to region from environment.
        :param secretsmanager_client: Optional pre-configured boto3 Secrets Manager client for testing.
        """
        if secretsmanager_client:
            self.client = secretsmanager_client
        else:
            # If region_name is not provided, boto3 will use the default region
            # configured for the Lambda execution environment.
            self.client = boto3.client("secretsmanager", region_name=region_name)
        logger.info(f"SecretsRepository initialized. Region: {region_name or 'default'}")

    def _get_raw_secret_string(self, secret_name: str) -> Optional[str]:
        """
        Retrieves the raw secret string from Secrets Manager or cache.
        Caches the secret string upon first successful retrieval.
        """
        if secret_name in _secrets_cache:
            logger.debug(f"Returning secret '{secret_name}' from cache.")
            return _secrets_cache[secret_name]

        try:
            logger.info(f"Fetching secret '{secret_name}' from AWS Secrets Manager.")
            get_secret_value_response = self.client.get_secret_value(SecretId=secret_name)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "ResourceNotFoundException":
                logger.error(f"Secret '{secret_name}' not found in AWS Secrets Manager.")
            elif error_code == "InvalidRequestException":
                logger.error(f"Invalid request for secret '{secret_name}': {e}")
            elif error_code == "DecryptionFailure":
                logger.error(f"Failed to decrypt secret '{secret_name}': {e}")
            else:
                logger.error(f"Error fetching secret '{secret_name}': {e}", exc_info=True)
            return None  # Or re-raise a custom exception

        # Decrypts secret using the associated KMS key.
        # Secrets Manager Python SDK uses the 'SecretString' field for string secrets.
        # 'SecretBinary' is for binary secrets.
        if "SecretString" in get_secret_value_response:
            secret_value = get_secret_value_response["SecretString"]
            _secrets_cache[secret_name] = secret_value  # Cache the raw string
            return secret_value
        else:
            # Handle binary secrets if necessary, though API keys are typically strings.
            # For this use case, we expect SecretString.
            logger.warning(f"Secret '{secret_name}' found but is in binary format, not SecretString.")
            return None

    def get_secret_value(self, secret_name: str, json_key: Optional[str] = None) -> Optional[str]:
        """
        Retrieves a secret value from AWS Secrets Manager.
        If json_key is provided, the secret is assumed to be a JSON string,
        and the value associated with json_key is returned.
        Otherwise, the entire secret string is returned.

        :param secret_name: The name or ARN of the secret in AWS Secrets Manager.
        :param json_key: Optional. If the secret is a JSON string, this is the key
                         for the desired value within the JSON.
        :return: The secret value as a string, or None if not found or an error occurs.
        """
        raw_secret_string = self._get_raw_secret_string(secret_name)

        if raw_secret_string is None:
            return None

        if json_key:
            try:
                secret_dict = json.loads(raw_secret_string)
                if not isinstance(secret_dict, dict):
                    logger.error(
                        f"Secret '{secret_name}' is not a JSON object, but a json_key '{json_key}' was requested."
                    )
                    return None

                value = secret_dict.get(json_key)
                if value is None:
                    logger.warning(f"Key '{json_key}' not found in JSON secret '{secret_name}'.")
                    return None
                if not isinstance(value, str):
                    logger.warning(
                        f"Value for key '{json_key}' in secret '{secret_name}' is not a string. Type: {type(value)}"
                    )
                    # Depending on strictness, you might convert or return None.
                    # For API keys, we expect a string.
                    return str(value)  # Attempt conversion
                return value
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON for secret '{secret_name}' when expecting key '{json_key}'.")
                return None
        else:
            # If no json_key, return the entire secret string
            return raw_secret_string
