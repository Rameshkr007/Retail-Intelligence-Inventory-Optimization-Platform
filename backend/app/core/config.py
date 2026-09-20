from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Retail Intelligence API"
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/retail_intel"
    jwt_secret: str = "CHANGE_ME_IN_ENV"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 8
    max_upload_size_mb: int = 200

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
