"""
news_monitor.py — Monitor Inteligente de Notícias Esportivas
Filtra feeds RSS usando a IA (Claude) para detectar impactos nas odds.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI
import feedparser
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Adiciona o diretório raiz ao path para importar config
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import config

load_dotenv()
console = Console()

config.DATA_DIR.mkdir(parents=True, exist_ok=True)
URGENT_ALERTS_FILE = config.DATA_DIR / "urgent_alerts.json"
NEWS_ALERTS_FILE = config.DATA_DIR / "news_alerts.json"

class NewsMonitor:
    """Monitora feeds RSS e tria notícias de alto impacto via Claude."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.CEREBRAS_API_KEY
        if not self.api_key:
            console.print("[yellow]Aviso: CEREBRAS_API_KEY não definida no .env.[/yellow]")
        
        self.client = OpenAI(base_url="https://api.cerebras.ai/v1", api_key=self.api_key)
        self.model = config.CEREBRAS_MODEL

        self.rss_sources = {
            "football": [
                "https://ge.globo.com/rss/feed.xml",
                "https://www.lance.com.br/feed",
                "https://www.espn.com.br/espn/rss/futebol/noticias",
                "https://www.bbc.com/sport/football/rss.xml",
                "https://feeds.skysports.com/football/news.rss"
            ],
            "nba": [
                "https://www.espn.com/espn/rss/nba/news",
                "https://bleacherreport.com/nba.rss"
            ]
        }
        
        # Histórico em memória para não triar duas vezes no mesmo ciclo de vida
        self._seen_urls = set()

    def _extract_json(self, text: str) -> dict:
        """Limpa a resposta da IA para extrair apenas o JSON."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())

    # ──────────────────────────────────────────
    # Extração
    # ──────────────────────────────────────────

    def fetch_recent_news(self, hours: int = 2) -> list[dict[str, Any]]:
        """Busca notícias das últimas X horas e deduplica."""
        console.print(f"[dim]Buscando feeds RSS das últimas {hours}h...[/dim]")
        
        recent_news = []
        seen_titles = set()
        
        # Define UTC timezone explícito para garantir consistência
        now_utc = datetime.now(timezone.utc)
        cutoff_time = now_utc - timedelta(hours=hours)

        for sport, feeds in self.rss_sources.items():
            for feed_url in feeds:
                try:
                    feed = feedparser.parse(feed_url)
                    for entry in feed.entries:
                        title = getattr(entry, "title", "").strip()
                        if not title or title in seen_titles:
                            continue
                            
                        # Extrai data de publicação (usando tuple padrão do feedparser)
                        # Se não tiver, assume agora
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        else:
                            pub_dt = now_utc
                            
                        if pub_dt >= cutoff_time:
                            # Converte para horário de Brasília (UTC-3)
                            tz_br = timezone(timedelta(hours=-3))
                            pub_br = pub_dt.astimezone(tz_br)
                            
                            news_item = {
                                "sport_category": sport,
                                "title": title,
                                "summary": getattr(entry, "summary", getattr(entry, "description", "")).strip()[:500],
                                "source": getattr(feed.feed, "title", feed_url),
                                "url": getattr(entry, "link", ""),
                                "published_at": pub_br.strftime("%Y-%m-%d %H:%M:%S")
                            }
                            
                            recent_news.append(news_item)
                            seen_titles.add(title)
                except Exception as e:
                    console.print(f"[dim red]Erro ao processar feed {feed_url}: {e}[/dim red]")
                    
        return recent_news

    # ──────────────────────────────────────────
    # Triagem via Inteligência Artificial
    # ──────────────────────────────────────────

    def triage_news(self, news_item: dict[str, Any]) -> dict[str, Any]:
        """Envia para o Claude classificar o impacto nas odds."""
        
        system_prompt = (
            "Você filtra notícias esportivas para identificar quais têm "
            "impacto imediato em odds de apostas. Seja conservador: só marque como "
            "relevante o que genuinamente muda probabilidades nas próximas 48h. "
            "Responda SOMENTE com JSON válido."
        )

        user_prompt = f"""Notícia: {news_item['title']} — {news_item['summary']}

Esta notícia afeta odds de jogos nas próximas 48h?

Eventos relevantes para odds:
- Lesão/suspensão de titular confirmada
- Escalação muito diferente do esperado
- Demissão/troca de treinador
- Jogador estrela descartado no dia do jogo (NBA: injury report)
- Resultado que muda dramaticamente o contexto (rebaixamento iminente)

{{
  "relevant": true/false,
  "teams_affected": ["time1"],
  "sport": "football" | "nba" | "other",
  "impact": "favorece_casa" | "favorece_visitante" | "mais_gols" | "menos_gols" | "neutro",
  "urgency": "alta" | "media" | "baixa",
  "action": "descrição em 1 frase de como explorar nas apostas",
  "reasoning": "1 frase explicando o impacto"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=300,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            result = self._extract_json(response.choices[0].message.content)
            
            # Mescla info da notícia com o resultado da IA
            return {**news_item, **result}
        except Exception as e:
            console.print(f"[dim red]Erro na triagem da notícia ({news_item['title'][:30]}): {e}[/dim red]")
            return {"relevant": False, "error": str(e)}

    # ──────────────────────────────────────────
    # Salvamento de Alertas
    # ──────────────────────────────────────────

    def _save_alert(self, data: dict, file_path: Path):
        """Adiciona um alerta no JSON mantendo o histórico recente."""
        alerts = []
        if file_path.exists():
            try:
                alerts = json.loads(file_path.read_text())
            except Exception:
                pass
                
        # Evitar duplicados exatos pelo URL
        if not any(a.get("url") == data.get("url") for a in alerts):
            alerts.insert(0, data)
            # Manter limite (ex: 100 alertas)
            alerts = alerts[:100]
            file_path.write_text(json.dumps(alerts, ensure_ascii=False, indent=2))

    # ──────────────────────────────────────────
    # Ciclo do Monitor
    # ──────────────────────────────────────────

    def run_cycle(self):
        """Executa um ciclo completo de busca e triagem."""
        console.print("\n[bold cyan]🔄 Iniciando ciclo de busca de notícias...[/bold cyan]")
        
        # Hora de Brasília
        tz_br = timezone(timedelta(hours=-3))
        agora = datetime.now(tz_br).strftime("%Y-%m-%d %H:%M:%S")
        
        news_list = self.fetch_recent_news(hours=2)
        novas_noticias = [n for n in news_list if n["url"] not in self._seen_urls]
        
        if not novas_noticias:
            console.print("[dim]Sem novas notícias no momento.[/dim]")
            return

        relevantes_encontradas = 0
        
        for news in novas_noticias:
            self._seen_urls.add(news["url"])
            triage_result = self.triage_news(news)
            
            if not triage_result.get("relevant", False):
                continue
                
            relevantes_encontradas += 1
            urgencia = triage_result.get("urgency", "baixa").lower()
            
            times = ", ".join(triage_result.get("teams_affected", []))
            msg = f"[{agora}] {news['title']}\nImpacto: {triage_result.get('impact')} | Times: {times}\nAção: {triage_result.get('action')}"
            
            if urgencia == "alta":
                console.print(Panel.fit(msg, title="🚨 ALERTA ALTA URGÊNCIA", border_style="red", style="red"))
                self._save_alert(triage_result, URGENT_ALERTS_FILE)
            elif urgencia == "media":
                console.print(Panel.fit(msg, title="⚠️ ALERTA MÉDIA URGÊNCIA", border_style="yellow", style="yellow"))
                self._save_alert(triage_result, NEWS_ALERTS_FILE)
            else:
                # Urgência baixa ou neutra, salva mas não pinta colorido chamativo
                console.print(f"🔹 [dim]Relevante (Baixa): {news['title']}[/dim]")
                self._save_alert(triage_result, NEWS_ALERTS_FILE)

        if relevantes_encontradas == 0:
            console.print("[green]Nenhum evento com impacto nas odds identificado neste ciclo.[/green]")

# ──────────────────────────────────────────────
# Agendador
# ──────────────────────────────────────────────

def start_scheduler(interval_minutes: int = 30):
    monitor = NewsMonitor()
    scheduler = BlockingScheduler()
    
    # Função wrapper para o job
    def job_tick():
        monitor.run_cycle()
        tz_br = timezone(timedelta(hours=-3))
        next_run = (datetime.now(tz_br) + timedelta(minutes=interval_minutes)).strftime("%H:%M")
        console.print(f"[bold green]✅ Monitor ativo — próxima verificação em {interval_minutes}min (às {next_run} BRT)[/bold green]")

    # Roda a primeira vez na hora
    job_tick()
    
    # Agenda as próximas
    scheduler.add_job(
        job_tick, 
        trigger=IntervalTrigger(minutes=interval_minutes)
    )
    
    console.print(f"[bold cyan]⏳ Scheduler APScheduler ativado (Intervalo: {interval_minutes}m)... Pressione Ctrl+C para sair.[/bold cyan]")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        console.print("[dim]Monitoramento encerrado.[/dim]")

if __name__ == "__main__":
    start_scheduler(interval_minutes=30)
