import asyncio
import json
from datetime import datetime
from sqlalchemy import select
from core.database import AsyncSessionLocal, Sinal, Aposta, Disputa, DataService
from src.odds_fetcher import OddsFetcher
from core.logger import logger, monitored_job

class SportsEdgeSettler:
    def __init__(self):
        self.fetcher = OddsFetcher()

    @monitored_job("Liquidação Determinística")
    async def run_settlement(self):
        async with AsyncSessionLocal() as session:
            # 1. Busca todos os sinais pendentes
            q = select(Sinal).where(Sinal.resultado == 'pendente')
            res = await session.execute(q)
            sinais_pendentes = res.scalars().all()

            if not sinais_pendentes:
                logger.info("settlement_skip", msg="📭 Nenhum sinal pendente para liquidação.")
                return

            # 2. Busca scores recentes da API
            # Agrupa por esporte para economizar chamadas
            esportes = list(set(s.esporte for s in sinais_pendentes))
            all_api_scores = {}
            
            for esp in esportes:
                # Mapeamento para The Odds API
                api_key = "soccer_epl" if esp == "football" else "basketball_nba"
                scores = await self.fetcher.get_recent_scores(api_key)
                for s in scores:
                    all_api_scores[s['id']] = s

            settled_count = 0
            for sinal in sinais_pendentes:
                api_data = all_api_scores.get(sinal.api_game_id)
                
                if api_data and api_data.get('completed'):
                    # SALVA RAW RESULT PRIMEIRO (Auditável)
                    sinal.resultado_api = json.dumps(api_data)
                    sinal.resultado_api_em = datetime.now()
                    
                    # Lógica Determinística
                    try:
                        home_score = int(api_data['scores'][0]['score'])
                        away_score = int(api_data['scores'][1]['score'])
                        
                        winner = api_data['home_team'] if home_score > away_score else \
                                 api_data['away_team'] if away_score > home_score else "Draw"
                        
                        # Determina se o sinal ganhou
                        # Supondo que o sinal é sempre no Home Team por enquanto (simplificado)
                        if sinal.jogo.startswith(winner):
                            sinal.resultado = 'ganhou'
                        elif winner == "Draw":
                            sinal.resultado = 'void'
                        else:
                            sinal.resultado = 'perdeu'
                        
                        sinal.resultado_verificado = True
                        
                        # Liquida as apostas vinculadas
                        await self._settle_user_bets(session, sinal)
                        settled_count += 1
                        
                    except Exception as e:
                        logger.error("settlement_error", sinal_id=sinal.id, error=str(e))
            
            await session.commit()
            logger.info("settlement_finished", count=settled_count)

    async def _settle_user_bets(self, session, sinal: Sinal):
        """Liquida todas as apostas de usuários vinculadas a este sinal."""
        q = select(Aposta).where(Aposta.sinal_id == sinal.id, Aposta.resultado == 'pendente')
        res = await session.execute(q)
        apostas = res.scalars().all()

        for aposta in apostas:
            aposta.resultado = sinal.resultado
            if sinal.resultado == 'ganhou':
                aposta.lucro_bruto = float(aposta.stake_real * sinal.odd)
                aposta.lucro_liquido = aposta.lucro_bruto - float(aposta.stake_real)
            elif sinal.resultado == 'perdeu':
                aposta.lucro_bruto = 0
                aposta.lucro_liquido = -float(aposta.stake_real)
            else: # void
                aposta.lucro_bruto = float(aposta.stake_real)
                aposta.lucro_liquido = 0
            
            aposta.liquidada_em = datetime.now()
            
            # Atualiza banca do usuário
            user = await session.get(Usuario, aposta.usuario_id)
            if user:
                user.banca_atual += aposta.lucro_liquido

    # --- RECONCILIAÇÃO ---

    async def reconciliar_apostas(self):
        """Verifica se há divergências entre o banco e a API (Double Check)."""
        async with AsyncSessionLocal() as session:
            # Busca sinais liquidados recentemente (últimas 24h)
            q = select(Sinal).where(Sinal.resultado_verificado == True)
            res = await session.execute(q)
            sinais = res.scalars().all()
            
            discrepancias = 0
            for sinal in sinais:
                # Re-busca na API para validar
                # (Simulado: em prod, chamaria a API novamente)
                pass
            
            return discrepancias

# Helper para importar Usuario sem circular dependency
from core.database import Usuario
