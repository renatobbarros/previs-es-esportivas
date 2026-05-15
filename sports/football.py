import pandas as pd
import numpy as np
from scipy.stats import poisson
from typing import Dict, List, Any

class FootballAnalyzer:
    """Motor de análise estatística para Futebol."""

    def __init__(self, db_manager=None):
        self.db = db_manager

    def calculate_poisson_probs(self, home_exp: float, away_exp: float, max_goals: int = 6) -> Dict[str, float]:
        """Calcula probabilidades de 1X2 e Over/Under usando Poisson."""
        home_dist = poisson.pmf(range(max_goals + 1), home_exp)
        away_dist = poisson.pmf(range(max_goals + 1), away_exp)
        
        matrix = np.outer(home_dist, away_dist)
        
        prob_h = np.sum(np.triu(matrix, 1).T)
        prob_d = np.sum(np.diag(matrix))
        prob_a = np.sum(np.tril(matrix, -1).T)
        
        # Over 2.5
        prob_over_25 = 1 - (matrix[0,0] + matrix[0,1] + matrix[0,2] + 
                           matrix[1,0] + matrix[1,1] + matrix[2,0])
        
        return {
            "home": round(prob_h, 4),
            "draw": round(prob_d, 4),
            "away": round(prob_a, 4),
            "over_25": round(prob_over_25, 4)
        }

    def get_team_stats(self, team_name: str, last_n: int = 10) -> Dict[str, float]:
        """Busca médias de gols e XG do time."""
        # Mock para estrutura
        return {
            "goals_scored_avg": 1.8,
            "goals_conceded_avg": 1.2,
            "xg_for_avg": 1.95,
            "xg_against_avg": 1.1
        }

    def analyze_match(self, match: Dict[str, Any]) -> Dict[str, Any]:
        h_stats = self.get_team_stats(match['home_team'])
        a_stats = self.get_team_stats(match['away_team'])
        
        # Projeção simples de gols
        h_exp = (h_stats['goals_scored_avg'] + a_stats['goals_conceded_avg']) / 2
        a_exp = (a_stats['goals_scored_avg'] + h_stats['goals_conceded_avg']) / 2
        
        probs = self.calculate_poisson_probs(h_exp, a_exp)
        
        return {
            "probabilities": probs,
            "expected_goals": {"home": h_exp, "away": a_exp}
        }
