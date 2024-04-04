import abc


class Transformer(abc.ABC):
    @staticmethod
    @abc.abstractmethod
    def transform(input_data: bytes) -> bytes:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def get_file_ext() -> str:
        raise NotImplementedError
