from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    APP_NAME: str = Field("voice-cloning-app", env="APP_NAME")
    STORAGE_PATH: str = Field("./storage", env="STORAGE_PATH")
    HOST: str = Field("0.0.0.0", env="HOST")
    PORT: int = Field(8000, env="PORT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
