#!/usr/bin/env python3
import os


def get_output_bucket_name() -> str:
    return os.environ["OUTPUT_BUCKET_NAME"]
