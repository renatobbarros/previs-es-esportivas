import asyncio
import sqlite3
import os
from datetime import datetime
from sqlalchemy import select, insert
from core.database import (
    engine, init_models, AsyncSessionLocal, 
    Usuario, Sinal, Aposta, BancaSnapshot, JobRun
)
from config import settings

SQLITE_DB = "data/sports_edge.db"

async def migrate():
    if not os.path.exists(SQLITE_DB):
        print(f"❌ Banco SQLite não encontrado em {SQLITE_DB}. Abortando.")
        return

    print("🏗️ Inicializando tabelas no PostgreSQL...")
    await init_models()

    # Conexão legada SQLite
    lite_conn = sqlite3.connect(SQLITE_DB)
    lite_conn.row_factory = sqlite3.Row
    lite_cursor = lite_conn.cursor()

    async with AsyncSessionLocal() as pg_session:
        # 1. Migrar Usuário Principal (Admin)
        print("👤 Migrando usuários...")
        # Cria o usuário dono se não existir
        admin_id = settings.OWNER_TELEGRAM_ID
        pg_user = await pg_session.execute(select(Usuario).where(Usuario.telegram_id == admin_id))
        user_obj = pg_user.scalar_one_or_none()
        
        if not user_obj:
            user_obj = Usuario(
                telegram_id=admin_id,
                username="admin_migrado",
                status="ativo",
                banca_inicial=settings.BANKROLL,
                banca_atual=settings.BANKROLL
            )
            pg_session.add(user_obj)
            await pg_session.flush()
        
        # 2. Migrar Sinais
        print("🎯 Migrando sinais...")
        lite_cursor.execute("SELECT * FROM signals")
        old_signals = lite_cursor.fetchall()
        signal_map = {} # old_id -> new_id
        
        for s in old_signals:
            new_s = Sinal(
                jogo=s['match_description'],
                esporte=s['sport'],
                odd=s['recommended_odds'],
                prob_real=s['ai_probability'],
                edge_pct=s['edge_percent'] * 100 if s['edge_percent'] < 1 else s['edge_percent'],
                confianca=s['confidence_score'],
                stake_sugerida=s['suggested_stake_units'],
                resultado="pendente", # Default
                criado_em=datetime.fromisoformat(s['created_at']) if s['created_at'] else datetime.now()
            )
            pg_session.add(new_s)
            await pg_session.flush()
            signal_map[s['id']] = new_s.id

        # 3. Migrar Apostas
        print("💰 Migrando apostas...")
        lite_cursor.execute("SELECT * FROM bets")
        old_bets = lite_cursor.fetchall()
        
        for b in old_bets:
            new_b = Aposta(
                usuario_id=user_obj.id,
                sinal_id=signal_map.get(b['signal_id']),
                stake_real=b['stake_amount'],
                resultado=b['status'],
                lucro_bruto=b['result_amount'] if b['status'] == 'won' else 0,
                lucro_liquido=b['result_amount'],
                apostada_em=datetime.fromisoformat(b['placed_at']) if b['placed_at'] else datetime.now(),
                liquidada_em=datetime.fromisoformat(b['settled_at']) if b['settled_at'] else None
            )
            pg_session.add(new_b)

        # 4. Migrar Snapshots de Banca
        print("📈 Migrando histórico de banca...")
        lite_cursor.execute("SELECT * FROM bankroll_snapshots")
        old_snaps = lite_cursor.fetchall()
        
        for snap in old_snaps:
            new_snap = BancaSnapshot(
                usuario_id=user_obj.id,
                valor=snap['balance'],
                delta=snap['profit_loss'],
                motivo="Migração Legada",
                criado_em=datetime.fromisoformat(snap['snapshot_at']) if snap['snapshot_at'] else datetime.now()
            )
            pg_session.add(new_snap)

        # 5. Migrar Job Runs
        print("⚙️ Migrando logs de sistema...")
        try:
            lite_cursor.execute("SELECT * FROM job_runs")
            old_jobs = lite_cursor.fetchall()
            for j in old_jobs:
                new_j = JobRun(
                    job_name=j['job_name'],
                    status=j['status'],
                    duracao_ms=j['duration_ms'],
                    erro=j['error'],
                    executado_em=datetime.fromisoformat(j['executed_at']) if j['executed_at'] else datetime.now()
                )
                pg_session.add(new_j)
        except:
            print("⚠️ Tabela job_runs não encontrada no SQLite. Pulando.")

        await pg_session.commit()
        print("✅ MIGRACÃO CONCLUÍDA COM SUCESSO!")

if __name__ == "__main__":
    asyncio.run(migrate())
