"""
ev_calculator.py — Cálculo de Expected Value e detecção de edge
Fórmulas baseadas em probabilidade implícita e mercado eficiente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.table import Table

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config

console = Console()


@dataclass
class OddsSignal:
    """Representa um sinal de aposta com edge positivo."""
    game_id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    commence_time: str
    market: str          # ex: 'h2h'
    outcome: str         # ex: 'home', 'away', 'draw'
    bookmaker: str
    odds: float
    implied_prob: float
    fair_prob: float
    edge: float          # (fair_prob - implied_prob)
    ev: float            # edge normalizado pelo risco
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_value(self) -> bool:
        return self.edge >= config.MIN_EDGE and self.ev >= config.MIN_EV

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "sport": self.sport,
            "league": self.league,
            "match": f"{self.home_team} vs {self.away_team}",
            "commence_time": self.commence_time,
            "market": self.market,
            "outcome": self.outcome,
            "bookmaker": self.bookmaker,
            "odds": round(self.odds, 3),
            "implied_prob": round(self.implied_prob, 4),
            "fair_prob": round(self.fair_prob, 4),
            "edge": round(self.edge, 4),
            "ev": round(self.ev, 4),
            "is_value": self.is_value,
        }


class EVCalculator:
    """
    Calcula Expected Value usando consenso de mercado como proxy de
    probabilidade justa (média ponderada das odds sem margem).
    """

    # ──────────────────────────────────────────
    # Cálculos de probabilidade
    # ──────────────────────────────────────────

    @staticmethod
    def implied_probability(odds: float) -> float:
        """Converte odds decimais em probabilidade implícita."""
        if odds <= 1.0:
            return 1.0
        return 1.0 / odds

    @staticmethod
    def remove_vig(outcomes_odds: list[float]) -> list[float]:
        """
        Remove a margem da casa (vig) usando método proporcional.
        Retorna probabilidades ajustadas que somam 1.
        """
        implied = [1 / o for o in outcomes_odds if o > 0]
        total = sum(implied)
        return [p / total for p in implied]

    @staticmethod
    def calculate_ev(fair_prob: float, odds: float) -> float:
        """
        EV = (fair_prob * (odds - 1)) - (1 - fair_prob)
        Retorna EV por unidade apostada.
        """
        return fair_prob * (odds - 1) - (1 - fair_prob)

    @staticmethod
    def calculate_edge(fair_prob: float, implied_prob: float) -> float:
        """Edge = probabilidade justa - probabilidade implícita."""
        return fair_prob - implied_prob

    # ──────────────────────────────────────────
    # Análise de jogos
    # ──────────────────────────────────────────

    def analyze_game(self, game: dict[str, Any]) -> list[OddsSignal]:
        """
        Analisa um jogo e retorna sinais de value bet encontrados.
        Usa consenso entre bookmakers como probabilidade justa.
        """
        signals: list[OddsSignal] = []

        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            return signals

        # Agrega odds por outcome de todos os bookmakers
        market_key = "h2h"  # head-to-head (1X2)
        outcome_odds: dict[str, list[float]] = {}

        for bm in bookmakers:
            markets = bm.get("markets", {})
            if market_key not in markets:
                continue
            for outcome_name, price in markets[market_key].items():
                if config.MIN_ODDS <= price <= config.MAX_ODDS:
                    outcome_odds.setdefault(outcome_name, []).append(price)

        if not outcome_odds:
            return signals

        # Calcula consenso (probabilidade justa) usando médias sem vig
        outcomes = list(outcome_odds.keys())
        avg_odds = [
            sum(outcome_odds[o]) / len(outcome_odds[o]) for o in outcomes
        ]
        fair_probs = self.remove_vig(avg_odds)
        fair_prob_map = dict(zip(outcomes, fair_probs))

        # Verifica cada bookmaker em busca de value
        for bm in bookmakers:
            markets = bm.get("markets", {})
            if market_key not in markets:
                continue

            bm_name = bm.get("name", "unknown")
            for outcome_name, price in markets[market_key].items():
                if not (config.MIN_ODDS <= price <= config.MAX_ODDS):
                    continue

                fair_prob = fair_prob_map.get(outcome_name)
                if fair_prob is None:
                    continue

                implied = self.implied_probability(price)
                edge = self.calculate_edge(fair_prob, implied)
                ev = self.calculate_ev(fair_prob, price)

                signal = OddsSignal(
                    game_id=game.get("id", ""),
                    sport=game.get("sport", ""),
                    league=game.get("league", ""),
                    home_team=game.get("home_team", ""),
                    away_team=game.get("away_team", ""),
                    commence_time=game.get("commence_time", ""),
                    market=market_key,
                    outcome=outcome_name,
                    bookmaker=bm_name,
                    odds=price,
                    implied_prob=implied,
                    fair_prob=fair_prob,
                    edge=edge,
                    ev=ev,
                )
                signals.append(signal)

        return signals

    def analyze_all(self, games: list[dict[str, Any]]) -> list[OddsSignal]:
        """Analisa todos os jogos e retorna apenas sinais com value."""
        all_signals: list[OddsSignal] = []
        for game in games:
            all_signals.extend(self.analyze_game(game))

        value_bets = [s for s in all_signals if s.is_value]
        console.print(
            f"[yellow]EV Calculator → {len(all_signals)} odds analisadas | "
            f"[green]{len(value_bets)} value bets encontradas[/green]"
        )
        return value_bets

    # ──────────────────────────────────────────
    # Display
    # ──────────────────────────────────────────

    def print_signals(self, signals: list[OddsSignal]) -> None:
        if not signals:
            console.print("[yellow]Nenhum value bet encontrado.[/yellow]")
            return

        table = Table(title="🎯 Value Bets Detectadas", show_lines=True)
        table.add_column("Jogo", style="white")
        table.add_column("Liga", style="cyan", no_wrap=True)
        table.add_column("Outcome", style="bold")
        table.add_column("Book", style="magenta")
        table.add_column("Odds", justify="right", style="yellow")
        table.add_column("Edge", justify="right", style="green")
        table.add_column("EV", justify="right", style="bright_green")

        for s in sorted(signals, key=lambda x: x.ev, reverse=True):
            table.add_row(
                f"{s.home_team} vs {s.away_team}",
                s.league,
                s.outcome,
                s.bookmaker,
                f"{s.odds:.2f}",
                f"{s.edge:.1%}",
                f"{s.ev:.1%}",
            )

        console.print(table)


if __name__ == "__main__":
    # Teste rápido com dados mockados
    mock_games = [
        {
            "id": "test123",
            "sport": "soccer_epl",
            "league": "Premier League",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "commence_time": "2025-01-01T15:00:00Z",
            "bookmakers": [
                {
                    "name": "bet365",
                    "markets": {"h2h": {"Arsenal": 2.10, "Draw": 3.40, "Chelsea": 3.20}},
                },
                {
                    "name": "pinnacle",
                    "markets": {"h2h": {"Arsenal": 2.30, "Draw": 3.30, "Chelsea": 3.10}},
                },
                {
                    "name": "betano",
                    "markets": {"h2h": {"Arsenal": 2.00, "Draw": 3.50, "Chelsea": 3.50}},
                },
            ],
        }
    ]

    calc = EVCalculator()
    signals = calc.analyze_all(mock_games)
    calc.print_signals(signals)
