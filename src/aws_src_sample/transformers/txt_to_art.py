from aws_src_sample.transformers.transformer import Transformer


class TxtToArtTransformer(Transformer):
    @staticmethod
    def transform(input_data: bytes) -> bytes:
        # file_contents = art.art(input_data)
        return b"hi: " + input_data

    @staticmethod
    def get_file_ext() -> str:
        return ".txt"
