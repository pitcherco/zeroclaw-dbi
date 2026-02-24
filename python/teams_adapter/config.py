"""Configuration for the Teams adapter."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Teams adapter configuration — loaded from environment variables."""

    # Bot Framework
    bot_app_id: str
    bot_app_secret: str

    # ZeroClaw gateway
    zeroclaw_gateway_url: str = "http://127.0.0.1:42617"
    zeroclaw_gateway_token: str = ""

    # Adapter
    adapter_host: str = "0.0.0.0"
    adapter_port: int = 3978

    # Timeouts (seconds)
    zeroclaw_timeout: int = 300  # 5 min for long m365 operations

    model_config = {"env_prefix": "ZEROCLAW_ADAPTER_"}


settings = Settings()
