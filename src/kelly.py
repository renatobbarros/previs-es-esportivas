"""
kelly.py — Critério de Kelly fracionado para gestão de banca
Calcula tamanho ótimo de aposta baseado no edge e na banca disponível.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config

if TYPE_CHECKING:
    from src.ev_calculator import OddsSignal

console = Console()


@dataclass
class BetRecommendation:
    """Recomendação de aposta com tamanho calculado pelo Kelly fracionado."""
    signal_ref: "OddsSignal"
    bankroll: float
    kelly_full: float       # Kelly completo (0–1)
    kelly_fraction: float   # Kelly fracionado aplicado
    bet_amount: float       # Valor em R$
    bet_pct: float          # Porcentagem da banca
    expected_profit: float  # Lucro esperado em R$

    def to_dict(self) -> dict:
        return {
            "match": f"{self.signal_ref.home_team} vs {self.signal_ref.away_team}",
            "league": self.signal_ref.league,
            "outcome": self.signal_ref.outcome,
            "bookmaker": self.signal_ref.bookmaker,
            "odds": round(self.signal_ref.odds, 3),
            "edge": round(self.signal_ref.edge, 4),
            "ev": round(self.signal_ref.ev, 4),
            "bankroll": round(self.bankroll, 2),
            "kelly_full": round(self.kelly_full, 4),
            "kelly_fraction_used": config.KELLY_FRACTION,
            "bet_pct": round(self.bet_pct, 4),
            "bet_amount_brl": round(self.bet_amount, 2),
            "expected_profit_brl": round(self.expected_profit, 2),
        }


class KellyCalculator:
    """
    Implementa o critério de Kelly fracionado.

    Kelly completo: f* = (p*(b+1) - 1) / b
    onde:
        p = probabilidade justa de vencer
        b = odds decimais - 1 (lucro líquido por unidade)
    """

    def __init__(
        self,
        bankroll: float | None = None,
        kelly_fraction: float = config.KELLY_FRACTION,
        max_bet_pct: float = config.MAX_BET_PCT,
        min_bet_pct: float = config.MIN_BET_PCT,
    ):
        self.bankroll = bankroll or config.DEFAULT_BANKROLL
        self.kelly_fraction = kelly_fraction
        self.max_bet_pct = max_bet_pct
        self.min_bet_pct = min_bet_pct

    # ──────────────────────────────────────────
    # Cálculo central
    # ──────────────────────────────────────────

    def kelly_stake(self, fair_prob: float, odds: float) -> float:
        """
        Retorna o Kelly completo (fração da banca a apostar).
        Retorna 0 se o Kelly for negativo (sem edge real).
        """
        b = odds - 1  # lucro líquido por unidade
        kelly = (fair_prob * (b + 1) - 1) / b
        return max(0.0, kelly)

    def fractional_kelly(self, fair_prob: float, odds: float) -> float:
        """Kelly fracionado = Kelly completo × fração configurada."""
        return self.kelly_stake(fair_prob, odds) * self.kelly_fraction

    def clamp(self, pct: float) -> float:
        """Limita o tamanho da aposta entre min e max configurados."""
        return max(self.min_bet_pct, min(self.max_bet_pct, pct))

    # ──────────────────────────────────────────
    # Recomendações
    # ──────────────────────────────────────────

    def recommend(self, signal: "OddsSignal") -> BetRecommendation | None:
        """
        Gera uma recomendação de aposta para um sinal.
        Retorna None se o Kelly for zero (sem edge).
        """
        kelly_full = self.kelly_stake(signal.fair_prob, signal.odds)
        if kelly_full <= 0:
            return None

        frac = self.fractional_kelly(signal.fair_prob, signal.odds)
        bet_pct = self.clamp(frac)
        bet_amount = self.bankroll * bet_pct
        expected_profit = bet_amount * signal.ev

        return BetRecommendation(
            signal_ref=signal,
            bankroll=self.bankroll,
            kelly_full=kelly_full,
            kelly_fraction=frac,
            bet_amount=bet_amount,
            bet_pct=bet_pct,
            expected_profit=expected_profit,
        )

    def recommend_all(self, signals: list["OddsSignal"]) -> list[BetRecommendation]:
        """Gera recomendações para uma lista de sinais, ordenadas por EV."""
        recs = [r for s in signals if (r := self.recommend(s)) is not None]
        return sorted(recs, key=lambda r: r.expected_profit, reverse=True)

    # ──────────────────────────────────────────
    # Display
    # ──────────────────────────────────────────

    def print_recommendations(self, recs: list[BetRecommendation]) -> None:
        if not recs:
            console.print("[yellow]Nenhuma recomendação de aposta disponível.[/yellow]")
            return

        total_exposure = sum(r.bet_amount for r in recs)
        total_expected = sum(r.expected_profit for r in recs)

        table = Table(title="💰 Recomendações de Aposta (Kelly Fracionado)", show_lines=True)
        table.add_column("Jogo", style="white")
        table.add_column("Outcome", style="bold")
        table.add_column("Book", style="magenta")
        table.add_column("Odds", justify="right", style="yellow")
        table.add_column("Edge", justify="right", style="green")
        table.add_column("Kelly%", justify="right")
        table.add_column("Aposta (R$)", justify="right", style="cyan")
        table.add_column("Lucro Esp. (R$)", justify="right", style="bright_green")

        for r in recs:
            s = r.signal_ref
            table.add_row(
                f"{s.home_team} vs {s.away_team}",
                s.outcome,
                s.bookmaker,
                f"{s.odds:.2f}",
                f"{s.edge:.1%}",
                f"{r.bet_pct:.1%}",
                f"R$ {r.bet_amount:.2f}",
                f"R$ {r.expected_profit:.2f}",
            )

        console.print(table)
        console.print(
            f"\n[bold]Banca:[/bold] R$ {self.bankroll:.2f} | "
            f"[bold]Exposição total:[/bold] R$ {total_exposure:.2f} "
            f"({total_exposure/self.bankroll:.1%}) | "
            f"[bold]Lucro esp.:[/bold] [green]R$ {total_expected:.2f}[/green]"
        )

    def update_bankroll(self, result_pnl: float) -> float:
        """Atualiza a banca após resultado (positivo = lucro, negativo = perda)."""
        self.bankroll += result_pnl
        symbol = "📈" if result_pnl >= 0 else "📉"
        console.print(
            f"{symbol} Banca atualizada: R$ {self.bankroll:.2f} "
            f"({'+'if result_pnl>=0 else ''}{result_pnl:.2f})"
        )
        return self.bankroll
