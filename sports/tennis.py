import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any

class TennisAnalyzer:
    def __init__(self, db_manager=None):
        self.db = db_manager

    def calculate_serve_return_model(self, p1_stats: Dict, p2_stats: Dict) -> float:
        s1 = p1_stats.get('avg_sv_pts_won', 0.60)
        s2 = p2_stats.get('avg_sv_pts_won', 0.60)
        r1 = 1 - s2
        dr1 = s1 / (1 - r1) if (1-r1) > 0 else 1.0
        dr2 = s2 / (1 - (1-s1)) if (1-(1-s1)) > 0 else 1.0
        return round(dr1 / (dr1 + dr2), 4)

    def analyze_match(self, match: Dict[str, Any]) -> Dict[str, Any]:
        p1_stats = {"avg_sv_pts_won": 0.64, "win_rate": 0.72}
        p2_stats = {"avg_sv_pts_won": 0.61, "win_rate": 0.65}
        prob = self.calculate_serve_return_model(p1_stats, p2_stats)
        return {"win_probability": prob}
