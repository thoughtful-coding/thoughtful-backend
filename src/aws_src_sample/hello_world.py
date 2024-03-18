#!/usr/bin/env python3


def say_hello(env: dict, context) -> dict[str, str]:
    print("Hello!")
    return {"hello": "world"}
