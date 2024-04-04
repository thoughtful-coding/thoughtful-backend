from aws_src_sample.transformers.csv_to_stl import CSVToSTLTransformer


def test_transform_1() -> None:
    assert CSVToSTLTransformer.transform(b"8, 8, 9\n8, 8, 10").startswith(b"numpy-stl (3.1.1)")


def test_get_file_extension_1() -> None:
    assert CSVToSTLTransformer().get_file_ext() == ".stl"
