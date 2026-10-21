
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    MODE: Literal['LOCAL', 'DEV', 'PROD', 'TEST']


    DB_NAME: str
    DB_PORT: int
    DB_USER: str
    DB_PASS: str
    DB_HOST: str

    REDIS_HOST: str
    REDIS_PORT: int


    @property
    def REDIS_URL(self):
        return f'redis://{self.REDIS_HOST}:{self.REDIS_PORT}'


    @property
    def DB_URL(self):
        return URL.create(
            "postgresql+asyncpg",
            username=self.DB_USER,
            password=self.DB_PASS,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
        )
    model_config = SettingsConfigDict(env_file=ENV_PATH,env_file_encoding="utf-8")
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

settings = Settings()
