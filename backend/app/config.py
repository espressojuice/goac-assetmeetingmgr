from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://goac:goac_dev@localhost:5432/goac"
    UPLOAD_DIR: str = "./uploads"
    TIMEZONE: str = "US/Central"
    APP_NAME: str = "GOAC Asset Meeting Manager"

    # Auth
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    FRONTEND_URL: str = "http://localhost:3000"

    # S3 Storage (Hetzner Object Storage)
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET_NAME: str = "assetmeetinghelper"
    S3_REGION: str = "eu-central"

    # Email (SendGrid)
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "notifications@goac-assetmeetingmgr.com"
    SENDGRID_FROM_NAME: str = "GOAC Asset Meeting Manager"
    NOTIFICATION_REMINDER_HOURS: int = 6
    NOTIFICATION_ENABLED: bool = True

    model_config = {"env_file": ".env"}


settings = Settings()
