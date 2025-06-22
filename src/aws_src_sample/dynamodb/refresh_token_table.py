import logging
import typing

import boto3
from botocore.exceptions import ClientError

from aws_src_sample.utils.base_types import RefreshTokenId, UserId

_LOGGER = logging.getLogger(__name__)


class RefreshTokenTable:
    def __init__(self, table_name: str):
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)

    def save_token(self, user_id: UserId, token_id: RefreshTokenId, ttl: int) -> bool:
        """Saves a refresh token to the table."""
        try:
            self.table.put_item(Item={"userId": user_id, "tokenId": token_id, "ttl": ttl})
            _LOGGER.info(f"Saved refresh token {token_id} for user {user_id}.")
            return True
        except ClientError as e:
            _LOGGER.error(f"Error saving refresh token for user {user_id}: {e}")
            return False

    def get_token(self, user_id: UserId, token_id: RefreshTokenId) -> typing.Optional[dict]:
        """Retrieves a refresh token if it exists and has not expired."""
        try:
            response = self.table.get_item(Key={"userId": user_id, "tokenId": token_id})
            return response.get("Item")
        except ClientError as e:
            _LOGGER.error(f"Error getting refresh token {token_id} for user {user_id}: {e}")
            return None

    def delete_token(self, user_id: UserId, token_id: RefreshTokenId) -> bool:
        """Deletes a specific refresh token, effectively logging out a session."""
        try:
            self.table.delete_item(Key={"userId": user_id, "tokenId": token_id})
            _LOGGER.info(f"Deleted refresh token {token_id} for user {user_id}.")
            return True
        except ClientError as e:
            _LOGGER.error(f"Error deleting refresh token {token_id} for user {user_id}: {e}")
            return False
