import asyncio
from sqlalchemy import text
from core.database import engine, init_models
from core.logger import logger

async def test_connection():
    print("⏳ Tentando conectar ao Supabase...")
    try:
        # 1. Testa a conexão básica
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            if result.scalar() == 1:
                print("✅ Conexão básica estabelecida com sucesso!")
        
        # 2. Tenta inicializar os modelos e triggers
        print("🏗️ Sincronizando tabelas e triggers de auditoria...")
        await init_models()
        print("✨ Tabelas criadas e triggers configurados com sucesso!")
        
        print("\n🚀 SEU BANCO DE DADOS ESTÁ 100% OPERACIONAL!")
        
    except Exception as e:
        print(f"\n❌ ERRO DE CONEXÃO: {e}")
        print("\nVerifique se:")
        print("1. A senha no .env está correta.")
        print("2. O IP da sua máquina não está bloqueado no Firewall do Supabase.")
        print("3. Você adicionou '+asyncpg' na URL.")

if __name__ == "__main__":
    asyncio.run(test_connection())
