from providers.base import BaseLLMProvider
from config import get_settings

# Task types and which model setting they use
_GENERATION_TASKS = {"generation", "generate", "generate_jenkinsfile", "generate_workflow"}
_ANALYSIS_TASKS = {"analysis", "analyze", "analyze_logs", "summarize"}


def get_provider(task: str = "analysis") -> BaseLLMProvider:
    """
    Return the configured LLM provider for the given task.

    Task type determines which model is selected:
      - analysis tasks  → settings.analysis_model
      - generation tasks → settings.generation_model

    Provider is selected by settings.llm_provider:
      - "ollama"     → OllamaProvider
      - "anthropic"  → AnthropicProvider  (Phase 5)
      - "groq"       → GroqProvider       (Phase 5)
      - "gemini"     → GeminiProvider     (Phase 5)
    """
    settings = get_settings()
    provider_name = settings.llm_provider.lower()

    is_generation = task.lower() in _GENERATION_TASKS
    model = settings.generation_model if is_generation else settings.analysis_model

    if provider_name == "ollama":
        from providers.ollama_provider import OllamaProvider
        return OllamaProvider(model=model)

    # Cloud providers wired in Phase 5 — stubs raise clearly until then
    if provider_name == "anthropic":
        raise NotImplementedError(
            "Anthropic provider not yet implemented. "
            "Set LLM_PROVIDER=ollama or wait for Phase 5."
        )
    if provider_name == "groq":
        raise NotImplementedError(
            "Groq provider not yet implemented. "
            "Set LLM_PROVIDER=ollama or wait for Phase 5."
        )
    if provider_name == "gemini":
        raise NotImplementedError(
            "Gemini provider not yet implemented. "
            "Set LLM_PROVIDER=ollama or wait for Phase 5."
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider_name}'. "
        "Valid options: ollama | anthropic | groq | gemini"
    )
