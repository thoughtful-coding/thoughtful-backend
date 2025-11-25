import typing

import pydantic

from thoughtful_backend.utils.base_types import IsoTimestamp, UserId


class UserProfileModel(pydantic.BaseModel):
    """
    Pydantic model representing a user profile stored in DynamoDB.
    Contains user-level metadata such as initialization status, timestamps, and preferences.
    """

    userId: UserId = pydantic.Field(description="Partition Key - user's email address")
    initialized: bool = pydantic.Field(
        default=False, description="Whether user has completed first-login initialization"
    )
    createdAt: typing.Optional[IsoTimestamp] = pydantic.Field(
        default=None, description="ISO8601 timestamp of when user first logged in"
    )
    lastLoginAt: typing.Optional[IsoTimestamp] = pydantic.Field(
        default=None, description="ISO8601 timestamp of most recent login"
    )
    preferences: typing.Optional[dict[str, typing.Any]] = pydantic.Field(
        default=None, description="User preferences (theme, language, etc.)"
    )
    metadata: typing.Optional[dict[str, typing.Any]] = pydantic.Field(
        default=None, description="Arbitrary metadata for future use"
    )
