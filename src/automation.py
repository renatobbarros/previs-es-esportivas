"""
src/automation.py — Motor de Automação do Sports Edge AI
Executa a busca de odds e análise de IA periodicamente em segundo plano.
"""
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

import config
from src.odds_fetcher import OddsFetcher
from src.ai_analyzer import AIAnalyzer

console = Console()

async def run_full_pipeline():
    """Executa o fluxo completo: Busca -> Cálculo EV -> Análise IA -> Relatório."""
    tz_br = timezone(timedelta(hours=-3))
    now = datetime.now(tz_br).strftime("%H:%M:%S")
    
    console.print(f"\n[bold magenta]🚀 [{now}] Iniciando Pipeline Automático...[/bold magenta]")
    
    try:
        # 1. Busca Odds
        fetcher = OddsFetcher()
        analyzer = AIAnalyzer()
        
        all_games = []
        for sport in config.ALL_LEAGUES:
            console.print(f"[dim]Buscando odds para {sport}...[/dim]")
            games = await fetcher.get_upcoming_games(sport)
            if games:
                all_games.extend(games)
        
        if not all_games:
            console.print("[yellow]Nenhum jogo encontrado nas APIs no momento.[/yellow]")
            return

        # 2. Analisa com IA (apenas o que tem edge ou interesse)
        # O batch_analyze já filtra e salva os sinais
        console.print(f"[green]Total de {len(all_games)} jogos encontrados. Enviando para triagem da IA...[/green]")
        analyzer.batch_analyze(all_games, "automated_sync")
        
        console.print(f"[bold green]✅ Pipeline concluído com sucesso às {datetime.now(tz_br).strftime('%H:%M:%S')}![/bold green]")
        
    except Exception as e:
        console.print(f"[bold red]❌ Erro crítico no pipeline: {e}[/bold red]")

def start_automation(interval_hours: int = 2):
    """Inicia o agendador de tarefas."""
    scheduler = BlockingScheduler()
    
    import asyncio
    
    def sync_wrapper():
        asyncio.run(run_full_pipeline())

    # Roda a primeira vez imediatamente
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
