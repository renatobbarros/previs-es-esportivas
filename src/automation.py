"""
src/automation.py — Motor de Automação do Sports Edge AI
Executa a busca de odds e análise de IA periodicamente em segundo plano.
"""
import json
import sys
import time

from datetime import datetime, timezone, timedelta
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from rich.console import Console

# Adiciona o diretório raiz ao path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import settings
from src.odds_fetcher import OddsFetcher
from src.ai_analyzer import AIAnalyzer
from src.telegram_bot import send_signal_alert

console = Console()

async def run_full_pipeline():
    """Executa o fluxo completo: Busca -> Cálculo EV -> Análise IA -> Relatório."""
    tz_br = timezone(timedelta(hours=-3))
    now = datetime.now(tz_br).strftime("%H:%M:%S")
    
    console.print(f"\n[bold magenta]🚀 [{now}] Iniciando Pipeline Automático...[/bold magenta]")
    
    try:
        # 1. Busca Odds em Paralelo
        from src.ev_calculator import EVCalculator
        fetcher = OddsFetcher()
        analyzer = AIAnalyzer()
        calculator = EVCalculator()
        
        async def fetch_sport(sport):
            console.print(f"[dim]Buscando odds para {sport}...[/dim]")
            return await fetcher.get_upcoming_games(sport)

        tasks = [fetch_sport(s) for s in settings.ALL_LEAGUES if s != "esports"]
        league_results = await asyncio.gather(*tasks)
        
        all_games = []
        for games in league_results:
            if games: all_games.extend(games)
        
        if not all_games:
            console.print("[yellow]Nenhum jogo encontrado nas APIs no momento.[/yellow]")
            return

        # 2. Prepara Contexto de Notícias
        urgent_path = settings.DATA_DIR / "urgent_alerts.json"
        news_path = settings.DATA_DIR / "news_alerts.json"
        
        all_alerts = []
        if urgent_path.exists():
            with open(urgent_path, 'r') as f: all_alerts.extend(json.load(f))
        if news_path.exists():
            with open(news_path, 'r') as f: all_alerts.extend(json.load(f))
            
        game_contexts = {}
        for game in all_games:
            relevant_news = []
            home = game.get("home_team", "").lower()
            away = game.get("away_team", "").lower()
            
            for alert in all_alerts:
                affected = [t.lower() for t in alert.get("teams_affected", [])]
                if any(t in home or home in t for t in affected) or any(t in away or away in t for t in affected):
                    news_text = f"[{alert.get('urgency', 'info').upper()}] {alert.get('title')}: {alert.get('impact')} - {alert.get('action')}"
                    relevant_news.append(news_text)
            
            if relevant_news:
                game_contexts[game["id"]] = "\n".join(relevant_news)

        # 3. Triagem e Análise com IA
        console.print(f"[green]Total de {len(all_games)} jogos encontrados. Iniciando triagem...[/green]")
        triaged_games = calculator.triage_games(all_games, news_contexts=game_contexts)
        
        if not triaged_games:
            console.print("[yellow]Nenhum jogo passou na triagem de valor/contexto.[/yellow]")
            return

        # Análise de IA em lote (Paralela e Rápida)
        ai_raw_results = await analyzer.batch_analyze(triaged_games, "automated_sync", contexts=game_contexts)
        
        # 4. Cálculo Matemático Rigoroso (Sem Alucinação)
        final_signals = calculator.apply_ai_results(ai_raw_results)

        # 5. Relatórios e Alertas
        if final_signals:
            await analyzer.format_signal_report(final_signals, "Múltiplos")
            console.print(f"[bold cyan]📲 Enviando {len(final_signals)} alertas para o Telegram...[/bold cyan]")
            for signal in final_signals:
                await send_signal_alert(signal)

        
        console.print(f"[bold green]✅ Pipeline concluído com sucesso às {datetime.now(tz_br).strftime('%H:%M:%S')}![/bold green]")
        
    except Exception as e:
        console.print(f"[bold red]❌ Erro crítico no pipeline: {e}[/bold red]")

def start_automation(interval_hours: int = 2):
    """Inicia o agendador de tarefas."""
    scheduler = BlockingScheduler()
    
    import asyncio
    
    def sync_wrapper():
        asyncio.run(run_full_pipeline())

    # Roda a primeira vez imediatamente de forma forçada
    console.print("[bold yellow]⚡ Executando triagem inicial imediata...[/bold yellow]")
    sync_wrapper()
    
    # Agenda para rodar a cada X horas
    scheduler.add_job(
        sync_wrapper,
        trigger=IntervalTrigger(hours=interval_hours),
        id="full_pipeline_job"
    )
    
    console.print(f"\n[bold green]🤖 Automação ATIVA.[/bold green]")
    console.print(f"[cyan]O sistema irá buscar e analisar jogos automaticamente a cada {interval_hours} hora(s).[/cyan]")
    console.print("[dim]Pressione Ctrl+C para encerrar o motor de automação.[/dim]\n")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        console.print("[yellow]Automação encerrada pelo usuário.[/yellow]")

if __name__ == "__main__":
    # Se quiser testar rápido, mude para minutes=1
    start_automation(interval_hours=2)
