# test/dynamodb/test_permissions_table_dal.py
import os
import typing

import boto3
import pytest
from moto import mock_aws

# Assuming your DAL and types are structured like this
from thoughtful_backend.dynamodb.user_permissions_table import (
    PermissionStatusType,
    PermissionType,
    UserPermissionsTable,
)

# If UserId and InstructorId are needed for type hints in tests:
from thoughtful_backend.utils.base_types import InstructorId, UserId

REGION = "us-east-2"
TABLE_NAME = "test-user-permissions"  # Test-specific table name

# Define constants for permission types and statuses to use in tests
# These should ideally match or be imported from where your DAL defines/uses them
# For this test, we'll redefine them for clarity if not easily importable as constants
PT_VIEW_FULL: PermissionType = "VIEW_STUDENT_DATA_FULL"
PT_VIEW_SUMMARY: PermissionType = "VIEW_STUDENT_PROGRESS_SUMMARY"
PS_ACTIVE: PermissionStatusType = "ACTIVE"
PS_INACTIVE: PermissionStatusType = "INACTIVE"
PS_PENDING: PermissionStatusType = "PENDING"


@pytest.fixture(scope="function")
def aws_credentials() -> typing.Iterator:
    """Mocks AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = REGION
    yield
    del os.environ["AWS_ACCESS_KEY_ID"]
    del os.environ["AWS_SECRET_ACCESS_KEY"]
    del os.environ["AWS_SECURITY_TOKEN"]
    del os.environ["AWS_SESSION_TOKEN"]
    del os.environ["AWS_DEFAULT_REGION"]


@pytest.fixture
def dynamodb_permissions_table(aws_credentials):  # Renamed fixture for clarity
    """Creates the mocked UserPermissions table with GSI."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        client = boto3.client("dynamodb", region_name=REGION)  # For operations like describe_table

        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "granterUserId", "KeyType": "HASH"},
                {"AttributeName": "granteePermissionTypeComposite", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "granterUserId", "AttributeType": "S"},
                {"AttributeName": "granteePermissionTypeComposite", "AttributeType": "S"},
                {"AttributeName": "granteeUserId", "AttributeType": "S"},  # GSI PK
                {"AttributeName": "granterPermissionTypeComposite", "AttributeType": "S"},  # GSI SK
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GranteePermissionsIndex",  # Use GSI_NAME from DAL
                    "KeySchema": [
                        {"AttributeName": "granteeUserId", "KeyType": "HASH"},
                        {"AttributeName": "granterPermissionTypeComposite", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    # For PAY_PER_REQUEST, ProvisionedThroughput is not specified here.
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        # Wait for table and GSI to be active (moto usually makes them active quickly)
        waiter = client.get_waiter("table_exists")
        waiter.wait(TableName=TABLE_NAME)

        # Check GSI status - may not be necessary with moto but good practice
        # desc = client.describe_table(TableName=TABLE_NAME)
        # for gsi_desc in desc['Table'].get('GlobalSecondaryIndexes', []):
        #     if gsi_desc['IndexName'] == PermissionsTableDal.GSI_NAME:
        #         gsi_waiter = # No specific GSI waiter, table waiter implies GSIs are ready
        #         break
        yield table  # Yield the table object directly if DAL instantiates its own client, or dynamodb resource


@pytest.fixture
def user_permissions_table(dynamodb_permissions_table) -> UserPermissionsTable:  # Depends on the created table
    # The DAL's __init__ does: self.client = boto3.resource("dynamodb")
    # Since moto patches boto3 globally, this will use the mocked resource.
    return UserPermissionsTable(TABLE_NAME)


# Helper to cast strings to custom types for test readability
def as_userid(s: str) -> UserId:
    return UserId(s)


def as_instructorid(s: str) -> InstructorId:
    return InstructorId(s)


# --- Test Cases ---


def test_grant_permission_success(user_permissions_table: UserPermissionsTable):
    granter = as_userid("student_grant1")
    grantee = as_instructorid("teacher_grant1")
    perm_type: PermissionType = PT_VIEW_FULL

    success = user_permissions_table.grant_permission(granter, grantee, perm_type, status=PS_ACTIVE)
    assert success is True

    # Verify item in DynamoDB
    expected_main_sk = user_permissions_table._make_main_sk(perm_type, grantee)
    expected_gsi_sk = user_permissions_table._make_gsi_sk(perm_type, granter)

    response = user_permissions_table.table.get_item(
        Key={"granterUserId": granter, "granteePermissionTypeComposite": expected_main_sk}
    )
    item = response.get("Item")
    assert item is not None
    assert item["granterUserId"] == granter
    assert item["granteeUserId"] == grantee
    assert item["granteePermissionTypeComposite"] == expected_main_sk
    assert item["granterPermissionTypeComposite"] == expected_gsi_sk
    assert item["permissionType"] == perm_type
    assert item["status"] == PS_ACTIVE
    assert "createdAt" in item
    assert "updatedAt" in item
    assert item["createdAt"] == item["updatedAt"]


def test_check_permission_exists_and_active(user_permissions_table: UserPermissionsTable):
    granter = as_userid("student_check1")
    grantee = as_instructorid("teacher_check1")
    perm_type: PermissionType = PT_VIEW_FULL
    user_permissions_table.grant_permission(granter, grantee, perm_type, status=PS_ACTIVE)

    assert user_permissions_table.check_permission(granter, grantee, perm_type) is True


def test_check_permission_exists_but_inactive(user_permissions_table: UserPermissionsTable):
    granter = as_userid("student_check2")
    grantee = as_instructorid("teacher_check2")
    perm_type: PermissionType = PT_VIEW_FULL
    user_permissions_table.grant_permission(granter, grantee, perm_type, status=PS_INACTIVE)

    assert user_permissions_table.check_permission(granter, grantee, perm_type) is False


def test_check_permission_not_exists(user_permissions_table: UserPermissionsTable):
    granter = as_userid("student_check3")
    grantee = as_instructorid("teacher_check3")
    perm_type: PermissionType = PT_VIEW_FULL

    assert user_permissions_table.check_permission(granter, grantee, perm_type) is False


def test_get_permitted_student_ids_for_teacher(user_permissions_table: UserPermissionsTable):
    teacher1 = as_instructorid("teacher_main1")
    student1 = as_userid("student_t1_s1")
    student2 = as_userid("student_t1_s2")
    student3_inactive = as_userid("student_t1_s3_inactive")
    student4_other_perm = as_userid("student_t1_s4_other_perm")
    student5_other_teacher = as_userid("student_t1_s5_other_teacher")
    teacher2 = as_instructorid("teacher_main2")

    # Grant permissions
    user_permissions_table.grant_permission(student1, teacher1, PT_VIEW_FULL, status=PS_ACTIVE)
    user_permissions_table.grant_permission(student2, teacher1, PT_VIEW_FULL, status=PS_ACTIVE)
    user_permissions_table.grant_permission(student3_inactive, teacher1, PT_VIEW_FULL, status=PS_INACTIVE)
    user_permissions_table.grant_permission(
        student4_other_perm, teacher1, PT_VIEW_SUMMARY, status=PS_ACTIVE
    )  # Different permission
    user_permissions_table.grant_permission(
        student5_other_teacher, teacher2, PT_VIEW_FULL, status=PS_ACTIVE
    )  # Different teacher

    # Test for teacher1, expecting student1 and student2
    permitted_students = user_permissions_table.get_permitted_student_ids_for_teacher(teacher1, PT_VIEW_FULL)
    assert len(permitted_students) == 2
    assert student1 in permitted_students
    assert student2 in permitted_students
    assert student3_inactive not in permitted_students
    assert student4_other_perm not in permitted_students  # Because we query for PT_VIEW_FULL

    # Test for teacher1 with different permission type
    permitted_students_summary = user_permissions_table.get_permitted_student_ids_for_teacher(teacher1, PT_VIEW_SUMMARY)
    assert len(permitted_students_summary) == 1
    assert student4_other_perm in permitted_students_summary

    # Test for teacher2
    permitted_students_t2 = user_permissions_table.get_permitted_student_ids_for_teacher(teacher2, PT_VIEW_FULL)
    assert len(permitted_students_t2) == 1
    assert student5_other_teacher in permitted_students_t2


def test_get_permitted_student_ids_for_teacher_handles_internal_pagination(
    user_permissions_table: UserPermissionsTable,
):
    teacher_id = as_instructorid("teacher_paginate_all")
    num_students = 7  # Choose a number that might cross a typical DDB page boundary if unmocked
    expected_student_ids = set()

    for i in range(num_students):
        student_id = as_userid(f"student_all_p{i}")
        expected_student_ids.add(student_id)
        # Grant permission with slightly varying timestamps to ensure sorting doesn't hide items
        # (though the DAL's internal pagination should fetch all regardless of exact order from DDB)
        # The grant_permission method will create different createdAt/updatedAt timestamps
        user_permissions_table.grant_permission(student_id, teacher_id, PT_VIEW_FULL, PS_ACTIVE)
        # Add a small delay if timestamps are too close and might affect SK uniqueness in tests
        # if num_students > 1: time.sleep(0.001)

    # Call the DAL method which should retrieve all permitted students, handling pagination internally
    all_retrieved_student_ids = user_permissions_table.get_permitted_student_ids_for_teacher(teacher_id, PT_VIEW_FULL)

    assert len(all_retrieved_student_ids) == num_students
    # Convert list to set for easy comparison, as order might not be guaranteed
    # unless the GSI SK (permissionType#granterUserId) results in a predictable order
    assert set(all_retrieved_student_ids) == expected_student_ids

    # Test with an empty result
    teacher_no_students = as_instructorid("teacher_no_students")
    no_students = user_permissions_table.get_permitted_student_ids_for_teacher(teacher_no_students, PT_VIEW_FULL)
    assert len(no_students) == 0


def test_revoke_permission(user_permissions_table: UserPermissionsTable):
    granter = as_userid("student_revoke")
    grantee = as_instructorid("teacher_revoke")
    perm_type: PermissionType = PT_VIEW_FULL

    user_permissions_table.grant_permission(granter, grantee, perm_type)
    assert user_permissions_table.check_permission(granter, grantee, perm_type) is True  # Verify it exists

    success_revoke = user_permissions_table.revoke_permission(granter, grantee, perm_type)
    assert success_revoke is True
    assert user_permissions_table.check_permission(granter, grantee, perm_type) is False  # Verify it's gone


def test_revoke_permission_not_exists(user_permissions_table: UserPermissionsTable):
    # Revoking a non-existent permission should still return True (as delete_item is idempotent)
    # or False depending on if we add a ConditionExpression for existence.
    # Current DAL's revoke_permission doesn't check for existence before delete.
    granter = as_userid("student_revoke_ne")
    grantee = as_instructorid("teacher_revoke_ne")
    perm_type: PermissionType = PT_VIEW_FULL

    success_revoke = user_permissions_table.revoke_permission(granter, grantee, perm_type)
    assert success_revoke is True  # delete_item on non-existent item doesn't error by default
