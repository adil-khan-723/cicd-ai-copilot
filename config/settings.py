from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM routing
    llm_provider: str = Field(default="ollama")
    analysis_model: str = Field(default="llama3.1:8b")
    generation_model: str = Field(default="qwen2.5-coder:14b")
    llm_fallback_provider: str = Field(default="groq")
    confidence_threshold: float = Field(default=0.75)

    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_models: str = Field(default="/Volumes/SSD/ollama-models")
    ollama_timeout: int = Field(default=120)

    # Anthropic
    anthropic_api_key: str = Field(default="")
    anthropic_analysis_model: str = Field(default="claude-haiku-4-5-20251001")
    anthropic_generation_model: str = Field(default="claude-sonnet-4-6")

    # Groq
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-versatile")

    # Gemini
    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-1.5-flash")

    # Slack
    slack_bot_token: str = Field(default="")
    slack_app_token: str = Field(default="")
    slack_signing_secret: str = Field(default="")
    slack_channel: str = Field(default="#devops-alerts")

    # UI
    slack_alerts: str = Field(default="enabled")   # "enabled" | "disabled"
    github_repo: str = Field(default="")           # "owner/repo" active project

    # Jenkins
    jenkins_url: str = Field(default="http://localhost:8080")
    jenkins_user: str = Field(default="admin")
    jenkins_token: str = Field(default="")

    # GitHub
    github_token: str = Field(default="")
    github_org: str = Field(default="")
    github_default_repo: str = Field(default="")

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
