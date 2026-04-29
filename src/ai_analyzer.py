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
import config

load_dotenv()
console = Console()

# Garante que os diretórios existam
config.SIGNALS_DIR.mkdir(parents=True, exist_ok=True)


class AIAnalyzer:
    """Usa IA (Cerebras) para calcular probabilidades justas e achar value bets."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.CEREBRAS_API_KEY
        if not self.api_key:
            console.print("[yellow]Aviso: CEREBRAS_API_KEY não definida no .env.[/yellow]")
        
        self.client = OpenAI(
            base_url="https://api.cerebras.ai/v1",
            api_key=self.api_key
        )
        self.model = config.CEREBRAS_MODEL

    def _extract_json(self, text: str) -> dict:
        """Limpa a resposta da IA para garantir a extração do JSON."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())

    # ──────────────────────────────────────────
    # Análise de Futebol
    # ──────────────────────────────────────────

    def analyze_football_game(self, game: dict[str, Any]) -> dict[str, Any]:
        """Constrói o prompt e analisa um jogo de futebol com Claude."""
        
        system_prompt = (
            "Você é um analista quantitativo especialista em apostas esportivas "
            "de valor esperado. Sua função é estimar probabilidades mais precisas que "
            "as odds do mercado com base em dados estatísticos e contextuais. "
            "Seja conservador: só recomende apostas com edge genuíno. "
            "Responda SOMENTE com JSON válido, sem markdown, sem texto adicional."
        )

        mc = game.get("market_consensus", {})
        best = game.get("best_odds", {})

        user_prompt = f"""Analise este jogo:

Jogo: {game.get('home_team')} vs {game.get('away_team')}
Competição: {game.get('league')}
Data/Hora (Brasília): {game.get('commence_time')}

Probabilidades implícitas do mercado (sem margem da casa):
- {game.get('home_team')} vence: {mc.get('home_prob', 0) * 100:.1f}%
- Empate: {mc.get('draw_prob', 0) * 100:.1f}%
- {game.get('away_team')} vence: {mc.get('away_prob', 0) * 100:.1f}%

Melhores odds disponíveis:
- {game.get('home_team')}: {best.get('home', {}).get('odd')} ({best.get('home', {}).get('bookmaker')})
- Empate: {best.get('draw', {}).get('odd')} ({best.get('draw', {}).get('bookmaker')})
- {game.get('away_team')}: {best.get('away', {}).get('odd')} ({best.get('away', {}).get('bookmaker')})

Com base no seu conhecimento sobre essas equipes e competição, forneça:

{{
  "home_prob": número entre 0 e 100,
  "draw_prob": número entre 0 e 100,
  "away_prob": número entre 0 e 100,
  "best_bet": "home" | "draw" | "away" | "skip",
  "edge": diferença entre sua probabilidade e a do mercado (pontos percentuais),
  "ev": expected value calculado = (sua_prob/100 * melhor_odd) - 1,
  "confidence": "low" | "medium" | "high",
  "reasoning": "explicação em máximo 3 frases diretas",
  "key_factors": ["até 4 fatores que justificam sua estimativa"],
  "red_flags": ["riscos que podem invalidar a análise"],
  "recommended_stake_pct": número (% da banca, máx 5)
}}

Regras: se edge < 6, retorne best_bet: "skip".
Se confidence for low, recommended_stake_pct não pode ser > 1.5."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            result = self._extract_json(response.choices[0].message.content)
            
            # Garante a regra manual caso a IA falhe
            if result.get("edge", 0) < 6:
                result["best_bet"] = "skip"
            if result.get("confidence") == "low" and result.get("recommended_stake_pct", 0) > 1.5:
                result["recommended_stake_pct"] = 1.5
                
            result["game_info"] = game
            return result
        except Exception as e:
            console.print(f"[red]Erro ao analisar jogo {game.get('home_team')}: {e}[/red]")
            return {"best_bet": "skip", "error": str(e), "game_info": game}

    # ──────────────────────────────────────────
    # Análise de Basquete (NBA)
    # ──────────────────────────────────────────

    def analyze_nba_game(self, game: dict[str, Any]) -> dict[str, Any]:
        """Constrói o prompt e analisa um jogo da NBA com Claude."""
        
        system_prompt = (
            "Você é um analista quantitativo especialista em apostas da NBA. "
            "Sua função é estimar probabilidades com base em estatísticas avançadas "
            "(pace, offensive/defensive rating, matchups, home/away splits) e "
            "contexto atual (back-to-backs, rest days, injury report). "
            "Responda SOMENTE com JSON válido, sem markdown, sem texto adicional."
        )

        mc = game.get("market_consensus", {})
        best = game.get("best_odds", {})

        user_prompt = f"""Analise este jogo da NBA:

Jogo: {game.get('home_team')} vs {game.get('away_team')}
Data/Hora (Brasília): {game.get('commence_time')}

Probabilidades implícitas do mercado Moneyline:
- {game.get('home_team')}: {mc.get('home_prob', 0) * 100:.1f}%
- {game.get('away_team')}: {mc.get('away_prob', 0) * 100:.1f}%

Melhores odds Moneyline:
- {game.get('home_team')}: {best.get('home', {}).get('odd')} ({best.get('home', {}).get('bookmaker')})
- {game.get('away_team')}: {best.get('away', {}).get('odd')} ({best.get('away', {}).get('bookmaker')})

Forneça:
{{
  "home_prob": número entre 0 e 100,
  "away_prob": número entre 0 e 100,
  "market_type": "moneyline" | "spread" | "total",
  "best_bet": "home" | "away" | "skip",
  "edge": diferença percentual (sua probabilidade vs mercado),
  "ev": expected value calculado = (sua_prob/100 * melhor_odd) - 1,
  "confidence": "low" | "medium" | "high",
  "reasoning": "explicação focada em pace, back-to-backs ou lesões chaves (máx 3 frases)",
  "key_factors": ["até 4 fatores justificando"],
  "red_flags": ["riscos de blowout, rest management ou lesões de última hora"],
  "recommended_stake_pct": número (% da banca, máx 5)
}}

Regras: se edge < 6, retorne best_bet: "skip".
Se confidence for low, recommended_stake_pct não pode ser > 1.5."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            result = self._extract_json(response.choices[0].message.content)
            
            if result.get("edge", 0) < 6:
                result["best_bet"] = "skip"
            if result.get("confidence") == "low" and result.get("recommended_stake_pct", 0) > 1.5:
                result["recommended_stake_pct"] = 1.5
                
            result["game_info"] = game
            return result
        except Exception as e:
            console.print(f"[red]Erro ao analisar jogo da NBA {game.get('home_team')}: {e}[/red]")
            return {"best_bet": "skip", "error": str(e), "game_info": game}

    # ──────────────────────────────────────────
    # Processamento em Lote
    # ──────────────────────────────────────────

    def batch_analyze(self, games: list[dict], sport: str) -> list[dict]:
        """Analisa uma lista de jogos, com delay e filtragem automática."""
        results = []
        
        console.print(f"\n[cyan]🤖 Iniciando análise de {len(games)} jogos via Claude AI...[/cyan]")
        
        import time
        for idx, game in enumerate(games, 1):
            title = f"{game.get('home_team')} x {game.get('away_team')}"
            console.print(f"[dim]({idx}/{len(games)}) Analisando: {title}...[/dim]")
            
            game_sport = game.get("sport", "")
            if "soccer" in game_sport:
                res = self.analyze_football_game(game)
            elif "basketball" in game_sport:
                res = self.analyze_nba_game(game)
            else:
                continue

            if res.get("best_bet") != "skip":
                results.append(res)
            
            time.sleep(1) # Delay para evitar rate limits
            
        # Ordena por EV decrescente
        results = sorted(results, key=lambda x: x.get("ev", 0), reverse=True)
        
        # Salvar em arquivo
        if results:
            ts = datetime.now().strftime("%Y-%m-%d")
            filepath = config.SIGNALS_DIR / f"signals_{ts}_{sport.replace('_', '')}.json"
            filepath.write_text(json.dumps(results, ensure_ascii=False, indent=2))
            console.print(f"[bold green]✓ {len(results)} sinais encontrados! Salvos em {filepath}[/bold green]")
            
            self.format_signal_report(results, sport)
            
        return results

    # ──────────────────────────────────────────
    # Formatação e Relatórios
    # ──────────────────────────────────────────

    def format_signal_report(self, signals: list[dict], sport: str) -> str:
        """Gera um relatório Markdown bonito e acionável."""
        if not signals:
            return ""
            
        ts = datetime.now().strftime("%d/%m/%Y %H:%M")
        md_lines = [
            f"# 🎯 Relatório de Sinais de Aposta — Sports Edge AI",
            f"**Gerado em:** {ts} | **Esporte:** {sport}",
            f"**Banca Padrão Assumida:** R$ {config.DEFAULT_BANKROLL:.2f}\n",
            "---"
        ]

        conf_emoji = {"high": "🟢 Alta", "medium": "🟡 Média", "low": "🔴 Baixa"}

        for s in signals:
            game = s.get("game_info", {})
            bet = s.get("best_bet")
            team_bet = game.get(f"{bet}_team") if bet in ["home", "away"] else "Empate"
            odd_info = game.get("best_odds", {}).get(bet, {})
            odd_val = odd_info.get("odd", 0)
            book = odd_info.get("bookmaker", "Desconhecido")
            
            stake_pct = s.get("recommended_stake_pct", 0)
            stake_brl = (stake_pct / 100) * config.DEFAULT_BANKROLL
            
            md_lines.extend([
                f"\n## ⚽ {game.get('home_team')} x {game.get('away_team')}",
                f"- **Aposta Recomendada:** **{team_bet}** (@ {odd_val:.2f})",
                f"- **Confiança IA:** {conf_emoji.get(s.get('confidence', 'low'), '🔴 Baixa')}",
                f"- **Edge Encontrado:** {s.get('edge', 0):.1f}% | **EV:** {s.get('ev', 0):.3f}",
                f"- **Stake Sugerido:** {stake_pct:.1f}% da banca (R$ {stake_brl:.2f})\n",
                f"### 🤖 Raciocínio",
                f"> {s.get('reasoning')}\n",
                f"**Fatores Chave:**"
            ])
            
            for factor in s.get("key_factors", []):
                md_lines.append(f"- ✅ {factor}")
                
            md_lines.append(f"\n**Riscos (Red Flags):**")
            for flag in s.get("red_flags", []):
                md_lines.append(f"- ⚠️ {flag}")
                
            md_lines.extend([
                f"\n### 💰 Onde Apostar",
                f"Melhor preço encontrado em: **{book}** (@ {odd_val:.2f})",
                "---"
            ])

        md_lines.extend([
            "\n> ⚠️ **Aviso Final:** Esta é uma análise de IA quantitativa. A decisão final de apostar é 100% sua. Aposte com responsabilidade."
        ])

        report_content = "\n".join(md_lines)
        
        # Salva o arquivo markdown
        ts_file = datetime.now().strftime("%Y-%m-%d")
        filepath = config.SIGNALS_DIR / f"report_{ts_file}_{sport.replace('_', '')}.md"
        filepath.write_text(report_content)
        
        console.print(f"[dim]Relatório Markdown gerado: {filepath}[/dim]")
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
