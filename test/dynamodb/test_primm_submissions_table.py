import os
import random
import typing
from datetime import datetime, timedelta, timezone

import boto3
import pytest
from moto import mock_aws

from thoughtful_backend.dynamodb.primm_submissions_table import PrimmSubmissionsTable
from thoughtful_backend.models.learning_entry_models import AssessmentLevel
from thoughtful_backend.models.primm_feedback_models import (
    PrimmEvaluationRequestModel,
    PrimmEvaluationResponseModel,
)
from thoughtful_backend.utils.base_types import UserId

REGION = "us-west-1"
TABLE_NAME = "PrimmSubmissionsTable"


@pytest.fixture
def dynamodb_table_resource(aws_credentials) -> typing.Iterable:
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "userId", "KeyType": "HASH"},  # PK
                {"AttributeName": "submissionCompositeKey", "KeyType": "RANGE"},  # SK
            ],
            AttributeDefinitions=[
                {"AttributeName": "userId", "AttributeType": "S"},
                {"AttributeName": "submissionCompositeKey", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield dynamodb


@pytest.fixture
def primm_submissions_table_instance(dynamodb_table_resource) -> PrimmSubmissionsTable:
    return PrimmSubmissionsTable(TABLE_NAME)


# Helper function to create sample data
def _create_sample_request_data(lesson_id="l1", section_id="s1", example_id="ex1") -> PrimmEvaluationRequestModel:
    return PrimmEvaluationRequestModel(
        lessonId=lesson_id,
        sectionId=section_id,
        primmExampleId=example_id,
        codeSnippet="print('hello')",
        userPredictionPromptText="What happens?",
        userPredictionText="It prints hello.",
        userPredictionConfidence=3,
        actualOutputSummary="hello",
        userExplanationText="It worked as expected.",
    )


def _create_sample_evaluation_data(
    pred_assessment: AssessmentLevel = "achieves",
    expl_assessment: AssessmentLevel = "mostly",
    comment: str = "Good job!",
) -> PrimmEvaluationResponseModel:
    return PrimmEvaluationResponseModel(
        aiPredictionAssessment=pred_assessment,
        aiExplanationAssessment=expl_assessment,
        aiOverallComment=comment,
    )


def test_save_submission_successful(primm_submissions_table_instance: PrimmSubmissionsTable):
    user_id = UserId("student1")
    req_data = _create_sample_request_data()
    eval_data = _create_sample_evaluation_data()
    timestamp_iso = datetime.now(timezone.utc).isoformat()

    success = primm_submissions_table_instance.save_submission(user_id, req_data, eval_data, timestamp_iso)
    assert success is True

    # Verify item in DynamoDB
    sk = primm_submissions_table_instance._make_submission_sk(
        req_data.lesson_id, req_data.section_id, req_data.primm_example_id, timestamp_iso
    )
    response = primm_submissions_table_instance.table.get_item(Key={"userId": user_id, "submissionCompositeKey": sk})
    item = response.get("Item")

    assert item is not None
    assert item["userId"] == user_id
    assert item["lessonId"] == req_data.lesson_id
    assert item["sectionId"] == req_data.section_id
    assert item["primmExampleId"] == req_data.primm_example_id
    assert item["timestampIso"] == timestamp_iso
    assert item["codeSnippet"] == req_data.code_snippet
    assert item["userPredictionText"] == req_data.user_prediction_text
    assert item["userPredictionConfidence"] == req_data.user_prediction_confidence
    assert item["userExplanationText"] == req_data.user_explanation_text
    assert item["aiPredictionAssessment"] == eval_data.ai_prediction_assessment
    assert item["aiExplanationAssessment"] == eval_data.ai_explanation_assessment
    assert item["aiOverallComment"] == eval_data.ai_overall_comment
    assert "createdAt" in item


def test_get_submissions_no_submissions_for_user(primm_submissions_table_instance: PrimmSubmissionsTable):
    submissions, next_key = primm_submissions_table_instance.get_submissions_by_student(UserId("non_existent_user"))
    assert len(submissions) == 0
    assert next_key is None


def test_get_submissions_for_student_multiple_entries(primm_submissions_table_instance: PrimmSubmissionsTable):
    user_id = UserId("student_multi")
    req1 = _create_sample_request_data("l1", "s1", "ex1")
    eval1 = _create_sample_evaluation_data("achieves", "mostly", "Good")
    ts1 = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    primm_submissions_table_instance.save_submission(user_id, req1, eval1, ts1)

    req2 = _create_sample_request_data("l1", "s1", "ex2")  # Different example
    eval2 = _create_sample_evaluation_data("developing", "insufficient", "Needs work")
    ts2 = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    primm_submissions_table_instance.save_submission(user_id, req2, eval2, ts2)

    req3 = _create_sample_request_data("l2", "s1", "ex1")  # Different lesson
    eval3 = _create_sample_evaluation_data("mostly")
    ts3 = datetime.now(timezone.utc).isoformat()
    primm_submissions_table_instance.save_submission(user_id, req3, eval3, ts3)

    # Get all for user (should be newest first due to ScanIndexForward=False and timestamp in SK)
    submissions, _ = primm_submissions_table_instance.get_submissions_by_student(user_id)
    assert len(submissions) == 3
    assert submissions[0].primmExampleId == "ex1"  # req3
    assert submissions[0].lessonId == "l2"
    assert submissions[1].primmExampleId == "ex2"  # req2
    assert submissions[2].primmExampleId == "ex1"  # req1
    assert submissions[2].lessonId == "l1"

    # Filter by lesson
    submissions_l1, _ = primm_submissions_table_instance.get_submissions_by_student(user_id, lesson_id_filter="l1")
    assert len(submissions_l1) == 2
    assert submissions_l1[0].primmExampleId == "ex2"  # req2
    assert submissions_l1[1].primmExampleId == "ex1"  # req1

    # Filter by lesson and section
    submissions_l1_s1, _ = primm_submissions_table_instance.get_submissions_by_student(
        user_id, lesson_id_filter="l1", section_id_filter="s1"
    )
    assert len(submissions_l1_s1) == 2

    # Filter by lesson, section, and example
    submissions_l1_s1_ex2, _ = primm_submissions_table_instance.get_submissions_by_student(
        user_id, lesson_id_filter="l1", section_id_filter="s1", primm_example_id_filter="ex2"
    )
    assert len(submissions_l1_s1_ex2) == 1
    assert submissions_l1_s1_ex2[0].primmExampleId == "ex2"


def test_get_submissions_pagination(primm_submissions_table_instance: PrimmSubmissionsTable):
    """
    Note: There might a bug in moto in that it doesn't model `ScanIndexForward` properly
    """
    user_id = UserId("student_paginate")
    order = [x for x in range(5)]
    random.shuffle(order)
    for i in order:
        req = _create_sample_request_data("l1", "s1", f"ex{i}")
        eval_data = _create_sample_evaluation_data()
        # Save with slightly different timestamps to ensure order
        ts = (datetime.now(timezone.utc) - timedelta(minutes=i * 10)).isoformat()
        primm_submissions_table_instance.save_submission(user_id, req, eval_data, ts)

    # Get first page
    page1_items, last_key1 = primm_submissions_table_instance.get_submissions_by_student(user_id, limit=2)
    assert len(page1_items) == 2
    assert last_key1 is not None
    assert page1_items[0].primmExampleId == "ex4"  # Newest (smallest timestamp offset)
    assert page1_items[1].primmExampleId == "ex3"

    # Get second page
    page2_items, last_key2 = primm_submissions_table_instance.get_submissions_by_student(
        user_id, limit=2, last_evaluated_key=last_key1
    )
    assert len(page2_items) == 2
    assert last_key2 is not None
    assert page2_items[0].primmExampleId == "ex2"
    assert page2_items[1].primmExampleId == "ex1"

    # Get third page
    page3_items, last_key3 = primm_submissions_table_instance.get_submissions_by_student(
        user_id, limit=2, last_evaluated_key=last_key2
    )
    assert len(page3_items) == 1
    assert last_key3 is None  # No more items
    assert page3_items[0].primmExampleId == "ex0"
