from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy import select, func, text
from core.database import AsyncSessionLocal, Aposta, Usuario, CicloComissao
from core.logger import logger

class CommissionManager:
    """Gerencia a lógica de monetização e ciclos de faturamento."""

    @staticmethod
    async def calcular_ciclo(session, usuario_id: int, inicio: datetime, fim: datetime) -> Dict[str, Any]:
        """Calcula o balanço financeiro de um usuário em um intervalo específico."""
        
        # 1. Busca apostas no intervalo
        q = select(Aposta).where(
            Aposta.usuario_id == usuario_id,
            Aposta.apostada_em >= inicio,
            Aposta.apostada_em <= fim,
            Aposta.resultado != 'pendente'
        )
        res = await session.execute(q)
        apostas = res.scalars().all()

        stats = {
            "ganhas": 0, "perdidas": 0, "void": 0,
            "receita_bruta": 0.0, "custo_stakes": 0.0,
            "lucro_liquido": 0.0, "comissao_devida": 0.0
        }

        for a in apostas:
            if a.resultado == 'ganhou':
                stats["ganhas"] += 1
                stats["receita_bruta"] += float(a.lucro_bruto or 0)
            elif a.resultado == 'perdeu':
                stats["perdidas"] += 1
                stats["custo_stakes"] += float(a.stake_real)
            elif a.resultado == 'void':
                stats["void"] += 1

        # Lucro Líquido = Receita Bruta (lucro das ganhas) - Stakes das perdidas
        stats["lucro_liquido"] = round(stats["receita_bruta"] - stats["custo_stakes"], 2)
        
        # Busca o usuário para ver o profit_share_pct
        user = await session.get(Usuario, usuario_id)
        pct = float(user.profit_share_pct or 0.10)
        
        if stats["lucro_liquido"] > 0:
            stats["comissao_devida"] = round(stats["lucro_liquido"] * pct, 2)
        else:
            stats["comissao_devida"] = 0.0

        stats["comissao_pct_efetiva"] = pct
        return stats

    @classmethod
    async def fechar_ciclo_usuario(cls, usuario_id: int):
        """Fecha o ciclo atual, gera o registro e notifica."""
        async with AsyncSessionLocal() as session:
            # Ciclo semanal: domingo passado (00:00) até hoje domingo (23:00)
            fim = datetime.now()
            inicio = fim - timedelta(days=7)
            
            stats = await cls.calcular_ciclo(session, usuario_id, inicio, fim)
            
            novo_ciclo = CicloComissao(
                usuario_id=usuario_id,
                inicio_ciclo=inicio,
                fim_ciclo=fim,
                lucro_liquido=stats["lucro_liquido"],
                comissao_devida=stats["comissao_devida"],
                status="fechado",
                fechado_em=datetime.now()
            )
            session.add(novo_ciclo)
            await session.commit()
            
            logger.info("cycle_closed", usuario_id=usuario_id, comissao=stats["comissao_devida"])
            return stats, novo_ciclo

async def get_all_active_users_ids():
    async with AsyncSessionLocal() as session:
        q = select(Usuario.id).where(Usuario.status == 'ativo')
        res = await session.execute(q)
        return res.scalars().all()
