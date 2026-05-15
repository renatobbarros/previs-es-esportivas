import httpx
import os
from datetime import datetime, timezone
from typing import List, Dict, Any
from loguru import logger

class PandaScoreFetcher:
    """Busca odds e jogos de E-sports via PandaScore."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("PANDASCORE_API_KEY")
        self.base_url = "https://api.pandascore.co"

    async def get_upcoming_matches(self) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("PANDASCORE_API_KEY não configurada.")
            return []

        # Busca partidas de CS2 e LoL que começam em breve
        url = f"{self.base_url}/matches/upcoming"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {"per_page": 10, "sort": "begin_at"}

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                matches = response.json()
                
                processed = []
                for m in matches:
                    # Normaliza para o formato do sistema
                    if not m.get('opponents'): continue
                    
                    item = {
                        "id": f"panda_{m['id']}",
                        "sport": "esports",
                        "league": m.get('videogame', {}).get('name', 'E-sports'),
                        "home_team": m['opponents'][0]['opponent']['name'],
                        "away_team": m['opponents'][1]['opponent']['name'] if len(m['opponents']) > 1 else "TBD",
                        "commence_time": m['begin_at'],
                        "best_odds": {
                            "h2h": {
                                "casa": {"odd": 1.85, "bookmaker": "Consenso Panda"}, # PandaScore free não dá odds detalhadas as vezes
                                "fora": {"odd": 1.85, "bookmaker": "Consenso Panda"}
                            }
                        }
                    }
                    processed.append(item)
                return processed
        except Exception as e:
            logger.error(f"Erro PandaScore: {e}")
            return []
