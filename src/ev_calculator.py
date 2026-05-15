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
from config import settings

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
        return self.edge >= settings.MIN_EDGE and self.ev >= settings.MIN_EV

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

        bookmakers = game.get("bookmakers", {})
        if not bookmakers:
            return signals

        # Agrega odds por outcome de todos os bookmakers
        market_key = "h2h"  # head-to-head (1X2)
        outcome_odds: dict[str, list[float]] = {}

        # O fetcher agora produz um dict de bookmakers
        for bm_key, bm_data in bookmakers.items():
            markets = bm_data.get("markets", {})
            if market_key not in markets:
                continue
            for outcome_name, price in markets[market_key].items():
                if settings.MIN_ODDS <= price <= settings.MAX_ODDS:
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
        for bm_key, bm_data in bookmakers.items():
            markets = bm_data.get("markets", {})
            if market_key not in markets:
                continue

            bm_name = bm_data.get("title", bm_key)
            for outcome_name, price in markets[market_key].items():
                if not (settings.MIN_ODDS <= price <= settings.MAX_ODDS):
                    continue

                fair_prob = fair_prob_map.get(outcome_name)
                if fair_prob is None:
                    continue

                implied = self.implied_probability(price)
                edge = self.calculate_edge(fair_prob, implied)
                ev = self.calculate_ev(fair_prob, price)

                if edge >= settings.MIN_EDGE_THRESHOLD:
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

    def triage_games(self, games: list[dict], news_contexts: dict = None) -> list[dict]:
        """
        Filtra apenas os jogos que valem a pena ser analisados pela IA.
        Critérios:
        1. Existe um edge matemático claro no mercado (arbitragem ou value).
        2. Existe contexto de notícias relevante (lesões, alertas).
        3. O spread entre bookmakers é alto (> 5%).
        """
        triaged = []
        news_contexts = news_contexts or {}
        
        for game in games:
            has_news = game["id"] in news_contexts
            
            # Cálculo de spread de mercado
            best_odds = game.get("best_odds", {}).get("h2h", {})
            h = best_odds.get("casa", {}).get("odd", 0)
            d = best_odds.get("empate", {}).get("odd", 0)
            a = best_odds.get("fora", {}).get("odd", 0)
            
            if h > 0 and d > 0 and a > 0:
                market_margin = (1/h + 1/d + 1/a) - 1
                # Se a margem for muito baixa ou negativa (raro), há ineficiência
                if market_margin < 0.02 or has_news:
                    triaged.append(game)
                    continue
            
            # Outros critérios podem ser adicionados aqui
            if has_news:
                triaged.append(game)
        
        console.print(f"[cyan]🎯 Triagem: {len(triaged)}/{len(games)} jogos selecionados para análise de IA.[/cyan]")
        return triaged

    def apply_ai_results(self, ai_results: list[dict]) -> list[dict]:
        """
        Recebe os resultados qualitativos da IA e aplica a matemática rigorosa.
        Retorna os sinais finais prontos para o Telegram/Dashboard.
        """
        from src.kelly import calculate_kelly
        
        final_signals = []
        for res in ai_results:
            game = res["game_info"]
            prob_ia = res["prob_real"]
            
            # Busca a melhor odd disponível para a sugestão da IA
            market_data = game.get("best_odds", {})
            
            best_odd = 0
            found_outcome = ""
            found_market = ""
            
            # Busca simples nos mercados H2H e Totais
            for m_name, outcomes in market_data.items():
                for o_name, o_data in outcomes.items():
                    # Se o nome sugerido pela IA está contido no nome do mercado ou vice-versa
                    if res["best_bet_name"].lower() in o_name.lower() or o_name.lower() in res["best_bet_name"].lower():
                        best_odd = o_data.get("odd", 0)
                        found_outcome = o_name
                        found_market = m_name
                        break
                if best_odd > 0: break

            if best_odd <= 1.0:
                continue

            # Cálculos Matemáticos (Sem Alucinação)
            edge = prob_ia - (1/best_odd)
            ev = (prob_ia * best_odd) - 1
            
            if ev > 0:
                stake_pct = calculate_kelly(best_odd, prob_ia, settings.KELLY_FRACTION)
                
                # Monta o sinal final
                signal = {
                    **res,
                    "odd": best_odd,
                    "market": found_market,
                    "outcome": found_outcome,
                    "edge_pct": round(edge * 100, 2),
                    "ev": round(ev, 3),
                    "stake_pct": round(stake_pct * 100, 2)
                }
                final_signals.append(signal)
        
        # Ordena por EV
        return sorted(final_signals, key=lambda x: x["ev"], reverse=True)


    def print_signals(self, signals: list[dict]) -> None:
        if not signals:
            console.print("[yellow]Nenhum sinal encontrado.[/yellow]")
            return

        table = Table(title="🎯 Sinais de Aposta Otimizados", show_lines=True)
        table.add_column("Jogo", style="white")
        table.add_column("Aposta", style="bold green")
        table.add_column("Odd", justify="right", style="yellow")
        table.add_column("Edge", justify="right", style="green")
        table.add_column("EV", justify="right", style="bright_green")
        table.add_column("Stake", justify="right", style="cyan")

        for s in signals:
            game = s.get("game_info", {})
            table.add_row(
                f"{game.get('home_team')} x {game.get('away_team')}",
                s.get("best_bet_name"),
                f"{s.get('odd'):.2f}",
                f"{s.get('edge_pct'):.1f}%",
                f"{s.get('ev'):.3f}",
                f"{s.get('stake_pct'):.1f}%"
            )

        console.print(table)


if __name__ == "__main__":
    # Teste rápido
    calc = EVCalculator()
    print("EV Calculator operacional.")
