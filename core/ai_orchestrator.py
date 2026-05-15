import os
import json
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from loguru import logger
from config import settings

class AIOrchestrator:
    """
    Orquestrador de IA em cascata: Groq (Triagem) -> Claude (Profundidade).
    Otimiza custos e maximiza precisão analítica.
    """

    def __init__(self):
        self.groq_key = settings.GROQ_API_KEY
        self.claude_key = settings.ANTHROPIC_API_KEY
        self.cache = {} 
        self.client = httpx.AsyncClient(timeout=30.0)

    async def triage_game(self, game_data: Dict, sport: str) -> Dict[str, Any]:
        """Análise rápida via Groq (Llama 3.3)."""
        if not self.groq_key:
            logger.warning("GROQ_API_KEY não configurada. Usando fallback básico.")
            return {"should_escalate": False, "edge": 0.05, "confidence": 50}

        prompt = f"""
Analise rapidamente este jogo de {sport} para Value Betting:
Jogo: {game_data.get('home_team')} x {game_data.get('away_team')}
Odds: {game_data.get('odds')} 

Retorne APENAS um JSON:
{{
  "edge": float,
  "ai_probability": float,
  "recommended_outcome": "Time Vence",
  "should_escalate": bool,
  "confidence": int,
  "key_factors": ["fator1", "fator2"]
}}
"""
        try:
            response = await self.client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.groq_key}"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1
                }
            )
            response.raise_for_status()
            return json.loads(response.json()['choices'][0]['message']['content'])
        except Exception as e:
            logger.error(f"Erro Groq: {e}")
            return {"should_escalate": False, "edge": 0}

    async def deep_analyze(self, game_data: Dict, sport: str, triage_result: Dict) -> Dict[str, Any]:
        """Análise profunda via Claude 3.5 Sonnet."""
        if not self.claude_key:
            return triage_result

        logger.info(f"🔥 Escalonando análise profunda para {game_data.get('home_team')} x {game_data.get('away_team')}")
        
        prompt = f"""
Você é um analista sênior de apostas quantitativas.
Analise PROFUNDAMENTE o jogo de {sport}: {game_data.get('home_team')} x {game_data.get('away_team')}
Triagem Inicial detectou Edge de {triage_result.get('edge')*100:.1f}%.

DADOS:
{json.dumps(game_data, indent=2)}

Retorne um JSON detalhado com 'risk_factors', 'reasoning' técnico e 'final_probability'.
"""
        try:
            response = await self.client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.claude_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-3-5-sonnet-20240620",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            content = response.json()['content'][0]['text']
            # Extração simples de JSON do texto do Claude
            import re
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                deep_result = json.loads(match.group())
                deep_result['model_used'] = "Groq + Claude 3.5"
                return deep_result
        except Exception as e:
            logger.error(f"Erro Claude: {e}")
        
        return triage_result

    async def run_full_pipeline(self, game_data: Dict, sport: str) -> Dict[str, Any]:
        # 1. Triage via Groq
        triage = await self.triage_game(game_data, sport)
        
        # 2. Decisão de Escalonamento (Apenas se chave Claude existir)
        if self.claude_key and (triage.get("should_escalate") or triage.get("edge", 0) > 0.08):
            result = await self.deep_analyze(game_data, sport, triage)
        else:
            result = triage
            result['model_used'] = "Groq (Llama 3.3)"
            
        # Garante que campos essenciais existam
        if 'ai_probability' not in result: result['ai_probability'] = triage.get('ai_probability', 0.5)
        if 'edge' not in result: result['edge'] = triage.get('edge', 0)
        if 'confidence' not in result: result['confidence'] = triage.get('confidence', 50)
            
        return result
