#!/usr/bin/env python3
import json
import logging
import random

from aws_src_sample.dynamodb.file_type_counter_table import FileTypeCounterTable
from aws_src_sample.s3.object_outputter import ObjectOutputter
from aws_src_sample.transformers.csv_to_stl import CSVToSTLTransformer
from aws_src_sample.utils.apig_utils import get_event_body
from aws_src_sample.utils.aws_env_vars import (
    get_file_type_counter_table_name,
    get_output_bucket_name,
    get_region,
)
from aws_src_sample.utils.s3_utils import bucket_name_and_key_to_http_url

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


class APIGPostLambdaHandler:
    def __init__(
        self,
        object_outputter: ObjectOutputter,
        file_type_counter_table: FileTypeCounterTable,
    ) -> None:
        self.object_outputter = object_outputter
        self.file_type_counter_table = file_type_counter_table
        self.transformer = CSVToSTLTransformer()

    def handle(self, event: dict) -> dict:
        try:
            input_data = get_event_body(event)
            output_bucket_name = get_output_bucket_name()
            output_bucket_key = f"transform_{random.randint(0, 100_000_000):09d}" + self.transformer.get_file_ext()

            output_data = self.transformer.transform(input_data)
            self.object_outputter.put(bucket=output_bucket_name, key=output_bucket_key, contents=output_data)
            output_url = bucket_name_and_key_to_http_url(get_region(), output_bucket_name, output_bucket_key)

            self.file_type_counter_table.increment(item_key=self.transformer.get_file_ext()[1:])

            return {
                "statusCode": 201,
                "headers": {
                    "Access-Control-Allow-Origin": "https://eric-rizzi.github.io",
                    "Content-Type": "application/json",
                },
                "body": json.dumps(
                    {
                        "message": "File processed successfully.",
                        "location": output_url,
                    }
                ),
            }
        except Exception as e:
            print(f"Error processing file: {str(e)}")

            return {"statusCode": 500, "body": json.dumps("Failed to process the file.")}


def api_post_lambda_handler(event: dict, context) -> dict:
    _LOGGER.info(event)

    lh = APIGPostLambdaHandler(
        ObjectOutputter(),
        FileTypeCounterTable(get_file_type_counter_table_name()),
    )
    return lh.handle(event)
