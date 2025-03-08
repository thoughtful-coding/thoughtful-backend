#!/usr/bin/env python3
import json
import os
from unittest.mock import Mock, patch

from aws_src_sample.lambdas.apig_post_lambda import APIGPostLambdaHandler

BASE64_POST = """77u/OCw4LjgsOS4yLDkuNCw5LjcsMTAuMSwxMC41LDExLDExLjYsMTIuMiwxMy4yLDEzLjcsMTQuNSwxNS41LDE2LjEsMTcsMTcuNywxOC4zLDE4LjcsMTkuNCwyMC4xLDIwLjYsMjAuOSwyMS4yLDIxLjYsMjEuNSwyMS44LDIxLjkNCjcuNSw4LjEsOC40LDguOCw5LjIsOS41LDEwLDEwLjUsMTEsMTEuOCwxMi41LDEzLDEzLjksMTQuNiwxNS4yLDE2LjEsMTYuNywxNy4yLDE3LjgsMTguNCwxOC44LDE5LjQsMTkuOCwyMCwyMC41LDIwLjYsMjAuNSwxOS42DQo3LjQsNy42LDcuNiw4LjMsOC42LDguNyw5LjUsMTAsMTAuMywxMS4zLDExLjksMTIsMTMuMywxNCwxMy45LDE1LjQsMTYsMTUuOCwxNy4xLDE3LjYsMTcuMywxOC41LDE4LjksMTguNCwxOS42LDIwLjEsMjAuMSwxOS44DQo3LjEsNy40LDcuNiw4LDguMyw4LjcsOS4zLDkuOCwxMC40LDExLjIsMTEuOSwxMi42LDEzLjUsMTQuMiwxNC43LDE1LjYsMTYuMiwxNi41LDE3LjEsMTcuNiwxNy45LDE4LjUsMTguOSwxOS4xLDE5LjUsMTkuOSwyMCwxOS45DQo2LjksNy4zLDcuNSw3LjgsOC4xLDguNCw5LDkuNiwxMC40LDExLjIsMTIsMTIuOSwxMy44LDE0LjUsMTUuMywxNi4xLDE2LjUsMTYuOSwxNy4zLDE3LjgsMTguMywxOC43LDE5LjEsMTkuNCwxOS42LDE5LjksMjAuMSwyMA0KNy40LDcuMyw3LjQsNy42LDcuNyw4LDguNiw5LjMsMTAuMiwxMS4yLDEyLjEsMTMuMSwxNC4zLDE0LjksMTUuOCwxNywxNywxNy4yLDE3LjIsMTguMiwxOC43LDE4LjgsMTkuNiwxOS44LDE5LjYsMjAuMiwyMC4zLDIwLjQNCjcuMiw3LjEsNyw3LDcuMSw3LjQsOCw4LjksMTAsMTEsMTIsMTMuMSwxNC4xLDE1LDE1LjksMTYuNywxNy4yLDE3LjcsMTguMiwxOC45LDE5LjUsMjAsMjAuNSwyMC43LDIwLjcsMjAuOCwyMC43LDIwLjYNCjYuOSw2LjksNi43LDYuNSw2LjIsNi4zLDcuMiw4LjQsOS43LDEwLjksMTIsMTMuMSwxNC4xLDE1LjEsMTUuOSwxNi44LDE3LjUsMTguMiwxOC45LDE5LjcsMjAuNSwyMS4yLDIxLjgsMjEuOSwyMS43LDIxLjUsMjEuMSwyMC44DQo3LDYuNyw2LjQsNS45LDUuMSw0LjQsNi4xLDcuOSw5LjQsMTAuOCwxMiwxMy4xLDE0LjIsMTUuMiwxNi4xLDE3LDE3LjgsMTguNywxOS42LDIwLjUsMjEuNiwyMi43LDIzLjQsMjMuMywyMi45LDIyLjIsMjEuNiwyMS4xDQo2LjksNi43LDYuMyw1LjUsNCwwLDUsNy41LDkuMywxMC44LDEyLDEzLjIsMTQuNSwxNS4zLDE2LjIsMTcuMywxOC4xLDE5LjEsMjAuMywyMS4yLDIyLjYsMjQuNSwyNS44LDI0LjksMjQuNCwyMi45LDIxLjksMjEuMQ0KNyw2LjgsNi41LDYsNS4yLDQuNSw2LjIsOCw5LjUsMTAuOSwxMi4xLDEzLjIsMTQuMywxNS4zLDE2LjMsMTcuMiwxOC4yLDE5LjIsMjAuMywyMS41LDIzLjEsMjUuNiwzMC41LDI2LjMsMjQuNSwyMy4xLDIyLDIxDQo3LDcsNi45LDYuNyw2LjUsNi42LDcuNSw4LjcsOS45LDExLjEsMTIuMiwxMy4zLDE0LjMsMTUuMywxNi4zLDE3LjIsMTguMiwxOS4xLDIwLjIsMjEuNCwyMi44LDI0LjQsMjYsMjUuMSwyNC4xLDIzLDIyLDIxLjENCjcuMiw3LjMsNy4zLDcuNCw3LjQsNy44LDguNSw5LjMsMTAuMywxMS4zLDEyLjMsMTMuNCwxNC40LDE1LjMsMTYuMywxNy4zLDE4LjEsMTksMTkuOSwyMSwyMi4xLDIzLjIsMjQuMSwyNC4xLDI0LDIyLjcsMjEuNywyMC44DQo3LjQsNy42LDcuNyw3LjksOC4xLDguNSw5LjEsOS44LDEwLjcsMTEuNiwxMi41LDEzLjUsMTQuNCwxNS40LDE2LjMsMTcuMiwxOCwxOC45LDE5LjgsMjAuNywyMS42LDIyLjQsMjIuOSwyMy4xLDIyLjksMjIuMiwyMS41LDIwLjgNCjcuNyw3LjksOC4yLDguNCw4LjcsOS4xLDkuNiwxMC4zLDExLDExLjgsMTIuNywxMy41LDE0LjQsMTUuNCwxNi4zLDE3LjEsMTcuOSwxOC44LDE5LjYsMjAuNCwyMS4xLDIxLjcsMjIuMiwyMi40LDIyLjIsMjEuNywyMS4yLDIwLjcNCjgsOC4yLDguNiw4LjcsOSw5LjUsMTAsMTAuNiwxMS4zLDEyLDEyLjgsMTMuNiwxNC41LDE1LjQsMTYuNCwxNy4xLDE3LjgsMTguNywxOS4zLDIwLjEsMjAuOSwyMS4zLDIxLjcsMjIuMywyMS44LDIxLjQsMjAuOSwyMC41DQo4LjEsOC40LDguNyw4LjksOS4zLDkuNywxMC4yLDEwLjgsMTEuNCwxMi4xLDEyLjksMTMuNiwxNC40LDE1LjMsMTYuMSwxNi45LDE3LjYsMTguNCwxOSwxOS43LDIwLjIsMjAuNywyMSwyMS4zLDIxLjIsMjEsMjAuNywyMC40DQo4LjEsOC40LDguOCw5LjEsOS41LDkuOSwxMC40LDEwLjksMTEuNSwxMi4yLDEyLjksMTMuNiwxNC40LDE1LjIsMTYsMTYuNywxNy40LDE4LjEsMTguNywxOS4zLDE5LjgsMjAuMiwyMC41LDIwLjcsMjAuNywyMC42LDIwLjQsMjAuMQ0KOC4zLDguNSw4LjksOS4yLDkuNiw5LjksMTAuNCwxMSwxMS42LDEyLjIsMTIuOSwxMy42LDE0LjMsMTUuMSwxNS45LDE2LjYsMTcuMywxNy45LDE4LjMsMTkuMSwxOS4zLDE5LjcsMjAuMSwyMC4yLDIwLjQsMjAuNCwyMC4zLDIwLjENCjguNSw4LjMsOSw5LjQsOS42LDkuOSwxMC41LDEwLjksMTEuNywxMi4zLDEyLjgsMTMuNCwxNC4zLDE0LjksMTUuOCwxNi42LDE3LjIsMTcuOCwxNy43LDE5LjQsMTguOCwxOS4zLDE5LjgsMTkuOCwyMC4yLDIwLjMsMjAuMywyMC44"""


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
    assert cal[0][1]["contents"].startswith(b"numpy-stl (3.2.0)")


@patch.dict(os.environ, {"OUTPUT_BUCKET_NAME": "output-bucket", "REGION": "us-east-2"})
def test_apig_post_lambda_handler_handle_2():
    event = {"body": BASE64_POST, "isBase64Encoded": True}

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
    assert cal[0][1]["contents"].startswith(b"numpy-stl (3.2.0)")
    assert len(cal[0][1]["contents"]) == 51384
