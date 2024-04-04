#!/usr/bin/env python3
from aws_src_sample.lambdas.s3_put_lambda import S3PutLambdaHandler


def test_say_hello_1():
    ret = S3PutLambdaHandler("1", "2", "3")
    assert ret.object_inputter == "1"
    assert ret.object_outputter == "2"
    assert ret.file_type_counter_table == "3"
