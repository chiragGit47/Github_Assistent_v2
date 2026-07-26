from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    github_client_id: str
    github_client_secret: str
    frontend_url: str = "http://localhost:5173"

    ollama_api_key: str
    ollama_base_url: str = "https://ollama.com"
    ollama_model: str = "gpt-oss:20b"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()