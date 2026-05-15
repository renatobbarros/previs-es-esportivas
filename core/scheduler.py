import asyncio
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timezone, timedelta
from pytz import timezone as pytz_tz
from config import settings
from core.logger import logger, monitored_job

from core.database import DatabaseManager
from core.ai_orchestrator import AIOrchestrator
from src.odds_fetcher import OddsFetcher
from src.pandascore_fetcher import PandaScoreFetcher
from core.telegram_bot import SportsEdgeBot
from core.kelly import KellyManager
from sports.football import FootballAnalyzer
from sports.basketball import BasketballAnalyzer

class SportsEdgeScheduler:
    def __init__(self):
        self.db = DatabaseManager()
        self.ai = AIOrchestrator()
        self.fetcher = OddsFetcher()
        self.panda = PandaScoreFetcher()
        self.bot = SportsEdgeBot(self.db)
        self.kelly = KellyManager()
        self.foot = FootballAnalyzer(self.db)
        self.basket = BasketballAnalyzer(self.db)
        self.scheduler = AsyncIOScheduler(timezone=pytz_tz('America/Sao_Paulo'))

    @monitored_job("Pipeline de Análise Diária")
    async def daily_pipeline(self):
        log = logger.bind(sport="multi")
        log.info("pipeline_started", msg="🌅 Iniciando pipeline de análise...")
        
        # 1. Coleta todos os jogos de todas as fontes
        leagues = ["soccer_epl", "soccer_brazil_campeonato", "basketball_nba"]
        all_raw_games = []
        
        for league in leagues:
            logger.info(f"🔍 Buscando jogos para {league}...")
            games = await self.fetcher.get_upcoming_games(league)
            for g in games:
                g['source_league'] = league # Tag para saber o esporte depois
                all_raw_games.append(g)

        logger.info("🎮 Buscando E-sports via PandaScore...")
        esports_games = await self.panda.get_upcoming_matches()
        for g in esports_games:
            g['source_league'] = 'esports'
            all_raw_games.append(g)

        # 2. Ordena por horário (Cronológico)
        all_raw_games.sort(key=lambda x: x['commence_time'])

        # 3. Processa e Filtra
        tz_br = pytz_tz('America/Sao_Paulo')
        now_br = datetime.now(tz_br)
        end_of_today = now_br.replace(hour=23, minute=59, second=59, microsecond=999999)

        for game in all_raw_games:
            game_time_utc = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
            game_time_br = game_time_utc.astimezone(tz_br)
            
            # FILTRO: Apenas o que acontece HOJE (até 23:59)
            if game_time_br > end_of_today:
                continue
            
            # Pula jogos que já começaram
            if game_time_br < now_br:
                continue

            # 1. Salva jogo no banco
            self.db.save_game(game)
            
            # 2. Verifica se sinal já existe
            if self.db.signal_exists(game['id']):
                continue
            
            # 3. Triagem e Análise IA
            game_id = game['id']
            league = game['source_league']
            sport_type = "esports" if league == "esports" else ("football" if "soccer" in league else "basketball")
            
            # Prepara dados (simplificado para triagem)
            if league == "esports":
                best_h, best_a = 1.85, 1.85 # Placeholder Panda
            else:
                best_h = game['best_odds']['h2h']['casa']['odd']
                best_a = game['best_odds']['h2h']['fora']['odd']
            
            if best_h < 1.1: continue

            analysis_data = {
                "id": game_id,
                "home_team": game['home_team'],
                "away_team": game['away_team'],
                "odds": f"Casa: {best_h}, Fora: {best_a}",
                "math_prob": "Triagem Automatizada"
            }
            
            result = await self.ai.run_full_pipeline(analysis_data, sport_type)
            
            min_edge = 0.05 if sport_type == "esports" else settings.MIN_EDGE_THRESHOLD
            
            if result.get('edge', 0) > min_edge:
                # Calcula Kelly e Stake baseada na banca real (R$ 20.00)
                bankroll = self.db.get_bankroll()['balance']
                kelly_res = self.kelly.calculate_kelly(result['ai_probability'], best_h)
                
                signal_data = {
                    "api_game_id": game['id'],
                    "api_source": "pandascore" if sport_type == "esports" else "theodds",
                    "game_id": game_id,
                    "sport": sport_type,
                    "league": game.get('league', league),
                    "match_description": f"{game['home_team']} x {game['away_team']}",
                    "market": "Winner" if sport_type == "esports" else "Vencedor (ML)",
                    "outcome": game['home_team'],
                    "recommended_odds": best_h,
                    "ai_probability": result['ai_probability'],
                    "market_probability": 1/best_h,
                    "edge_percent": result['edge'],
                    "ev_percent": kelly_res['ev_percent'],
                    "confidence_score": result['confidence'],
                    "kelly_stake_percent": kelly_res['suggested_stake_pct'],
                    "suggested_stake_units": kelly_res['suggested_stake_pct'] * bankroll,
                    "model_used": result['model_used'],
                    "signal_quality": self.kelly.get_signal_grade(result['edge'], result['confidence']),
                    "expires_at": game['commence_time']
                }
                
                signal_id = self.db.save_signal(signal_data)
                signal_data['id'] = signal_id
                logger.success(f"🎯 SINAL GERADO: {signal_data['match_description']} - Horário: {game_time_br.strftime('%H:%M')}")
                
                # Envia para o Telegram
                await self.bot.send_signal(signal_data)
                log.info("signal_pushed", game=signal_data['match_description'])

    async def start(self):
        # 1. Roda a análise única do dia imediatamente se for a primeira vez
        # ou agenda para rodar todo dia às 08:00
        self.scheduler.add_job(
            self.daily_pipeline, 
            'cron', 
            hour=8, 
            minute=0, 
            id="daily_analysis"
        )
        
        # 2. Agenda a liquidação de resultados para as 23:30
        from core.settler import SportsEdgeSettler
        settler = SportsEdgeSettler(self.db)
        self.scheduler.add_job(
            settler.run_settlement, 
            'cron', 
            hour=23, 
            minute=30, 
            id="daily_settlement"
        )

        # 3. Fechamento de Ciclo Semanal (Comissões) - Domingo 23:00
        from core.comissao import CommissionManager, get_all_active_users_ids
        async def weekly_billing():
            uids = await get_all_active_users_ids()
            for uid in uids:
                stats, ciclo = await CommissionManager.fechar_ciclo_usuario(uid)
                # Notificação enviada via bot (precisaria injetar o bot aqui ou usar o sender global)
        
        self.scheduler.add_job(
            weekly_billing,
            'cron',
            day_of_week='sun',
            hour=23,
            minute=0,
            id="weekly_billing"
        )

        # 4. Report Semanal de Performance (Backtest) - Segunda 09:00
        async def weekly_performance_report():
            from core.backtesting import BacktestManager
            inicio = datetime.now() - timedelta(days=7)
            fim = datetime.now()
            results = await BacktestManager.run_backtest(inicio, fim)
            msg = BacktestManager.format_report(results)
            await self.bot.app.bot.send_message(
                chat_id=settings.OWNER_TELEGRAM_ID,
                text=f"<b>📈 RELATÓRIO SEMANAL DE PERFORMANCE</b>\n\n{msg}",
                parse_mode=ParseMode.HTML
            )

        self.scheduler.add_job(
            weekly_performance_report,
            'cron',
            day_of_week='mon',
            hour=9,
            minute=0,
            id="weekly_performance_report"
        )
        
        # 5. Monitoramento de Smart Money (Odds) - A cada 2h (08:00 - 22:00)
        from core.odds_monitor import OddsMonitor
        monitor = OddsMonitor()
        self.scheduler.add_job(
            monitor.run_monitoring,
            'interval',
            hours=2,
            id="odds_monitoring"
        )
        
        # Roda uma vez agora para garantir que temos dados hoje
        await self.daily_pipeline()
        
        self.scheduler.start()
        logger.info("🚀 Sistema configurado para modo PROFISSIONAL (Análise às 08:00 | Liquidação às 23:30)")
        
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    scheduler = SportsEdgeScheduler()
    asyncio.run(scheduler.start())
