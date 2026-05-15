#!/bin/bash
# Sports Edge AI - Orchestration Script
set -e

echo "---------------------------------------"
echo "   🎯 SPORTS EDGE AI PRO - STARTUP"
echo "---------------------------------------"

# 1. Limpar processos antigos
echo "🧹 Limpando processos anteriores..."
pkill -f "scheduler.py" || true
pkill -f "streamlit" || true
pkill -f "telegram_bot.py" || true
rm -f /tmp/sports_edge_scheduler.lock

# 2. Iniciar Componentes
echo "📡 [1/3] Iniciando Scheduler (Orquestrador)..."
uv run python core/scheduler.py > data/logs/scheduler.log 2>&1 &

echo "🤖 [2/3] Iniciando Interface Telegram..."
uv run python core/telegram_bot.py > data/logs/telegram.log 2>&1 &

echo "📊 [3/3] Iniciando Dashboard Profissional..."
uv run streamlit run dashboard/app.py --server.port 8501 --theme.base "dark" &

echo "🚀 Todos os sistemas iniciados!"
wait
