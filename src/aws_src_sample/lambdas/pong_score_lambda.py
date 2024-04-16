#!/usr/bin/env python3
import logging
import os


from aws_src_sample.s3.object_inputter import ObjectInputter
from aws_src_sample.s3.object_outputter import ObjectOutputter
from aws_src_sample.dynamodb.pong_score_table import PongScoreTable

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)
from aws_src_sample.utils.aws_env_vars import (
    get_pong_score_table_name,
    get_output_bucket_name,
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


# placehold


def pong_score_lambda_handler(event: dict, context) -> dict:
    lh = PongScoreHandler(
        # whatever
        ObjectOutputter(),
        PongScoreTable(get_pong_score_table_name()),
    )
    return lh.handle(event)
