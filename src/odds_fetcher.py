"""
odds_fetcher.py — Busca e processamento de odds em tempo real.
Implementa suporte a The Odds API, cálculo de no-vig e fuso horário Brasília.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Adiciona o diretório raiz ao path para importar config
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config

load_dotenv()
console = Console()

class OddsFetcher:
    """Busca odds, calcula consenso de mercado e melhores preços."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.ODDS_API_KEY
        self.is_demo = not self.api_key
        self.base_url = "https://api.the-odds-api.com/v4"
        
        if self.is_demo:
            console.print("[bold yellow]⚠️ MODO DEMO ATIVADO:[/bold yellow] Chave de API não encontrada no .env. Usando dados fictícios.")

    # ──────────────────────────────────────────
    # Cálculos de Probabilidade
    # ──────────────────────────────────────────

    def calculate_no_vig_probs(self, odds_dict: dict[str, float]) -> dict[str, float]:
        """
        Remove a margem da casa (overround) das odds.
        Fórmula: prob = (1/odd) / soma(1/todas_odds)
        """
        if not odds_dict:
            return {}
        
        implied_probs = {k: 1/v for k, v in odds_dict.items() if v > 0}
        total_implied = sum(implied_probs.values())
        
        if total_implied == 0:
            return {}
            
        return {k: round(p / total_implied, 4) for k, p in implied_probs.items()}

    # ──────────────────────────────────────────
    # Busca de Dados
    # ──────────────────────────────────────────

    async def get_upcoming_games(self, sport: str) -> list[dict]:
        """
        Busca jogos e odds. Implementa retentativas para rate limit.
        """
        if self.is_demo:
            return self._get_mock_data(sport)

        params = {
            "apiKey": self.api_key,
            "regions": "eu,uk",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        }
        url = f"{self.base_url}/sports/{sport}/odds/"

        async with httpx.AsyncClient(timeout=20) as client:
            for attempt in range(3):
                try:
                    response = await client.get(url, params=params)
                    
                    # Log de requests restantes
                    remaining = response.headers.get("X-Requests-Remaining", "?")
                    if attempt == 0:
                        console.print(f"[dim]API Info: {remaining} requisições restantes.[/dim]")

                    if response.status_code == 401:
                        console.print("[bold red]ERRO:[/bold red] Chave de API inválida. Verifique o arquivo .env.")
                        return []
                    
                    if response.status_code == 429:
                        console.print(f"[yellow]Rate limit atingido. Tentativa {attempt+1}/3. Aguardando 2s...[/yellow]")
                        await asyncio.sleep(2)
                        continue

                    response.raise_for_status()
                    games_data = response.json()
                    
                    if not games_data:
                        console.print(f"[cyan]Nenhum jogo disponível para {sport} no momento.[/cyan]")
                        return []

                    return self._process_games(games_data, sport)

                except httpx.HTTPError as e:
                    if attempt == 2:
                        console.print(f"[red]Erro na API após 3 tentativas: {e}[/red]")
                        return []
                    await asyncio.sleep(1)
            
        return []

    # ──────────────────────────────────────────
    # Processamento e Normalização
    # ──────────────────────────────────────────

    def _process_games(self, raw_games: list[dict], sport: str) -> list[dict]:
        """Processa a resposta bruta da API para o formato solicitado."""
        processed = []
        # Fuso horário de Brasília (UTC-3)
        tz_br = timezone(timedelta(hours=-3))

        for game in raw_games:
            # Conversão de horário
            dt_utc = datetime.fromisoformat(game["commence_time"].replace("Z", "+00:00"))
            dt_br = dt_utc.astimezone(tz_br)

            item = {
                "id": game["id"],
                "sport": sport,
                "league": game.get("sport_title", "Unknown"),
                "home_team": game["home_team"],
                "away_team": game["away_team"],
                "commence_time": dt_br.strftime("%Y-%m-%d %H:%M:%S"),
                "bookmakers": {},
                "best_odds": {"home": {"odd": 0.0, "bookmaker": ""}, "draw": {"odd": 0.0, "bookmaker": ""}, "away": {"odd": 0.0, "bookmaker": ""}},
                "market_consensus": {"home_prob": 0.0, "draw_prob": 0.0, "away_prob": 0.0}
            }

            all_no_vig_probs = []
            
            for bm in game.get("bookmakers", []):
                bm_key = bm["key"]
                h2h = next((m for m in bm["markets"] if m["key"] == "h2h"), None)
                
                if h2h:
                    odds = {o["name"]: o["price"] for o in h2h["outcomes"]}
                    
                    # Normaliza nomes para home, draw, away
                    normalized_odds = {}
                    for name, price in odds.items():
                        if name == item["home_team"]: key = "home"
                        elif name == item["away_team"]: key = "away"
                        else: key = "draw"
                        normalized_odds[key] = price
                    
                    item["bookmakers"][bm_key] = normalized_odds
                    
                    # Update Best Odds
                    for key, price in normalized_odds.items():
                        if price > item["best_odds"][key]["odd"]:
                            item["best_odds"][key] = {"odd": price, "bookmaker": bm["title"]}
                    
                    # Calcula no-vig para este bookie
                    all_no_vig_probs.append(self.calculate_no_vig_probs(normalized_odds))

            # Calcula consenso (média das probabilidades no-vig)
            if all_no_vig_probs:
                for key in ["home", "draw", "away"]:
                    probs = [p.get(key, 0) for p in all_no_vig_probs if key in p]
                    if probs:
                        item["market_consensus"][f"{key}_prob"] = round(sum(probs) / len(probs), 4)

            processed.append(item)
        return processed

    # ──────────────────────────────────────────
    # Relatórios e Pandas
    # ──────────────────────────────────────────

    def get_best_odds_summary(self, games: list[dict]) -> pd.DataFrame:
        """Cria um resumo consolidado das melhores odds e eficiência do mercado."""
        if not games:
            return pd.DataFrame()

        summary_data = []
        for g in games:
            # Calcula spread (eficiência do mercado)
            # Diferença entre a melhor e a pior odd encontrada para o time da casa
            h_odds = [bm.get("home") for bm in g["bookmakers"].values() if "home" in bm]
            spread = max(h_odds) - min(h_odds) if len(h_odds) > 1 else 0.0

            summary_data.append({
                "Jogo": f"{g['home_team']} x {g['away_team']}",
                "Início (BRT)": g["commence_time"],
                "Melhor Home": f"{g['best_odds']['home']['odd']:.2f} ({g['best_odds']['home']['bookmaker']})",
                "Melhor Draw": f"{g['best_odds']['draw']['odd']:.2f} ({g['best_odds']['draw']['bookmaker']})",
                "Melhor Away": f"{g['best_odds']['away']['odd']:.2f} ({g['best_odds']['away']['bookmaker']})",
                "Spread (H)": round(spread, 2),
                "Consenso Home": f"{g['market_consensus']['home_prob']:.1%}"
            })
        
        return pd.DataFrame(summary_data)

    # ──────────────────────────────────────────
    # Modo Demo
    # ──────────────────────────────────────────

    def _get_mock_data(self, sport: str) -> list[dict]:
        """Gera dados mockados realistas para testes."""
        mock_raw = []
        
        if "soccer" in sport:
            teams = [
                ("Arsenal", "Chelsea"), ("Real Madrid", "Barcelona"), 
                ("Man City", "Liverpool"), ("Flamengo", "Palmeiras"),
                ("Bayern", "Dortmund")
            ]
            for i, (h, a) in enumerate(teams):
                mock_raw.append({
                    "id": f"mock_soc_{i}",
                    "sport_title": "Soccer Demo",
                    "home_team": h, "away_team": a,
                    "commence_time": (datetime.now(timezone.utc) + timedelta(hours=i+2)).isoformat(),
                    "bookmakers": [
                        {"key": "bet365", "title": "Bet365", "markets": [{"key": "h2h", "outcomes": [{"name": h, "price": 2.1}, {"name": "Draw", "price": 3.4}, {"name": a, "price": 3.2}]}]},
                        {"key": "betano", "title": "Betano", "markets": [{"key": "h2h", "outcomes": [{"name": h, "price": 2.05}, {"name": "Draw", "price": 3.5}, {"name": a, "price": 3.25}]}]}
                    ]
                })
        elif "basketball" in sport:
            teams = [("Lakers", "Warriors"), ("Celtics", "Heat"), ("Nets", "Bucks")]
            for i, (h, a) in enumerate(teams):
                mock_raw.append({
                    "id": f"mock_nba_{i}",
                    "sport_title": "NBA Demo",
                    "home_team": h, "away_team": a,
                    "commence_time": (datetime.now(timezone.utc) + timedelta(hours=i+5)).isoformat(),
                    "bookmakers": [
                        {"key": "pinnacle", "title": "Pinnacle", "markets": [{"key": "h2h", "outcomes": [{"name": h, "price": 1.91}, {"name": a, "price": 1.91}]}]},
                        {"key": "bet365", "title": "Bet365", "markets": [{"key": "h2h", "outcomes": [{"name": h, "price": 1.85}, {"name": a, "price": 1.95}]}]}
                    ]
                })
        
        return self._process_games(mock_raw, sport)

# ──────────────────────────────────────────────
# Execução de Teste
# ──────────────────────────────────────────────

async def main():
    fetcher = OddsFetcher()
    
    console.rule("[bold cyan]Buscando Odds: Premier League")
    soccer_games = await fetcher.get_upcoming_games("soccer_epl")
    
    if soccer_games:
        summary = fetcher.get_best_odds_summary(soccer_games)
        
        table = Table(title="Melhores Odds Encontradas (Premier League)")
        for col in summary.columns:
            table.add_column(col)
        
        for _, row in summary.iterrows():
            # Destaca linhas com spread alto (exemplo > 0.05)
            style = "bold green" if float(row["Spread (H)"].split()[0] if isinstance(row["Spread (H)"], str) else row["Spread (H)"]) > 0.04 else ""
            table.add_row(*[str(val) for val in row.values], style=style)
            
        console.print(table)
        console.print("\n[dim]* Linhas em verde indicam maior spread entre casas (oportunidade).[/dim]")

    console.rule("[bold cyan]Buscando Odds: NBA")
    nba_games = await fetcher.get_upcoming_games("basketball_nba")
    if nba_games:
        nba_summary = fetcher.get_best_odds_summary(nba_games)
        console.print(nba_summary)

if __name__ == "__main__":
    asyncio.run(main())
