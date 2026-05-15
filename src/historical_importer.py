"""
src/historical_importer.py — Importador de dados históricos do football-data.co.uk.
Permite baixar dados de temporadas passadas para validação de modelos.
"""
import httpx
import pandas as pd
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from config import settings

class HistoricalImporter:
    """Baixa e processa CSVs do football-data.co.uk."""
    
    BASE_URL = "https://www.football-data.co.uk/mmz4281"
    
    # Mapeamento de códigos de ligas
    LEAGUES = {
        "E0": "Premier League",
        "E1": "Championship",
        "SP1": "La Liga",
        "SP2": "Segunda Division",
        "D1": "Bundesliga",
        "I1": "Serie A",
        "F1": "Ligue 1",
        "B1": "Belgium",
        "P1": "Portugal",
        "BRA": "Brazil Serie A" # Nota: Brazil costuma ter formato diferente ou via outro link
    }

    def __init__(self):
        settings.HISTORICAL_DIR.mkdir(parents=True, exist_ok=True)

    def download_season(self, league_code: str, season_str: str = "2324"):
        """
        Baixa o CSV de uma liga e temporada específica.
        season_str: "2324" para 2023/2024
        """
        url = f"{self.BASE_URL}/{season_str}/{league_code}.csv"
        filename = f"{league_code}_{season_str}.csv"
        filepath = settings.HISTORICAL_DIR / filename
        
        print(f"Baixando {url}...")
        
        try:
            with httpx.Client() as client:
                response = client.get(url)
                response.raise_for_status()
                
                with open(filepath, "wb") as f:
                    f.write(response.content)
                
                print(f"✓ Salvo em {filepath}")
                return filepath
        except Exception as e:
            print(f"Erro ao baixar: {e}")
            return None

    def load_historical_data(self, filepath: Path):
        """Carrega e limpa o CSV para análise."""
        df = pd.read_csv(filepath)
        # Filtra colunas básicas: Data, Times, Gols, Odds (B365)
        columns = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR', 'B365H', 'B365D', 'B365A']
        # Verifica quais colunas existem no CSV (pode variar por temporada)
        available_cols = [c for c in columns if c in df.columns]
        return df[available_cols]

if __name__ == "__main__":
    importer = HistoricalImporter()
    # Baixa Premier League temporada atual
    path = importer.download_season("E0", "2324")
    if path:
        df = importer.load_historical_data(path)
        print(df.head())
