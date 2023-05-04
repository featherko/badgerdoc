from minio import Minio

from .config import settings


class MinioCommunicator:
    client: Minio = None

    def __init__(self) -> None:
        if not self.client:
            self.create_client()

    @classmethod
    def create_client(cls) -> None:
        cls.client = Minio(
            endpoint=settings.minio_host,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )
