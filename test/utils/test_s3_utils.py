from aws_src_sample.utils.s3_utils import bucket_name_and_key_to_http_url


def test_bucket_name_and_key_to_http_url_1() -> None:
    url = bucket_name_and_key_to_http_url("us-east-2", "example-bucket", "output.txt")
    assert url == "https://example-bucket.s3.us-east-2.amazonaws.com/output.txt"
