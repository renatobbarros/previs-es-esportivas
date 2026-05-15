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
from config import settings
from rich.console import Console
from rich.table import Table
console = Console()

class OddsFetcher:
    """Busca odds, calcula consenso de mercado e melhores preços."""

    def __init__(self, api_keys: list[str] | None = None):
        # Carrega todas as chaves disponíveis no .env se não passadas
        if not api_keys:
            self.keys = [settings.THE_ODDS_API_KEY]
            # Adiciona chaves extras se existirem no ambiente (pode ser expandido no config.py se necessário)
            self.keys = [k for k in self.keys if k]
        else:
            self.keys = api_keys

        self.current_key_index = 0
        self.is_demo = len(self.keys) == 0
        self.base_url = "https://api.the-odds-api.com/v4"
        
        if self.is_demo:
            console.print("[bold yellow]⚠️ MODO DEMO ATIVADO:[/bold yellow] Nenhuma chave de API encontrada. Usando dados fictícios.")

    @property
    def api_key(self):
        if self.is_demo: return None
        return self.keys[self.current_key_index]

    def rotate_key(self):
        """Muda para a próxima chave disponível."""
        if len(self.keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.keys)
            console.print(f"[bold cyan]🔄 Rotação de Chave:[/bold cyan] Alternando para a chave {self.current_key_index + 1}")
            return True
        return False

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

                    if response.status_code in [401, 429] or "Usage quota" in response.text:
                        console.print(f"[yellow]Aviso: Chave {self.current_key_index + 1} falhou (Erro {response.status_code}).[/yellow]")
                        if self.rotate_key():
                            # Tenta novamente com a nova chave (mesma tentativa)
                            return await self.get_upcoming_games(sport)
                        else:
                            console.print("[bold red]ERRO:[/bold red] Todas as chaves atingiram o limite.")
                            return []

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

    async def get_recent_scores(self, sport: str, days_ago: int = 3) -> list[dict]:
        """
        Busca resultados/placares recentes para um esporte.
        """
        if self.is_demo:
            return []

        params = {
            "apiKey": self.api_key,
            "daysFrom": days_ago,
        }
        url = f"{self.base_url}/sports/{sport}/scores/"

        async with httpx.AsyncClient(timeout=20) as client:
            for attempt in range(3):
                try:
                    response = await client.get(url, params=params)
                    
                    if response.status_code in [401, 429]:
                        if self.rotate_key():
                            params["apiKey"] = self.api_key
                            continue
                        else:
                            return []

                    response.raise_for_status()
                    return response.json()
                except Exception as e:
                    if attempt == 2:
                        console.print(f"[red]Erro ao buscar scores para {sport}: {e}[/red]")
                        return []
                    await asyncio.sleep(1)
        return []

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
                "best_odds": {
                    "h2h": {"casa": {"odd": 0.0, "bookmaker": ""}, "empate": {"odd": 0.0, "bookmaker": ""}, "fora": {"odd": 0.0, "bookmaker": ""}},
                    "totals": {}, # Ex: "Over 2.5": {"odd": 2.1, "bookmaker": "Bet365"}
                    "spreads": {} # Ex: "Casa -1.5": {"odd": 1.9, "bookmaker": "Pinnacle"}
                },
                "market_consensus": {"h2h": {"casa_prob": 0.0, "empate_prob": 0.0, "fora_prob": 0.0}, "totals": {}}
            }

            all_h2h_no_vig = []
            all_totals_no_vig = {}

            
            for bm in game.get("bookmakers", []):
                bm_key = bm["key"]
                bm_title = bm["title"]
                item["bookmakers"][bm_key] = {"markets": {}}
                
                for market in bm.get("markets", []):
                    m_key = market["key"]
                    outcomes = market["outcomes"]
                    
                    if m_key == "h2h":
                        odds = {o["name"]: o["price"] for o in outcomes}
                        normalized_h2h = {}
                        for name, price in odds.items():
                            if name == item["home_team"]: key = "casa"
                            elif name == item["away_team"]: key = "fora"
                            else: key = "empate"
                            normalized_h2h[key] = price
                            
                            # Update Best Odds H2H
                            if price > item["best_odds"]["h2h"][key]["odd"]:
                                item["best_odds"]["h2h"][key] = {"odd": price, "bookmaker": bm_title}
                        
                        item["bookmakers"][bm_key]["markets"]["h2h"] = normalized_h2h
                        all_h2h_no_vig.append(self.calculate_no_vig_probs(normalized_h2h))
                        
                    elif m_key == "totals":
                        # Outcomes: Over/Under with point
                        normalized_totals = {}
                        for o in outcomes:
                            label = f"{o['name']} {o['point']}"
                            price = o["price"]
                            item["bookmakers"][bm_key]["markets"].setdefault("totals", {})[label] = price
                            
                            if label not in item["best_odds"]["totals"] or price > item["best_odds"]["totals"][label]["odd"]:
                                item["best_odds"]["totals"][label] = {"odd": price, "bookmaker": bm_title}
                                
                            # Prepare for no-vig calculation by point
                            point_key = str(o['point'])
                            normalized_totals.setdefault(point_key, {})[o['name']] = price
                            
                        for point_key, odds_dict in normalized_totals.items():
                            if "Over" in odds_dict and "Under" in odds_dict:
                                no_vig = self.calculate_no_vig_probs(odds_dict)
                                if no_vig:
                                    all_totals_no_vig.setdefault(f"Over {point_key}", []).append(no_vig.get("Over", 0))
                                    all_totals_no_vig.setdefault(f"Under {point_key}", []).append(no_vig.get("Under", 0))
                                
                    elif m_key == "spreads":
                        # Outcomes: Team name with point
                        for o in outcomes:
                            team_type = "Casa" if o["name"] == item["home_team"] else "Fora"
                            label = f"{team_type} {o['point']:+}"
                            price = o["price"]
                            item["bookmakers"][bm_key]["markets"].setdefault("spreads", {})[label] = price
                            
                            if label not in item["best_odds"]["spreads"] or price > item["best_odds"]["spreads"][label]["odd"]:
                                item["best_odds"]["spreads"][label] = {"odd": price, "bookmaker": bm_title}

            # Calcula consenso H2H
            if all_h2h_no_vig:
                for key in ["casa", "empate", "fora"]:
                    probs = [p.get(key, 0) for p in all_h2h_no_vig if key in p]
                    if probs:
                        item["market_consensus"]["h2h"][f"{key}_prob"] = round(sum(probs) / len(probs), 4)
                        
            # Calcula consenso Totals
            for label, probs in all_totals_no_vig.items():
                if probs:
                    item["market_consensus"]["totals"][label] = round(sum(probs) / len(probs), 4)

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
            # Calcula spread (eficiência do mercado) em H2H
            h_odds = [bm["markets"]["h2h"].get("casa") for bm in g["bookmakers"].values() 
                     if "h2h" in bm["markets"] and "casa" in bm["markets"]["h2h"]]
            spread = max(h_odds) - min(h_odds) if len(h_odds) > 1 else 0.0

            summary_data.append({
                "Jogo": f"{g['home_team']} x {g['away_team']}",
                "Início (BRT)": g["commence_time"],
                "Melhor Casa": f"{g['best_odds']['h2h']['casa']['odd']:.2f} ({g['best_odds']['h2h']['casa']['bookmaker']})",
                "Melhor Empate": f"{g['best_odds']['h2h']['empate']['odd']:.2f} ({g['best_odds']['h2h']['empate']['bookmaker']})",
                "Melhor Fora": f"{g['best_odds']['h2h']['fora']['odd']:.2f} ({g['best_odds']['h2h']['fora']['bookmaker']})",
                "Spread (C)": round(spread, 2),
                "Consenso Casa": f"{g['market_consensus']['h2h']['casa_prob']:.1%}"
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
                        {"key": "bet365", "title": "Bet365", "markets": [
                            {"key": "h2h", "outcomes": [{"name": h, "price": 2.1}, {"name": "Draw", "price": 3.4}, {"name": a, "price": 3.2}]},
                            {"key": "totals", "outcomes": [{"name": "Over", "price": 1.95, "point": 2.5}, {"name": "Under", "price": 1.85, "point": 2.5}]}
                        ]},
                        {"key": "betano", "title": "Betano", "markets": [
                            {"key": "h2h", "outcomes": [{"name": h, "price": 2.05}, {"name": "Draw", "price": 3.5}, {"name": a, "price": 3.25}]},
                            {"key": "spreads", "outcomes": [{"name": h, "price": 1.9, "point": -0.5}, {"name": a, "price": 1.9, "point": +0.5}]}
                        ]}
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
                        {"key": "pinnacle", "title": "Pinnacle", "markets": [
                            {"key": "h2h", "outcomes": [{"name": h, "price": 1.91}, {"name": a, "price": 1.91}]},
                            {"key": "totals", "outcomes": [{"name": "Over", "price": 1.91, "point": 220.5}, {"name": "Under", "price": 1.91, "point": 220.5}]}
                        ]},
                        {"key": "bet365", "title": "Bet365", "markets": [
                            {"key": "h2h", "outcomes": [{"name": h, "price": 1.85}, {"name": a, "price": 1.95}]},
                            {"key": "spreads", "outcomes": [{"name": h, "price": 1.9, "point": -5.5}, {"name": a, "price": 1.9, "point": +5.5}]}
                        ]}
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
