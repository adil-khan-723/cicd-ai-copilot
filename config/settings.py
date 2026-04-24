from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

_settings: "Settings | None" = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM routing — providers: ollama | anthropic
    llm_provider: str = Field(default="ollama")
    analysis_model: str = Field(default="llama3.1:8b")
    generation_model: str = Field(default="qwen2.5-coder:14b")
    llm_fallback_provider: str = Field(default="anthropic")
    confidence_threshold: float = Field(default=0.75)

    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_models: str = Field(default="/Volumes/SSD/ollama-models")
    ollama_timeout: int = Field(default=120)

    # Anthropic
    anthropic_api_key: str = Field(default="")
    anthropic_analysis_model: str = Field(default="claude-haiku-4-5-20251001")
    anthropic_generation_model: str = Field(default="claude-sonnet-4-6")

    # Jenkins
    jenkins_url: str = Field(default="http://localhost:8080")
    jenkins_user: str = Field(default="admin")
    jenkins_token: str = Field(default="")
    # Set to container name (e.g. "jenkins") when Jenkins runs in Docker.
    # Set to "" for bare-metal / systemd Jenkins — workspace accessed directly.
    jenkins_docker_container: str = Field(default="jenkins")
    # Absolute path to Jenkins workspace root on the host (or inside the container).
    # Auto-detected when empty: /var/lib/jenkins/workspace (Linux bare-metal)
    # or /var/jenkins_home/workspace (Docker container default).
    jenkins_workspace_path: str = Field(default="")

    # Webhook
    webhook_port: int = Field(default=8000)
    webhook_secret: str = Field(default="")
    webhook_host: str = Field(default="0.0.0.0")

    # Cache
    cache_ttl: int = Field(default=3600)
    redis_url: str = Field(default="")

    # Logging
    log_level: str = Field(default="INFO")
    audit_log_path: str = Field(default="audit.log")


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
