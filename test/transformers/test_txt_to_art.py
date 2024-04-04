from aws_src_sample.transformers.txt_to_art import TxtToArtTransformer


def test_transform_1() -> None:
    assert TxtToArtTransformer.transform(b"eric") == b"hi: eric"


def test_get_file_extension_1() -> None:
    assert TxtToArtTransformer().get_file_ext() == ".txt"
