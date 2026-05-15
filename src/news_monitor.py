import feedparser
import httpx
import json
import hashlib
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger

class NewsMonitor:
    """Monitor global de notícias esportivas com classificação de impacto via IA."""

    SOURCES = {
        "football": ["https://ge.globo.com/rss/futebol/", "https://www.espn.com.br/rss/futebol"],
        "nba": ["https://www.nba.com/rss/nba_rss.xml"],
        "tennis": ["https://www.atptour.com/en/media/rss-feed"],
        "esports": ["https://www.hltv.org/rss/news"]
    }

    def __init__(self, db_manager):
        self.db = db_manager
        self.processed_hashes = set()

    async def analyze_impact(self, news_item: Dict) -> Optional[Dict]:
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key: return None

        prompt = f"""
Analise o impacto desta notícia para apostas:
Título: {news_item['headline']}
Esporte: {news_item['sport']}

Retorne APENAS JSON:
{{
  "team": "Nome",
  "impact": "CRÍTICO/ALTO/MÉDIO/BAIXO",
  "summary": "Resumo",
  "probability_adjustment": float
}}
"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"}
                    }
                )
                data = json.loads(response.json()['choices'][0]['message']['content'])
                data.update({"source": news_item['url'], "published_at": news_item['published_at']})
                return data
        except Exception:
            return None

    async def run_sync(self):
        logger.info("📰 Buscando notícias...")
        # Lógica de fetch e análise...
        pass
