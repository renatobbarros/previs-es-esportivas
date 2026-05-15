from config import settings

class EsportsAnalyzer:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.PANDASCORE_API_KEY

    def analyze_match(self, match: Dict[str, Any]) -> Dict[str, Any]:
        # Lógica para CS2/LoL
        return {"winner_probability": 0.55, "best_map": "Mirage"}
