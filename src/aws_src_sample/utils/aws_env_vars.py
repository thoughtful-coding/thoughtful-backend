#!/usr/bin/env python3
import os


def get_output_bucket_name() -> str:
    return os.environ["OUTPUT_BUCKET_NAME"]
def get_file_type_counter_table_name() -> str:
    return os.environ["FILE_TYPE_COUNTER_TABLE_NAME"]
