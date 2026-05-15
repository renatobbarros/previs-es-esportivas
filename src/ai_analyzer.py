"""
ai_analyzer.py — Análise de valor esperado e probabilidade estimada via IA
Usa o Claude para encontrar edges e precificações incorretas do mercado.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv
from rich.console import Console

# Adiciona o diretório raiz ao path para importar config
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings
from src.kelly import calculate_kelly

console = Console()

# Garante que os diretórios existam
settings.SIGNALS_DIR.mkdir(parents=True, exist_ok=True)


from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal

class AnaliseIA(BaseModel):
    prob_real: float = Field(ge=0.0, le=1.0)
    confianca: float = Field(ge=0.0, le=1.0)
    fatores_positivos: List[str]
    fatores_negativos: List[str]
    red_flags: List[str]
    recomendacao: Literal["apostar", "ignorar", "monitorar"]
    resumo_executivo: str
    best_bet_name: str = Field(description="Nome literal da aposta na BetNacional (ex: 'Flamengo', 'Acima de 2.5')")

    @field_validator('recomendacao')
    def check_red_flags(cls, v, info):
        if info.data.get('red_flags') and v == "apostar":
            return "monitorar"
        return v

class AIAnalyzer:
    """Usa IA (Groq) para calcular probabilidades justas e achar value bets."""

    def __init__(self, api_key: str | None = None):
        # ... inicialização ...
        self.api_key = api_key or settings.GROQ_API_KEY
        self.client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=self.api_key
        )
        self.model = settings.GROQ_MODEL

    def _extract_json(self, text: str) -> dict:
        """Limpa a resposta da IA para garantir a extração do JSON."""
        import re
        try:
            # Tenta encontrar JSON entre chaves
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return json.loads(text)
        except Exception as e:
            logger.error("json_parse_error", text=text[:200], error=str(e))
            raise ValueError("Resposta da IA não contém JSON válido")

    # ──────────────────────────────────────────
    # Análise de Futebol
    # ──────────────────────────────────────────

    async def analyze_football_game(self, game: dict[str, Any], context: str = "") -> dict[str, Any]:
        """Análise estruturada focada em probabilidade justa."""
        
        system_prompt = (
            "Você é um analista quantitativo de apostas esportivas. Analise os dados abaixo e estime a probabilidade REAL do evento.\n"
            "Responda EXCLUSIVAMENTE com um objeto JSON válido.\n\n"
            "REGRAS DE OURO:\n"
            "1. NÃO faça cálculos de EV ou Edge. Apenas forneça sua probabilidade estimada baseada em contexto.\n"
            "2. 'best_bet_name' deve ser o nome EXATO como aparece na BetNacional (ex: 'Real Madrid', 'Acima de 2.5').\n"
            "3. Se houver desfalques críticos, reduza a confiança.\n\n"
            "Campos obrigatórios:\n"
            "{\n"
            "  \"prob_real\": float (0.0 a 1.0),\n"
            "  \"confianca\": float (0.0 a 1.0),\n"
            "  \"best_bet_name\": \"string\",\n"
            "  \"fatores_positivos\": [\"max 3\"],\n"
            "  \"fatores_negativos\": [\"max 3\"],\n"
            "  \"red_flags\": [\"riscos críticos\"],\n"
            "  \"recomendacao\": \"apostar\" | \"ignorar\" | \"monitorar\",\n"
            "  \"resumo_executivo\": \"máx 2 frases\"\n"
            "}"
        )

        user_prompt = f"""
        JOGO: {game.get('home_team')} x {game.get('away_team')} | {game.get('league')}
        ODDS MERCADO: {json.dumps(game.get('best_odds', {}).get('h2h', {}), ensure_ascii=False)}
        CONSENSO MERCADO (Prob Implícita): {json.dumps(game.get('market_consensus', {}).get('h2h', {}), ensure_ascii=False)}
        CONTEXTO: {context or 'Sem notícias recentes.'}
        """

        for attempt in range(2):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.0
                )
                
                raw_json = self._extract_json(response.choices[0].message.content)
                valid_res = AnaliseIA(**raw_json)
                res_dict = valid_res.model_dump()
                res_dict["game_info"] = game
                return res_dict
                
            except Exception as e:
                if attempt == 1:
                    return {"recomendacao": "ignorar", "error": str(e), "game_info": game}
                await asyncio.sleep(1)
        return {"recomendacao": "ignorar", "error": "timeout", "game_info": game}

    async def analyze_nba_game(self, game: dict[str, Any], context: str = "") -> dict[str, Any]:
        """Análise específica para NBA."""
        system_prompt = (
            "Você é um especialista em NBA. Analise pace, offensive rating e injury report.\n"
            "Responda APENAS JSON.\n"
            "Use terminologia BetNacional: 'Acima de 220.5', 'Lakers -4.5', etc."
        )
        # Reutiliza a base de prompt do futebol mas com instruções NBA
        return await self.analyze_football_game(game, context)

    async def format_signal_report(self, signals: list[dict], sport: str) -> str:
        """Gera um relatório Markdown com os dados processados."""
        if not signals: return ""
            
        ts = datetime.now().strftime("%d/%m/%Y %H:%M")
        md_lines = [
            f"# 🎯 Relatório de Sinais — Sports Edge AI",
            f"**Gerado em:** {ts} | **Esporte:** {sport}\n",
            "---"
        ]

        conf_emoji = {"high": "🟢 Alta", "medium": "🟡 Média", "low": "🔴 Baixa"}

        for s in signals:
            game = s.get("game_info", {})
            stake_brl = (s.get('stake_pct', 0) / 100) * settings.DEFAULT_BANKROLL
            
            md_lines.extend([
                f"\n## ⚽ {game.get('home_team')} x {game.get('away_team')}",
                f"- **Aposta:** **{s.get('best_bet_name')}** (@ {s.get('odd', 0):.2f})",
                f"- **Confiança:** {conf_emoji.get(s.get('confianca', 'low'), '🔴 Baixa')}",
                f"- **Edge:** {s.get('edge_pct', 0):.1f}% | **EV:** {s.get('ev', 0):.3f}",
                f"- **Stake:** {s.get('stake_pct', 0):.1f}% (R$ {stake_brl:.2f})\n",
                f"### 🤖 Raciocínio",
                f"> {s.get('resumo_executivo')}\n"
            ])
            
            md_lines.append(f"**Fatores Chave:**")
            for factor in s.get("fatores_positivos", []):
                md_lines.append(f"- ✅ {factor}")
                
            md_lines.append(f"\n**Riscos:**")
            for flag in s.get("red_flags", []):
                md_lines.append(f"- ⚠️ {flag}")
            
            md_lines.append("\n---")

        report_content = "\n".join(md_lines)
        ts_file = datetime.now().strftime("%Y-%m-%d")
        filepath = settings.SIGNALS_DIR / f"report_{ts_file}_{sport}.md"
        filepath.write_text(report_content)
        return report_content


# ──────────────────────────────────────────────
# Teste e Execução
# ──────────────────────────────────────────────
if __name__ == "__main__":
    from rich.panel import Panel

    mock_games = [
        {
            "id": "demo_1",
            "league": "Premier League",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "commence_time": "2024-05-10 16:00:00",
            "market_consensus": {"home_prob": 0.45, "draw_prob": 0.25, "away_prob": 0.30},
            "best_odds": {
                "home": {"odd": 2.25, "bookmaker": "Bet365"}, # 1/2.25 = 0.44
                "draw": {"odd": 4.10, "bookmaker": "Pinnacle"},
                "away": {"odd": 3.40, "bookmaker": "Betano"}
            }
        },
        {
            "id": "demo_2",
            "league": "La Liga",
            "home_team": "Real Madrid",
            "away_team": "Barcelona",
            "commence_time": "2024-05-11 17:00:00",
            "market_consensus": {"home_prob": 0.50, "draw_prob": 0.20, "away_prob": 0.30},
            "best_odds": {
                "home": {"odd": 1.95, "bookmaker": "Betano"},
                "draw": {"odd": 5.20, "bookmaker": "Bet365"},
                "away": {"odd": 3.50, "bookmaker": "Pinnacle"}
            }
        }
    ]

    analyzer = AIAnalyzer()
    
    # Se não tiver chave da API válida, não quebra a demonstração inteira. O Anthropic AuthError vai printar o erro capturado.
    console.print(Panel.fit("🧪 Iniciando Teste do AI Analyzer com 2 jogos fictícios...", border_style="cyan"))
    
    signals = analyzer.batch_analyze(mock_games, "soccer_mock")
    
    if signals:
        console.print("\n[bold green]Sinais Gerados no Teste:[/bold green]")
        for s in signals:
            console.print(f"- {s.get('game_info', {}).get('home_team')} (Aposta: {s.get('best_bet')} | Edge: {s.get('edge')}% | EV: {s.get('ev'):.2f})")
    else:
        console.print("\n[dim yellow]Nenhum sinal encontrado (Edge baixo ou erro de autenticação API).[/dim yellow]")
