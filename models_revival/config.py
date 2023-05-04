from pydantic import BaseSettings


# todo: optimize settings
class Settings(BaseSettings):
    """Settings.
    Some of these settings are overridden by environment variables"""

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    minio_host: str = "minio:9000"  # how to use in main app
    minio_access_key: str = "minio"  # how to use in main app
    minio_secret_key: str = "minio123"  # how to use in main app
    root_path: str = ""  # exclude


settings = Settings()
