from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    BIGINT, INT, NUMERIC, TEXT, TIMESTAMP, Column, ForeignKey, 
    Index, String, Table, text, select, func
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from config import settings

# --- INFRAESTRUTURA ---

# Ajusta URL para driver asyncpg se necessário
DATABASE_URL = settings.POSTGRES_URL or "postgresql+asyncpg://admin:password@localhost:5432/sports_edge"
if "asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# --- MODELOS ---

class Usuario(Base):
    __tablename__ = "usuarios"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BIGINT, unique=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(TEXT)
    nome: Mapped[Optional[str]] = mapped_column(TEXT)
    status: Mapped[str] = mapped_column(TEXT, server_default="pendente") # pendente|ativo|suspenso
    
    banca_inicial: Mapped[float] = mapped_column(NUMERIC(10, 2), default=20.00)
    banca_atual: Mapped[float] = mapped_column(NUMERIC(10, 2), default=20.00)
    profit_share_pct: Mapped[float] = mapped_column(NUMERIC(4, 3), default=0.100)
    
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    ativo_em: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    apostas = relationship("Aposta", back_populates="usuario")
    snapshots = relationship("BancaSnapshot", back_populates="usuario")

class Sinal(Base):
    __tablename__ = "sinais"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    api_game_id: Mapped[Optional[str]] = mapped_column(TEXT) # ID original na The Odds/Panda
    api_source: Mapped[Optional[str]] = mapped_column(TEXT)  # theodds | pandascore
    
    jogo: Mapped[str] = mapped_column(TEXT, nullable=False)
    esporte: Mapped[Optional[str]] = mapped_column(TEXT)
    odd: Mapped[float] = mapped_column(NUMERIC(6, 3))
    prob_real: Mapped[float] = mapped_column(NUMERIC(5, 4))
    edge_pct: Mapped[float] = mapped_column(NUMERIC(5, 2))
    confianca: Mapped[float] = mapped_column(NUMERIC(5, 4))
    stake_sugerida: Mapped[float] = mapped_column(NUMERIC(10, 2))
    
    resultado: Mapped[str] = mapped_column(TEXT, server_default="pendente")
    resultado_api: Mapped[Optional[str]] = mapped_column(TEXT)     # Placar RAW da API
    resultado_api_em: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    resultado_verificado: Mapped[bool] = mapped_column(server_default="false")
    
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())

    apostas = relationship("Aposta", back_populates="sinal")

class Disputa(Base):
    __tablename__ = "disputas"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    aposta_id: Mapped[int] = mapped_column(ForeignKey("apostas.id"))
    valor_banco: Mapped[str] = mapped_column(TEXT)
    valor_api: Mapped[str] = mapped_column(TEXT)
    resolvido: Mapped[bool] = mapped_column(server_default="false")
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())

class Aposta(Base):
    __tablename__ = "apostas"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    sinal_id: Mapped[int] = mapped_column(ForeignKey("sinais.id"))
    
    stake_real: Mapped[float] = mapped_column(NUMERIC(10, 2), nullable=False)
    resultado: Mapped[str] = mapped_column(TEXT, server_default="pendente")
    
    lucro_bruto: Mapped[Optional[float]] = mapped_column(NUMERIC(10, 2))
    comissao: Mapped[Optional[float]] = mapped_column(NUMERIC(10, 2))
    lucro_liquido: Mapped[Optional[float]] = mapped_column(NUMERIC(10, 2))
    
    apostada_em: Mapped[datetime] = mapped_column(server_default=func.now())
    liquidada_em: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    usuario = relationship("Usuario", back_populates="apostas")
    sinal = relationship("Sinal", back_populates="apostas")

class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    sinal_id: Mapped[int] = mapped_column(ForeignKey("sinais.id"))
    
    odd_home: Mapped[float] = mapped_column(NUMERIC(6, 3))
    odd_draw: Mapped[Optional[float]] = mapped_column(NUMERIC(6, 3))
    odd_away: Mapped[float] = mapped_column(NUMERIC(6, 3))
    
    bookmaker: Mapped[str] = mapped_column(TEXT)
    capturado_em: Mapped[datetime] = mapped_column(server_default=func.now())

    sinal = relationship("Sinal")

class BancaSnapshot(Base):
    __tablename__ = "banca_snapshots"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    
    valor: Mapped[float] = mapped_column(NUMERIC(10, 2))
    delta: Mapped[Optional[float]] = mapped_column(NUMERIC(10, 2))
    motivo: Mapped[Optional[str]] = mapped_column(TEXT)
    ref_aposta_id: Mapped[Optional[int]] = mapped_column(INT)
    
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())

    usuario = relationship("Usuario", back_populates="snapshots")

class CicloComissao(Base):
    __tablename__ = "ciclos_comissao"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    
    inicio_ciclo: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    fim_ciclo: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    
    lucro_liquido: Mapped[float] = mapped_column(NUMERIC(10, 2))
    comissao_devida: Mapped[float] = mapped_column(NUMERIC(10, 2))
    
    status: Mapped[str] = mapped_column(TEXT, server_default="aberto") # aberto|fechado|pago|contestado
    fechado_em: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    pago_em: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    comprovante_pix: Mapped[Optional[str]] = mapped_column(TEXT)

    usuario = relationship("Usuario")

class Convite(Base):
    __tablename__ = "convites"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    criado_por_id: Mapped[int] = mapped_column(BIGINT)
    usado_por_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    expira_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    usado_em: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    tabela: Mapped[str] = mapped_column(TEXT)
    registro_id: Mapped[int] = mapped_column(INT)
    campo_alterado: Mapped[Optional[str]] = mapped_column(TEXT)
    valor_anterior: Mapped[Optional[str]] = mapped_column(TEXT) # JSON
    valor_novo: Mapped[Optional[str]] = mapped_column(TEXT)     # JSON
    alterado_por: Mapped[str] = mapped_column(TEXT)            # sistema|admin|usuario:id
    alterado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    ip_origem: Mapped[Optional[str]] = mapped_column(TEXT)
    hash_anterior: Mapped[Optional[str]] = mapped_column(TEXT) # Blockchain chain

class JobRun(Base):
    __tablename__ = "job_runs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    job_name: Mapped[str] = mapped_column(TEXT)
    status: Mapped[str] = mapped_column(TEXT)
    duracao_ms: Mapped[int] = mapped_column(INT)
    erro: Mapped[Optional[str]] = mapped_column(TEXT)
    executado_em: Mapped[datetime] = mapped_column(server_default=func.now())

# --- HELPERS DE PERSISTÊNCIA ---

class DataService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_telegram_id(self, tid: int) -> Optional[Usuario]:
        res = await self.session.execute(select(Usuario).where(Usuario.telegram_id == tid))
        return res.scalar_one_or_none()

    async def create_invite(self, admin_tid: int) -> str:
        import uuid
        from datetime import timedelta
        token = str(uuid.uuid4())
        invite = Convite(
            token=token,
            criado_por_id=admin_tid,
            expira_em=datetime.now() + timedelta(hours=48)
        )
        self.session.add(invite)
        await self.session.commit()
        return token

    async def validate_invite(self, token: str) -> Optional[Convite]:
        res = await self.session.execute(
            select(Convite).where(
                Convite.token == token,
                Convite.usado_em == None,
                Convite.expira_em > datetime.now()
            )
        )
        return res.scalar_one_or_none()

    async def save_signal(self, data: dict) -> int:
        signal = Sinal(
            api_game_id=data.get('api_game_id'),
            api_source=data.get('api_source'),
            jogo=data['match_description'],
            esporte=data['sport'],
            odd=data['recommended_odds'],
            prob_real=data['ai_probability'],
            edge_pct=data['edge_percent'],
            confianca=data['confidence_score'],
            stake_sugerida=data['suggested_stake_units']
        )
        self.session.add(signal)
        await self.session.commit()
        return signal.id

    async def register_user(self, tid: int, username: str, nome: str) -> Usuario:
        user = Usuario(telegram_id=tid, username=username, nome=nome, status='pendente')
        self.session.add(user)
        await self.session.commit()
        return user

    async def update_user_banca(self, tid: int, banca: float):
        user = await self.get_user_by_telegram_id(tid)
        if user:
            user.banca_inicial = banca
            user.banca_atual = banca
            await self.session.commit()

    async def activate_user(self, uid: int) -> Optional[Usuario]:
        res = await self.session.execute(select(Usuario).where(Usuario.id == uid))
        user = res.scalar_one_or_none()
        if user:
            user.status = 'ativo'
            user.ativo_em = func.now()
            await self.session.commit()
        return user

    async def get_user_stats(self, user_id: int) -> dict:
        # 1. Total Bets e Win Rate (30d)
        date_30d = datetime.now() - timedelta(days=30)
        q_30d = select(
            func.count(Aposta.id).label("total"),
            func.sum(text("CASE WHEN resultado = 'ganhou' THEN 1 ELSE 0 END")).label("wins"),
            func.sum(Aposta.lucro_liquido).label("profit")
        ).where(Aposta.usuario_id == user_id, Aposta.apostada_em >= date_30d)
        
        res_30d = (await self.session.execute(q_30d)).fetchone()
        
        # 2. ROI 7d
        date_7d = datetime.now() - timedelta(days=7)
        q_7d = select(func.sum(Aposta.lucro_liquido), func.sum(Aposta.stake_real)).where(
            Aposta.usuario_id == user_id, Aposta.apostada_em >= date_7d
        )
        res_7d = (await self.session.execute(q_7d)).fetchone()
        
        roi_7d = (res_7d[0] / res_7d[1] * 100) if res_7d and res_7d[1] and res_7d[1] > 0 else 0
        
        return {
            "total_30d": res_30d.total or 0,
            "win_rate_30d": (res_30d.wins / res_30d.total * 100) if res_30d and res_30d.total and res_30d.total > 0 else 0,
            "profit_30d": float(res_30d.profit or 0),
            "roi_7d": float(roi_7d)
        }

    async def get_user_history(self, user_id: int, status: Optional[str] = None, page: int = 1) -> List[Aposta]:
        limit = 10
        offset = (page - 1) * limit
        q = select(Aposta).where(Aposta.usuario_id == user_id).order_by(Aposta.apostada_em.desc())
        if status:
            q = q.where(Aposta.resultado == status)
        
        res = await self.session.execute(q.limit(limit).offset(offset))
        return list(res.scalars().all())

    async def record_bankroll_adjustment(self, user: Usuario, new_val: float, motivo: str):
        delta = new_val - user.banca_atual
        snap = BancaSnapshot(
            usuario_id=user.id,
            valor=new_val,
            delta=delta,
            motivo=motivo
        )
        user.banca_atual = new_val
        self.session.add(snap)
        await self.session.commit()
        return delta

    # --- BI ADMIN ---

    async def get_admin_revenue_stats(self) -> dict:
        # Total Pago
        q_pago = select(func.sum(CicloComissao.comissao_devida)).where(CicloComissao.status == 'pago')
        # Em aberto (Fechado mas não pago)
        q_aberto = select(func.sum(CicloComissao.comissao_devida)).where(CicloComissao.status == 'fechado')
        
        pago = (await self.session.execute(q_pago)).scalar() or 0
        aberto = (await self.session.execute(q_aberto)).scalar() or 0
        
        return {"total_recebido": float(pago), "total_em_aberto": float(aberto)}

    async def get_admin_user_overview(self) -> List[dict]:
        # Tabela completa de usuários com performance do ciclo atual
        q = select(Usuario).order_by(Usuario.banca_atual.desc())
        users = (await self.session.execute(q)).scalars().all()
        
        from core.comissao import CommissionManager
        hoje = datetime.now()
        inicio_semana = hoje - timedelta(days=hoje.weekday() + 1)
        
        results = []
        for u in users:
            stats = await CommissionManager.calcular_ciclo(self.session, u.id, inicio_semana, hoje)
            results.append({
                "id": u.id,
                "nome": u.nome,
                "banca_atual": float(u.banca_atual),
                "lucro_ciclo": stats["lucro_liquido"],
                "comissao_devida": stats["comissao_devida"],
                "status": u.status
            })
        return results

    async def get_admin_alerts(self) -> List[str]:
        alerts = []
        # 1. Banca Zerada
        q_zero = select(Usuario.nome).where(Usuario.banca_atual <= 0)
        zero_users = (await self.session.execute(q_zero)).scalars().all()
        for n in zero_users: alerts.append(f"🔴 Banca zerada: {n}")
        
        # 2. Inativos (7 dias)
        date_limit = datetime.now() - timedelta(days=7)
        # q_inactive = select(Usuario.nome).where(Usuario.ativo_em < date_limit)
        
        # 3. Inadimplentes (Ciclo fechado há mais de 7 dias e não pago)
        q_debt = select(Usuario.nome).join(CicloComissao, Usuario.id == CicloComissao.usuario_id).where(
            CicloComissao.status == 'fechado',
            CicloComissao.fechado_em < date_limit
        )
        debt_users = (await self.session.execute(q_debt)).scalars().all()
        for n in debt_users: alerts.append(f"💸 Inadimplente (>7d): {n}")
        
        return alerts

    async def update_ciclo_status(self, ciclo_id: int, status: str, comprovante: str = None):
        ciclo = await self.session.get(CicloComissao, ciclo_id)
        if ciclo:
            ciclo.status = status
            ciclo.pago_em = func.now() if status == 'pago' else None
            ciclo.comprovante_pix = comprovante
            await self.session.commit()
            return ciclo
        return None

    # --- AUDITORIA E INTEGRIDADE ---

    async def get_audit_trail(self, user_id: int, mes: int) -> List[AuditLog]:
        # Busca alterações que afetam o usuário (via foreign keys das tabelas auditadas)
        # Simplificado: busca por id de registro nas tabelas correspondentes
        q = select(AuditLog).where(
            func.extract('month', AuditLog.alterado_em) == mes
        ).order_by(AuditLog.alterado_em.desc())
        res = await self.session.execute(q)
        return list(res.scalars().all())

    async def verificar_integridade(self) -> dict:
        import hashlib
        q = select(AuditLog).order_by(AuditLog.id.asc())
        logs = (await self.session.execute(q)).scalars().all()
        
        broken_id = None
        last_hash = ""
        
        for log in logs:
            # Reconstrói a string do registro para hash (excluindo o campo hash_anterior)
            data = f"{log.tabela}|{log.registro_id}|{log.valor_novo}|{log.alterado_por}"
            current_hash = hashlib.sha256(data.encode()).hexdigest()
            
            if log.hash_anterior and log.hash_anterior != last_hash:
                broken_id = log.id
                break
            last_hash = current_hash
            
        return {"status": "ok" if not broken_id else "corrompido", "broken_at": broken_id}

    async def log_fraud_attempt(self, tid: int, acao: str):
        log = AuditLog(
            tabela="seguranca",
            registro_id=0,
            campo_alterado=acao,
            valor_novo="TENTATIVA_FRAUDE",
            alterado_por=f"usuario:{tid}",
            alterado_em=func.now()
        )
        self.session.add(log)
        await self.session.commit()

Index("idx_usuario_telegram", Usuario.telegram_id)
Index("idx_aposta_usuario", Aposta.usuario_id)
Index("idx_snapshot_usuario", BancaSnapshot.usuario_id)
Index("idx_sinal_criado", Sinal.criado_em)

class DatabaseManager:
    """Interface unificada para operações de banco de dados async."""
    def __init__(self):
        self.session_factory = AsyncSessionLocal

    async def save_game(self, game_data: dict):
        async with self.session_factory() as session:
            # Lógica para salvar jogo (se necessário para histórico)
            pass

    async def signal_exists(self, api_game_id: str) -> bool:
        async with self.session_factory() as session:
            res = await session.execute(select(Sinal).where(Sinal.api_game_id == api_game_id))
            return res.scalar_one_or_none() is not None

    async def save_signal(self, data: dict) -> int:
        async with self.session_factory() as session:
            ds = DataService(session)
            return await ds.save_signal(data)

    async def get_bankroll(self) -> dict:
        # Retorna banca do admin ou média (para fins de cálculo de stake no scheduler)
        return {"balance": settings.BANKROLL}

# --- INICIALIZAÇÃO ---

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # SQL para Triggers de Auditoria em TODAS as tabelas financeiras
        # Criamos a função primeiro
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION process_audit() RETURNS TRIGGER AS $body$
            BEGIN
                IF (TG_OP = 'UPDATE') THEN
                    INSERT INTO audit_log (tabela, registro_id, campo_alterado, valor_anterior, valor_novo, alterado_por)
                    VALUES (TG_TABLE_NAME, OLD.id, 'UPDATE', CAST(OLD.* AS TEXT), CAST(NEW.* AS TEXT), 'trigger_db');
                    RETURN NEW;
                ELSIF (TG_OP = 'DELETE') THEN
                    INSERT INTO audit_log (tabela, registro_id, campo_alterado, valor_anterior, alterado_por)
                    VALUES (TG_TABLE_NAME, OLD.id, 'DELETE', CAST(OLD.* AS TEXT), 'trigger_db');
                    RETURN OLD;
                END IF;
                RETURN NULL;
            END;
            $body$ LANGUAGE plpgsql;
        """))

        # Depois os triggers individualmente
        await conn.execute(text("DROP TRIGGER IF EXISTS audit_apostas ON apostas;"))
        await conn.execute(text("CREATE TRIGGER audit_apostas AFTER UPDATE OR DELETE ON apostas FOR EACH ROW EXECUTE FUNCTION process_audit();"))

        await conn.execute(text("DROP TRIGGER IF EXISTS audit_banca ON banca_snapshots;"))
        await conn.execute(text("CREATE TRIGGER audit_banca AFTER UPDATE OR DELETE ON banca_snapshots FOR EACH ROW EXECUTE FUNCTION process_audit();"))

        await conn.execute(text("DROP TRIGGER IF EXISTS audit_comissao ON ciclos_comissao;"))
        await conn.execute(text("CREATE TRIGGER audit_comissao AFTER UPDATE OR DELETE ON ciclos_comissao FOR EACH ROW EXECUTE FUNCTION process_audit();"))

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_models())
    print("🚀 Banco de Dados PostgreSQL sincronizado com Triggers de Auditoria!")
