#!/usr/bin/env python3
from aws_src_sample.hello_world import say_hello


def test_say_hello_1():
    ret = say_hello()
    assert ret == {"hello": "world"}
