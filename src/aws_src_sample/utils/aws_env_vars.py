import os


def get_output_bucket_name() -> str:
    return os.environ["OUTPUT_BUCKET_NAME"]


def get_file_type_counter_table_name() -> str:
    return os.environ["FILE_TYPE_COUNTER_TABLE_NAME"]


def get_region() -> str:
    return os.environ["REGION"]

def get_pong_score_table_name() -> str:
    return os.environ["PONG_SCORE_TABLE_NAME"]