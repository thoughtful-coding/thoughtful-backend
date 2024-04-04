import boto3


class ObjectOutputter:
    def __init__(self) -> None:
        self.client = boto3.client("s3")

    def put(self, *, bucket: str, key: str, contents: bytes) -> None:
        result = self.client.put_object(
            Bucket=bucket,
            Key=key,
            Body=contents,
        )
        return result
