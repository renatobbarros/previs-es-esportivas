import os
from dotenv import set_key

def setup():
    print("🎯 Sports Edge AI Pro - Setup")
    keys = ["THE_ODDS_API_KEY", "GROQ_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    if not os.path.exists(".env"): open(".env", "w").close()
    
    for key in keys:
        val = input(f"Digite {key}: ")
        set_key(".env", key, val)
    print("✅ Configuração concluída!")

if __name__ == "__main__":
    setup()
