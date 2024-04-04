#!/usr/bin/env python3
import logging
import os

from aws_src_sample.dynamodb.file_type_counter_table import FileTypeCounterTable
from aws_src_sample.s3.object_inputter import ObjectInputter
from aws_src_sample.s3.object_outputter import ObjectOutputter
from aws_src_sample.transformers.csv_to_stl import CSVToSTLTransformer
from aws_src_sample.transformers.transformer import Transformer
from aws_src_sample.transformers.txt_to_art import TxtToArtTransformer
from aws_src_sample.utils.aws_env_vars import (
    get_file_type_counter_table_name,
    get_output_bucket_name,
)

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


def create_instructions(
    object_inputter: ObjectInputter,
    object_outputter: ObjectOutputter,
    input_bucket_name: str,
    input_bucket_key: str,
    output_bucket_name: str,
) -> None:
    object_outputter.put(
        bucket=output_bucket_name,
        key="instructions.txt",
        contents="lorem ipsum asjhdkajsdhkajshd",
    )


FN_INTERFACE: dict[str, Transformer] = {
    "csv": CSVToSTLTransformer(),
    "txt": TxtToArtTransformer(),
}


class S3PutLambdaHandler:
    def __init__(
        self,
        object_inputter: ObjectInputter,
        object_outputter: ObjectOutputter,
        file_type_counter_table: FileTypeCounterTable,
    ) -> None:
        self.object_inputter = object_inputter
        self.object_outputter = object_outputter
        self.file_type_counter_table = file_type_counter_table

    def handle(self, event: dict) -> dict:
        input_bucket = event["Records"][0]["s3"]["bucket"]["name"]
        input_key = event["Records"][0]["s3"]["object"]["key"]
        input_file_type = str(input_key.split(".")[-1])
        output_bucket_name = get_output_bucket_name()

        # Get our bucket and file name
        _LOGGER.info(f"decision: {input_file_type}")
        if input_file_type not in FN_INTERFACE:
            _LOGGER.info("invalid file")
            create_instructions(
                self.object_inputter, self.object_outputter, input_bucket, input_key, output_bucket_name
            )
        else:
            _LOGGER.info(f"valid file: {FN_INTERFACE[input_file_type]}")
            input_data = self.object_inputter.get(bucket=input_bucket, key=input_key)

            output_data = FN_INTERFACE[input_file_type].transform(input_data)
            output_path = os.path.splitext(input_key)[0] + FN_INTERFACE[input_file_type].get_file_ext()

            self.object_outputter.put(bucket=output_bucket_name, key=output_path, contents=output_data)

            self.file_type_counter_table.increment(item_key=input_file_type)

        return {"statusCode": 201}


def s3_put_lambda_handler(event: dict, context) -> dict:
    _LOGGER.info(event)

    lh = S3PutLambdaHandler(
        ObjectInputter(),
        ObjectOutputter(),
        FileTypeCounterTable(get_file_type_counter_table_name()),
    )
    return lh.handle(event)
