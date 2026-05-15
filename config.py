from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Optional

class Settings(BaseSettings):
    # Configuração do Pydantic para ler o .env
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # --- APIs DE DADOS ---
    THE_ODDS_API_KEY: str
    PANDASCORE_API_KEY: str
    GROQ_API_KEY: str
    ADMIN_PASSWORD: str = "mudar_em_producao"
    
    # --- APIs DE IA ---
    ANTHROPIC_API_KEY: Optional[str] = None
    CEREBRAS_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # --- COMUNICAÇÃO ---
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str
    OWNER_TELEGRAM_ID: int

    # --- BANCO DE DADOS ---
    DATABASE_PATH: str = "data/sports_edge.db"
    POSTGRES_URL: Optional[str] = None
    
    @property
    def ROOT_DIR(self) -> Path:
        return Path(__file__).parent
    
    @property
    def DATA_DIR(self) -> Path:
        return self.ROOT_DIR / "data"

    @property
    def SIGNALS_DIR(self) -> Path:
        return self.DATA_DIR / "signals"

    @property
    def HISTORICAL_DIR(self) -> Path:
        return self.DATA_DIR / "historical"

    @property
    def BACKTEST_DIR(self) -> Path:
        return self.DATA_DIR / "backtests"

    # --- GESTÃO DE RISCO ---
    BANKROLL: float = 20.0
    MIN_EDGE_THRESHOLD: float = 0.06
    MIN_CONFIDENCE_THRESHOLD: int = 60
    KELLY_FRACTION: float = 0.25
    MAX_STAKE_PERCENT: float = 0.05
    PROFIT_SHARE_PCT: float = 0.10
    
    # Aliases para compatibilidade legada
    @property
    def DEFAULT_BANKROLL(self) -> float: return self.BANKROLL
    @property
    def MAX_BET_PCT(self) -> float: return self.MAX_STAKE_PERCENT
    @property
    def MIN_BET_PCT(self) -> float: return 0.01 # 1% default

    # --- SISTEMA ---
    LOG_LEVEL: str = "INFO"
    REFRESH_INTERVAL: int = 3600
    CEREBRAS_MODEL: str = "llama3.1-70b"
    
    ENABLE_FOOTBALL: bool = True
    ENABLE_BASKETBALL: bool = True
    ENABLE_ESPORTS: bool = True
    ENABLE_DEEP_ANALYSIS: bool = False

    FOOTBALL_LEAGUES: list[str] = ["soccer_epl", "soccer_brazil_campeonato"]
    BASKETBALL_LEAGUES: list[str] = ["basketball_nba"]
    
    @property
    def ALL_LEAGUES(self) -> list[str]:
        return self.FOOTBALL_LEAGUES + self.BASKETBALL_LEAGUES + ["esports"]

    @property
    def MIN_EDGE(self) -> float: return self.MIN_EDGE_THRESHOLD
    @property
    def MIN_EV(self) -> float: return 0.05
    @property
    def MIN_ODDS(self) -> float: return 1.20
    @property
    def MAX_ODDS(self) -> float: return 5.00

# Instância global importável
try:
    settings = Settings()
except Exception as e:
    print("\n❌ ERRO DE CONFIGURAÇÃO: Verifique se o arquivo .env está correto.")
    print(f"Detalhes: {e}\n")
    raise SystemExit(1)
