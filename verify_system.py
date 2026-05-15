import asyncio
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

# Adiciona o diretório raiz ao path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import settings
from src.odds_fetcher import OddsFetcher
from src.ai_analyzer import AIAnalyzer
from src.telegram_bot import send_telegram_message

console = Console()

async def run_full_audit():
    console.rule("[bold cyan]🔍 AUDITORIA COMPLETA DO SISTEMA")
    
    results = []
    
    # 1. Pastas e Arquivos
    dirs = [settings.DATA_DIR, settings.SIGNALS_DIR, settings.HISTORICAL_DIR]
    for d in dirs:
        status = "✅ OK" if d.exists() else "❌ Criando..."
        if not d.exists(): d.mkdir(parents=True)
        results.append(["Estrutura", d.name, status])

    # 2. Conexão APIs
    fetcher = OddsFetcher()
    try:
        # Tenta uma busca leve
        games = await fetcher.get_upcoming_games(settings.FOOTBALL_LEAGUES[0])
        results.append(["API Dados", "The Odds API", "✅ Online" if games or fetcher.is_demo else "⚠️ Vazio"])
    except Exception as e:
        results.append(["API Dados", "The Odds API", f"❌ Erro: {str(e)[:20]}"])

    # 3. IA Check (Novo Formato)
    try:
        analyzer = AIAnalyzer()
        # Mock de jogo para teste de prompt
        mock_game = {"home_team": "Test H", "away_team": "Test A", "league": "Test L", "best_odds": {"h2h": {"casa": 2.0}}, "market_consensus": {"h2h": {"casa_prob": 0.5}}}
        res = await analyzer.analyze_football_game(mock_game, context="teste de integridade")
        results.append(["API IA", settings.GROQ_MODEL, "✅ Operacional" if "prob_real" in res else "⚠️ Resposta Estranha"])
    except Exception as e:
        results.append(["API IA", "Groq", f"❌ Falha: {str(e)[:20]}"])

    # 4. Telegram Check
    test_msg = "🚨 *Auditoria Sports Edge AI:* Sistema otimizado e 100% operacional."
    success = await send_telegram_message(test_msg)
    results.append(["Comunicação", "Telegram Bot", "✅ Enviado" if success else "❌ Falha no Token/ChatID"])

    # Exibe Tabela
    table = Table(title="Status de Verificação")
    table.add_column("Categoria")
    table.add_column("Componente")
    table.add_column("Resultado")
    
    for res in results:
        table.add_row(*res)
    
    console.print(table)
    
    if all("✅" in r[2] for r in results):
        console.print("\n[bold green]🚀 SISTEMA 100% OPERACIONAL![/bold green]")
        return True
    else:
        console.print("\n[bold yellow]⚠️ Sistema operacional com alertas. Verifique os logs.[/bold yellow]")
        return False

if __name__ == "__main__":
    asyncio.run(run_full_audit())
