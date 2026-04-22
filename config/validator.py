def validate_config(settings) -> None:
    if settings.llm_provider == "anthropic" and not settings.anthropic_api_key:
        raise SystemExit(
            "ERROR: ANTHROPIC_API_KEY not set.\n"
            "Set it in .env or as an environment variable.\n"
            "Get your key at https://console.anthropic.com"
        )
