import logging
import typing
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from utils.base_types import InstructorId, UserId

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


PermissionType = typing.Literal[
    "VIEW_STUDENT_DATA_FULL",
    "VIEW_STUDENT_PROGRESS_SUMMARY",
    "VIEW_STUDENT_FINAL_LEARNING_ENTRIES",
]


PermissionStatusType = typing.Literal[
    "ACTIVE",
    "INACTIVE",
    "REVOKED",
    "PENDING",  # For future friend request system
    "EXPIRED",  # For future time-limited permissions
]


class UserPermissionsTable:
    """
    Data Abstraction Layer for interacting with the UserPermissions DynamoDB table.
    Table Schema:
      - PK: granterUserId (e.g., USER#studentId)
      - SK: permissionType#granteeUserId (e.g., VIEW_ALL_STUDENT_DATA#USER#teacherId)
    GSI ('GranteePermissionsIndex'):
      - GSI_PK: granteeUserId (e.g., USER#teacherId)
      - GSI_SK: permissionType#granterUserId (e.g., VIEW_ALL_STUDENT_DATA#USER#studentId)
    """

    GSI_NAME = "GranteePermissionsIndex"

    def __init__(self, table_name: str):
        self.client = boto3.resource("dynamodb")
        self.table = self.client.Table(table_name)

    def _make_main_sk(self, permission_type: PermissionType, grantee_user_id: InstructorId) -> str:
        return f"{permission_type}#{grantee_user_id}"

    def _make_gsi_sk(self, permission_type: PermissionType, granter_user_id: UserId) -> str:
        return f"{permission_type}#{granter_user_id}"

    def grant_permission(
        self,
        granter_user_id: UserId,  # The user whose data will be accessed
        grantee_user_id: InstructorId,  # The user receiving the permission (e.g., teacher)
        permission_type: PermissionType,
        status: PermissionStatusType = "ACTIVE",
        # GSI attributes must also be written to the main item
        # The main table SK uses permissionType and grantee_user_id
        # The GSI SK uses permissionType and granter_user_id
        # Both grantee_user_id and granter_user_id are needed as top-level attributes for GSI PKs
    ) -> bool:
        """
        Grants a permission from a granter to a grantee.
        This effectively creates or updates a permission item.
        """
        main_sk_value = self._make_main_sk(permission_type, grantee_user_id)
        gsi_sk_value = self._make_gsi_sk(permission_type, granter_user_id)
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            self.table.put_item(
                Item={
                    "granterUserId": granter_user_id,
                    "granteePermissionTypeComposite": main_sk_value,  # Main table SK attribute name from CDK
                    # Attributes needed for GSI and general info:
                    "granteeUserId": grantee_user_id,  # GSI PK attribute name from CDK
                    "granterPermissionTypeComposite": gsi_sk_value,  # GSI SK attribute name from CDK
                    "permissionType": permission_type,
                    "status": status,
                    "createdAt": timestamp,
                    "updatedAt": timestamp,
                }
            )
            _LOGGER.info(f"Permission '{permission_type}' granted by '{granter_user_id}' to '{grantee_user_id}'.")
            return True
        except ClientError as e:
            _LOGGER.error(
                f"Error granting permission by '{granter_user_id}' to '{grantee_user_id}': {e.response['Error']['Message']}"
            )
            return False

    def check_permission(
        self,
        granter_user_id: UserId,  # The student whose data is being accessed
        grantee_user_id: InstructorId,  # The teacher attempting access
        permission_type: PermissionType,
    ) -> bool:
        """
        Checks if an active permission exists for the grantee to access the granter's data
        for a specific permission type.
        """
        main_sk_value = self._make_main_sk(permission_type, grantee_user_id)
        try:
            response = self.table.get_item(
                Key={"granterUserId": granter_user_id, "granteePermissionTypeComposite": main_sk_value}
            )
            item = response.get("Item")
            if item and item.get("status") == "ACTIVE":
                _LOGGER.debug(
                    f"Active permission '{permission_type}' found for grantee '{grantee_user_id}' on granter '{granter_user_id}'."
                )
                return True
            _LOGGER.debug(
                f"No active permission '{permission_type}' for grantee '{grantee_user_id}' on granter '{granter_user_id}'. Item: {item}"
            )
            return False
        except ClientError as e:
            _LOGGER.error(
                f"Error checking permission for grantee '{grantee_user_id}' on granter '{granter_user_id}': {e.response['Error']['Message']}"
            )
            return False  # Fail closed on error

    def get_permitted_student_ids_for_teacher(
        self,
        teacher_user_id: InstructorId,
        permission_type: PermissionType = "VIEW_STUDENT_DATA_FULL",
    ) -> list[UserId]:
        """
        Retrieves a list of student (granter) IDs for whom the given teacher (grantee)
        has an active specified permission. Uses the GSI.
        """
        student_ids: list[UserId] = []
        try:
            # Query the GSI where GSI_PK is granteeUserId and GSI_SK begins with permissionType
            # The GSI SK was defined as 'permissionType#granterUserId'
            # The actual attribute name for GSI SK in the table is 'granterPermissionTypeComposite'
            response = self.table.query(
                IndexName=self.GSI_NAME,
                KeyConditionExpression=Key("granteeUserId").eq(teacher_user_id)
                & Key("granterPermissionTypeComposite").begins_with(f"{permission_type}#"),
                FilterExpression=Attr("status").eq("ACTIVE"),
            )
            items = response.get("Items", [])
            for item in items:
                # The granterUserId is the student's ID. It's the PK of the main table and also projected to GSI.
                # Or, if not projected, it can be extracted from the GSI SK 'granterPermissionTypeComposite'
                if "granterUserId" in item:  # If granterUserId is projected
                    student_ids.append(item["granterUserId"])
                else:  # Fallback to parse from GSI SK if 'granterUserId' wasn't explicitly projected
                    gsi_sk_parts = item.get("granterPermissionTypeComposite", "").split("#", 1)
                    if len(gsi_sk_parts) == 2:
                        student_ids.append(gsi_sk_parts[1])  # Assumes format PERMISSION_TYPE#GRANTER_ID

            # Handle pagination if necessary
            while "LastEvaluatedKey" in response:
                response = self.table.query(
                    IndexName=self.GSI_NAME,
                    KeyConditionExpression=Key("granteeUserId").eq(teacher_user_id)
                    & Key("granterPermissionTypeComposite").begins_with(f"{permission_type}#"),
                    FilterExpression=Attr("status").eq("ACTIVE"),
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                items = response.get("Items", [])
                for item in items:
                    if "granterUserId" in item:
                        student_ids.append(item["granterUserId"])
                    else:
                        gsi_sk_parts = item.get("granterPermissionTypeComposite", "").split("#", 1)
                        if len(gsi_sk_parts) == 2:
                            student_ids.append(gsi_sk_parts[1])
                _LOGGER.info(
                    f"Fetched {len(student_ids)} permitted student IDs for teacher {teacher_user_id} with permission {permission_type}."
                )

        except ClientError as e:
            _LOGGER.error(
                f"Error fetching permitted students for teacher '{teacher_user_id}': {e.response['Error']['Message']}"
            )
            # Return empty list or raise, depending on desired error handling
        return list(set(student_ids))  # Ensure uniqueness

    def revoke_permission(
        self,
        granter_user_id: UserId,
        grantee_user_id: InstructorId,
        permission_type: PermissionType,
    ) -> bool:
        """Revokes a specific permission."""
        main_sk_value = self._make_main_sk(permission_type, grantee_user_id)
        try:
            self.table.delete_item(
                Key={"granterUserId": granter_user_id, "granteePermissionTypeComposite": main_sk_value}
                # Optionally, add a ConditionExpression to ensure the item exists before deleting
            )
            _LOGGER.info(
                f"Permission '{permission_type}' revoked for grantee '{grantee_user_id}' from granter '{granter_user_id}'."
            )
            return True
        except ClientError as e:
            _LOGGER.error(
                f"Error revoking permission for grantee '{grantee_user_id}' from granter '{granter_user_id}': {e.response['Error']['Message']}"
            )
            return False
