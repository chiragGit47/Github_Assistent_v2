from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    github_client_id: str
    github_client_secret: str
    frontend_url: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()