# src/aws_src_sample/models/permission_models.py
import typing
from datetime import datetime

from pydantic import BaseModel, Field

from thoughtful_backend.utils.base_types import InstructorId, UserId

PermissionType = typing.Literal[
    "VIEW_STUDENT_DATA_FULL",
    "VIEW_STUDENT_PROGRESS_SUMMARY",
    "VIEW_STUDENT_FINAL_LEARNING_ENTRIES",
]

PermissionStatusType = typing.Literal[
    "ACTIVE",
    "INACTIVE",
    "REVOKED",
    "PENDING",
    "EXPIRED",
]


class PermissionItemModel(BaseModel):
    # These field names are Pythonic (snake_case).
    # We'll use aliases if your DynamoDB attributes are camelCase.
    # Your DAL currently uses camelCase attributes in put_item.
    granter_user_id: UserId
    grantee_permission_type_composite: str

    # Attributes also used for GSI
    grantee_user_id: InstructorId
    granter_permission_type_composite: str

    permission_type: PermissionType
    status: PermissionStatusType
    created_at: datetime
    updated_at: datetime
