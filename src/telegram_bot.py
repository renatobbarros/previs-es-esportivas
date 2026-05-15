"""
src/telegram_bot.py — Serviço de notificações via Telegram.
Envia sinais de aposta diretamente para o celular do usuário.
"""
import httpx
import asyncio
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path para importar config
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from config import settings

async def send_telegram_message(message: str):
    """Envia uma mensagem para o chat configurado via Telegram Bot API."""
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    
    if not token or not chat_id:
        # Silencioso se não estiver configurado
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")
        return False

def format_date_br(date_str: str) -> str:
    """Converte data ISO/YYYY-MM-DD para formato amigável em PT-BR."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        meses = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        
        dia_semana = dias[dt.weekday()]
        mes = meses[dt.month]
        
        return f"{dia_semana}, {dt.day:02d} {mes} - {dt.hour:02d}:{dt.minute:02d}"
    except:
        return date_str

async def send_signal_alert(signal: dict):
    """Formata e envia um alerta de sinal de aposta (Async)."""
    game = signal.get("game_info", {})
    
    # Novos campos do pipeline otimizado
    best_bet = signal.get("best_bet_name", "N/A")
    odd = signal.get("odd", 0)
    edge = signal.get("edge_pct", 0)
    stake = signal.get("stake_pct", 0)
    confidence = signal.get("confianca", "low").upper()
    
    msg = (
        f"🎯 *NOVO SINAL ENCONTRADO*\n\n"
        f"⚽ *{game.get('home_team')} x {game.get('away_team')}*\n"
        f"🏆 {game.get('league')}\n\n"
        f"✅ *Aposta:* {best_bet}\n"
        f"📈 *Odd:* @{odd:.2f}\n"
        f"🔥 *Confiança:* {confidence}\n"
        f"📊 *Edge:* {edge:.1f}%\n"
        f"💰 *Stake:* {stake:.1f}%\n\n"
        f"🤖 *Resumo:* {signal.get('resumo_executivo')}"
    )
    
    return await send_telegram_message(msg)

if __name__ == "__main__":
    # Teste rápido
    from datetime import datetime
    test_signal = {
        "best_bet_name": "Arsenal",
        "odd": 2.10,
        "edge_pct": 12.5,
        "stake_pct": 5.0,
        "confianca": "high",
        "resumo_executivo": "Teste de notificação do Telegram Bot.",
        "game_info": {
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "league": "Premier League"
        }
    }
    asyncio.run(send_signal_alert(test_signal))
