import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.odds_fetcher import OddsFetcher

async def diagnose():
    fetcher = OddsFetcher()
    all_games = []
    print(f"Buscando jogos para {len(config.ALL_LEAGUES)} ligas...")
    for sport in config.ALL_LEAGUES:
        games = await fetcher.get_upcoming_games(sport)
        if games:
            all_games.extend(games)
    
    print(f"Total de jogos encontrados: {len(all_games)}")
    
    dates = {}
    for g in all_games:
        dt_str = g.get('commence_time')
        # dt format is %Y-%m-%d %H:%M:%S
        dt = dt_str.split(' ')[0]
        dates[dt] = dates.get(dt, 0) + 1
    
    print("\nDistribuição por data:")
    for d in sorted(dates.keys()):
        print(f"{d}: {dates[d]} jogos")

    # Check markets for today's games
    tz_br = timezone(timedelta(hours=-3))
    hoje_str = datetime.now(tz_br).strftime("%Y-%m-%d")
    hoje_games = [g for g in all_games if g.get('commence_time').startswith(hoje_str)]
    
    print(f"\nJogos para HOJE ({hoje_str}): {len(hoje_games)}")
    if hoje_games:
        for g in hoje_games[:5]:
            print(f"- {g['home_team']} x {g['away_team']} | Markets: {list(g['best_odds'].keys())}")

if __name__ == "__main__":
    asyncio.run(diagnose())
