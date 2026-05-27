from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_ENV: str = "development"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str
    REDIS_URL: str

    GEMINI_API_KEY: str

    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001

    class Config:
        env_file = ".env"

settings = Settings()