import abc


class Transformer(abc.ABC):
    @abc.abstractmethod
    @staticmethod
    def transform(input_data: bytes) -> bytes:
        raise NotImplementedError

    @abc.abstractmethod
    @staticmethod
    def get_file_ext() -> str:
        raise NotImplementedError
