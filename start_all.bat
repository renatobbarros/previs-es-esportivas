@echo off
TITLE Sports Edge AI - Control Center

echo --------------------------------------------------
echo 🚀 INICIANDO SPORTS EDGE AI (WINDOWS)
echo --------------------------------------------------

:: Inicia o Monitor de Notícias em uma nova janela minimizada
echo 📡 [1/3] Iniciando Monitor de Notícias...
start /min "News Monitor" uv run python src/news_monitor.py

:: Inicia o Motor de Automação em uma nova janela minimizada
echo 🤖 [2/3] Iniciando Motor de Automação...
start /min "Automation Engine" uv run python src/automation.py

:: Inicia o Dashboard na janela atual
echo 🎯 [3/3] Iniciando Dashboard Streamlit...
echo --------------------------------------------------
echo ✅ Sistema Rodando!
echo 👉 Dashboard: http://localhost:8501
echo --------------------------------------------------
uv run streamlit run dashboard/app.py

pause
