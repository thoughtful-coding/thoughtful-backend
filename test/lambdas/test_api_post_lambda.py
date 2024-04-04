#!/usr/bin/env python3
import json
import os
from unittest.mock import Mock, patch

from aws_src_sample.lambdas.apig_post_lambda import APIGPostLambdaHandler


def test_apig_post_lambda_handler_1():
    ret = APIGPostLambdaHandler("1", "2")
    assert ret.object_outputter == "1"
    assert ret.file_type_counter_table == "2"


@patch.dict(os.environ, {"OUTPUT_BUCKET_NAME": "output-bucket", "REGION": "us-east-2"})
def test_apig_post_lambda_handler_handle_1():
    event = {"body": "8, 8, 8\n9, 9, 8"}

    outputter = Mock()

    file_counter_table = Mock()

    ret = APIGPostLambdaHandler(outputter, file_counter_table)
    response = ret.handle(event)

    assert response["statusCode"] == 201
    assert json.loads(response["body"])["location"].startswith(
        "https://output-bucket.s3.us-east-2.amazonaws.com/transform_"
    )

    cal = outputter.put.call_args_list
    assert len(cal) == 1
    assert cal[0][1]["bucket"] == "output-bucket"
    assert cal[0][1]["key"].startswith("transform_")
    assert cal[0][1]["contents"].startswith(b"numpy-stl (3.1.1)")
