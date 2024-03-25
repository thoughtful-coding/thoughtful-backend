#!/usr/bin/env python3
from aws_src_sample.hello_world import LambdaHandler


def test_say_hello_1():
    ret = LambdaHandler("1", "2")
    assert ret.object_inputter == "1"
    assert ret.object_outputter == "2"