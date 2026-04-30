"""
config.py — Configurações centrais do Sports Edge AI
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"
SIGNALS_DIR = DATA_DIR / "signals"
HISTORICAL_DIR = DATA_DIR / "historical"
BACKTEST_DIR = DATA_DIR / "backtest_results"

for _dir in (SIGNALS_DIR, HISTORICAL_DIR, BACKTEST_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────
# API Keys
# ──────────────────────────────────────────────
CEREBRAS_API_KEY: str = os.getenv("CEREBRAS_API_KEY", "")
ODDS_API_KEY: str = os.getenv("ODDS_API_KEY", "")
RAPIDAPI_KEY: str = os.getenv("RAPIDAPI_KEY", "")

# ──────────────────────────────────────────────
# Ligas monitoradas — The Odds API sport keys
# ──────────────────────────────────────────────
FOOTBALL_LEAGUES: list[str] = [
    "soccer_epl",                # Premier League
    "soccer_uefa_champs_league", # Champions League
    "soccer_spain_la_liga",      # La Liga
    "soccer_germany_bundesliga", # Bundesliga
    "soccer_brazil_campeonato",  # Brasileirão Série A
]

BASKETBALL_LEAGUES: list[str] = [
    "basketball_nba",            # NBA
    "basketball_euroleague",     # Euroleague
    "basketball_ncaab",          # NCAA Basketball
    "basketball_brazil_nbb",     # NBB Brasil
]

ALL_LEAGUES: list[str] = FOOTBALL_LEAGUES + BASKETBALL_LEAGUES

# ──────────────────────────────────────────────
# Bookmakers prioritários (ordem de preferência)
# ──────────────────────────────────────────────
BOOKMAKERS: list[str] = [
    "bet365",
    "betano",
    "unibet",
    "pinnacle",
]

# ──────────────────────────────────────────────
# Parâmetros de edge e valor esperado
# ──────────────────────────────────────────────
MIN_EDGE: float = 0.07   # edge mínimo aceitável (7 %)
MIN_EV: float = 0.05     # EV mínimo aceitável (5 %)
MAX_ODDS: float = 10.0   # odds máximas consideradas
MIN_ODDS: float = 1.20   # odds mínimas consideradas

# ──────────────────────────────────────────────
# Gestão de banca
# ──────────────────────────────────────────────
DEFAULT_BANKROLL: float = float(os.getenv("BANKROLL", "100"))  # R$
KELLY_FRACTION: float = 0.25  # Kelly fracionado (25 % do Kelly completo)
MAX_BET_PCT: float = 0.10     # aposta máxima = 10 % da banca
MIN_BET_PCT: float = 0.01     # aposta mínima = 1 % da banca

# ──────────────────────────────────────────────
# Cerebras / IA
# ──────────────────────────────────────────────
CEREBRAS_MODEL: str = "llama3.1-8b"
IA_MAX_TOKENS: int = 1024
IA_TEMPERATURE: float = 0.0  # baixo para análise objetiva

# ──────────────────────────────────────────────
# Agendamento
# ──────────────────────────────────────────────
REFRESH_INTERVAL: int = int(os.getenv("REFRESH_INTERVAL", "300"))  # segundos

# ──────────────────────────────────────────────
# RSS Feeds — notícias esportivas
# ──────────────────────────────────────────────
NEWS_FEEDS: list[str] = [
    "https://www.espn.com/espn/rss/news",
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://globoesporte.globo.com/rss.xml",
    "https://www.skysports.com/rss/12040",   # Sky Sports Football
]

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
