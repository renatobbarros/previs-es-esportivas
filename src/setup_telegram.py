import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

def get_chat_id():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN não encontrado no .env")
        return
    
    print(f"📡 Aguardando mensagem no bot... (Token: {token[:10]}...)")
    print("👉 Por favor, abra o Telegram e mande um 'OI' para o seu bot AGORA.")
    
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    
    while True:
        try:
            r = requests.get(url).json()
            if r.get("ok") and r.get("result"):
                chat_id = r["result"][-1]["message"]["chat"]["id"]
                user_name = r["result"][-1]["message"]["from"].get("first_name", "Usuário")
                print(f"\n✅ Chat ID encontrado: {chat_id} ({user_name})")
                return chat_id
            else:
                print(".", end="", flush=True)
                time.sleep(2)
        except Exception as e:
            print(f"\n❌ Erro: {e}")
            break

if __name__ == "__main__":
    chat_id = get_chat_id()
    if chat_id:
        print(f"\n📝 Copie este número para o seu .env em TELEGRAM_CHAT_ID: {chat_id}")
