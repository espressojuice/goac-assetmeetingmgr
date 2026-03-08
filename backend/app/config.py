from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://goac:goac_dev@localhost:5432/goac"
    UPLOAD_DIR: str = "./uploads"
    TIMEZONE: str = "US/Central"
    APP_NAME: str = "GOAC Asset Meeting Manager"

    model_config = {"env_file": ".env"}


settings = Settings()
