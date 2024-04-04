#!/usr/bin/env python3
import os
from unittest.mock import Mock, patch

from aws_src_sample.lambdas.s3_put_lambda import S3PutLambdaHandler


def test_s3_put_lambda_handler_1():
    ret = S3PutLambdaHandler("1", "2", "3")
    assert ret.object_inputter == "1"
    assert ret.object_outputter == "2"
    assert ret.file_type_counter_table == "3"


@patch.dict(os.environ, {"OUTPUT_BUCKET_NAME": "output-bucket"})
def test_s3_put_lambda_handler_handle_1():
    event = {"Records": [{"s3": {"bucket": {"name": "example-bucket"}, "object": {"key": "in.txt"}}}]}

    inputter = Mock()
    inputter.get.return_value = b"test"

    outputter = Mock()

    file_counter_table = Mock()

    ret = S3PutLambdaHandler(inputter, outputter, file_counter_table)
    ret.handle(event)

    cal = outputter.put.call_args_list
    assert len(cal) == 1
    assert cal[0][1]["bucket"] == "output-bucket"
    assert cal[0][1]["key"] == "in.txt"
    assert cal[0][1]["contents"] == b"hi: test"
