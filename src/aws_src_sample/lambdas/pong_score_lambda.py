#!/usr/bin/env python3
import logging
import os
import json
from aws_src_sample.utils.apig_utils import get_event_body
from aws_src_sample.s3.object_inputter import ObjectInputter
from aws_src_sample.s3.object_outputter import ObjectOutputter
from aws_src_sample.dynamodb.pong_score_table import PongScoreTable

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)
from aws_src_sample.utils.aws_env_vars import (
    get_pong_score_table_name,
    get_output_bucket_name,
    get_region,
)


class PongScoreHandler:
    def __init__(
        self,
        object_outputter: ObjectOutputter,
        pong_score_table: PongScoreTable,
    ) -> None:
        self.object_outputter = object_outputter
        self.pong_score_table = pong_score_table

    def handle(self, event: dict) -> dict:
        output_bucket_name = get_output_bucket_name()
        self.object_outputter.put(bucket=output_bucket_name, key="data", contents=self.pong_score_table.get_top_five())
        return {}

    def handle2(self, event: dict) -> dict:
        try:
            input_data = get_event_body(event)
            self.pong_score_table.set_value(item_key="abc", item_value=9)
            return {
                "statusCode": 201,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": json.dumps(
                    {
                        "message": "File processed successfully.",
                    }
                ),
            }
        except Exception as e:
            print(f"Error processing file: {str(e)}")

            return {"statusCode": 500, "body": json.dumps("Failed to process the file.")}


# placehold


def pong_score_get_lambda_handler(event: dict, context) -> dict:
    lh = PongScoreHandler(
        # whatever
        ObjectOutputter(),
        PongScoreTable(get_pong_score_table_name()),
    )
    return lh.handle(event)


def pong_score_post_lambda_handler(event: dict, context) -> dict:
    lh = PongScoreHandler(
        # whatever
        ObjectOutputter(),
        PongScoreTable(get_pong_score_table_name()),
    )
    return lh.handle(event)
