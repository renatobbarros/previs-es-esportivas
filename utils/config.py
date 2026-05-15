from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    THE_ODDS_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    ANTHROPIC_API_KEY: Optional[str] = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    BANKROLL_INITIAL: float = 20.00
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
