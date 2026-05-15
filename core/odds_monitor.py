import asyncio
from datetime import datetime, time
from sqlalchemy import select
from core.database import AsyncSessionLocal, Sinal, OddsSnapshot, DataService
from src.odds_fetcher import OddsFetcher
from core.logger import logger, monitored_job

class OddsMonitor:
    def __init__(self):
        self.fetcher = OddsFetcher()

    @monitored_job("Monitoramento de Smart Money")
    async def run_monitoring(self):
        # Só executa entre 08:00 e 22:00
        now = datetime.now().time()
        if not (time(8, 0) <= now <= time(22, 0)):
            return

        async with AsyncSessionLocal() as session:
            # 1. Busca sinais pendentes para jogos que ainda não começaram
            q = select(Sinal).where(Sinal.resultado == 'pendente')
            res = await session.execute(q)
            sinais = res.scalars().all()

            for sinal in sinais:
                # Busca odds atuais na API
                # (Simplificado: assumindo que o fetcher consegue buscar por ID ou esporte)
                current_odds = await self.fetcher.get_upcoming_games(sinal.esporte)
                
                # Procura o jogo específico pelo api_game_id
                game_data = next((g for g in current_odds if g['id'] == sinal.api_game_id), None)
                
                if game_data:
                    # Salva Snapshot
                    best_h2h = game_data['best_odds']['h2h']
                    snap = OddsSnapshot(
                        sinal_id=sinal.id,
                        odd_home=best_h2h['casa']['odd'],
                        odd_draw=best_h2h['empate']['odd'] if 'empate' in best_h2h else None,
                        odd_away=best_h2h['fora']['odd'],
                        bookmaker=best_h2h['casa']['bookmaker']
                    )
                    session.add(snap)
                    
                    # Analisa Movimento
                    await self._analyze_movement(session, sinal, snap)
            
            await session.commit()

    async def _analyze_movement(self, session, sinal: Sinal, current_snap: OddsSnapshot):
        # Busca o snapshot de abertura (o primeiro do dia)
        q = select(OddsSnapshot).where(
            OddsSnapshot.sinal_id == sinal.id
        ).order_by(OddsSnapshot.capturado_em.asc()).limit(1)
        
        res = await session.execute(q)
        opening_snap = res.scalar_one_or_none()
        
        if not opening_snap or opening_snap.id == current_snap.id:
            return

        # Calcula variação na odd que foi recomendada (ex: Casa)
        # Assumindo que o sinal foi para o Home Team
        old_odd = opening_snap.odd_home
        new_odd = current_snap.odd_home
        
        if old_odd > 0:
            variation = (new_odd - old_odd) / old_odd
            
            # REGRAS DE SMART MONEY
            if variation > 0.08:
                # Odd subiu (mercado rejeitando)
                sinal.confianca = float(sinal.confianca) * 0.8
                logger.warning("smart_money_contra", sinal_id=sinal.id, var=f"{variation:.1%}")
            elif variation < -0.08:
                # Odd caiu (smart money entrando)
                sinal.confianca = float(sinal.confianca) * 1.15
                logger.info("smart_money_favor", sinal_id=sinal.id, var=f"{variation:.1%}")
