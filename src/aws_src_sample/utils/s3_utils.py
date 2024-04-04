def bucket_name_and_key_to_http_url(region: str, bucket_name: str, bucket_key: str) -> str:
    return f"https://{bucket_name}.s3.{region}.amazonaws.com/{bucket_key}"
