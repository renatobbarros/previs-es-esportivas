import numpy as np
from typing import Dict, Any

class KellyManager:
    """
    Motor de gestão de banca baseado no Critério de Kelly.
    Implementa Kelly Fracionário e travas de segurança.
    """

    def __init__(self, kelly_fraction: float = 0.25, max_stake_pct: float = 0.05):
        self.kelly_fraction = kelly_fraction
        self.max_stake_pct = max_stake_pct

    def calculate_kelly(self, ai_prob: float, odds: float) -> Dict[str, Any]:
        """
        Calcula stake sugerida.
        f = (bp - q) / b
        b = odds - 1
        p = prob ia
        q = 1 - p
        """
        if odds <= 1.0: return {"stake_pct": 0, "ev": 0}

        b = odds - 1
        p = ai_prob
        q = 1 - p

        # Kelly Completo
        full_kelly = (b * p - q) / b if b > 0 else 0
        
        # Kelly Fracionário
        suggested_f = full_kelly * self.kelly_fraction
        
        # Travas de segurança
        final_f = max(0, min(suggested_f, self.max_stake_pct))
        
        # Expected Value (EV)
        ev = (p * b) - q
        
        # Edge
        market_prob = 1 / odds
        edge = p - market_prob

        return {
            "full_kelly": round(full_kelly, 4),
            "suggested_stake_pct": round(final_f, 4),
            "ev_percent": round(ev, 4),
            "edge_percent": round(edge, 4),
            "is_value": ev > 0 and edge > 0.05
        }

    def get_signal_grade(self, edge: float, confidence: float) -> str:
        """Categoriza a qualidade do sinal (A, B, C)."""
        if edge > 0.12 and confidence > 80:
            return "A"
        elif edge > 0.08 and confidence > 65:
            return "B"
        elif edge > 0.05:
            return "C"
        return "D"

    def run_monte_carlo(self, initial_bankroll: float, win_prob: float, odds: float, bets: int = 1000):
        """Simula risco de ruína."""
        results = []
        for _ in range(100): # 100 trajetórias
            bankroll = initial_bankroll
            path = [bankroll]
            stake_pct = self.calculate_kelly(win_prob, odds)['suggested_stake_pct']
            
            for _ in range(bets):
                stake = bankroll * stake_pct
                if np.random.random() < win_prob:
                    bankroll += stake * (odds - 1)
                else:
                    bankroll -= stake
                path.append(bankroll)
                if bankroll < initial_bankroll * 0.1: # Ruína (10% da banca)
                    break
            results.append(path)
        return results
