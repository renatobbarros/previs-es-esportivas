import asyncio
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path.cwd()))

from src.odds_fetcher import OddsFetcher
from config import settings

async def test():
    fetcher = OddsFetcher()
    for league in settings.ALL_LEAGUES:
        if league == "esports": continue
        print(f"Buscando {league}...")
        games = await fetcher.get_upcoming_games(league)
        print(f"-> {league}: {len(games)} jogos")

if __name__ == "__main__":
    asyncio.run(test())
