import boto3


class ObjectInputter:
    def __init__(self) -> None:
        self.client = boto3.client("s3")

    def get(self, *, bucket: str, key: str) -> bytes:
        response = self.client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
