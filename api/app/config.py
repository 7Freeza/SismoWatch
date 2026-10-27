from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    db_dsn_reader: str
    jwt_secret: str
    jwt_expire_minutes: int = 480
    cors_origins: str = "http://localhost:3000"
    airflow_base_url: str = "http://airflow-webserver:8080"
    airflow_api_user: str = "admin"
    airflow_api_password: str = ""
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen2.5:3b"
    answer_model: str = "qwen2.5:3b"
    llm_timeout_seconds: int = 45
    ai_enabled: bool = True

    @property
    def cors_list(self):
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
