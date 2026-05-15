#!/bin/bash
echo "🛑 Encerrando todos os serviços..."
pkill -f "scheduler.py"
pkill -f "streamlit"
pkill -f "telegram_bot.py"
rm -f /tmp/sports_edge_scheduler.lock
echo "👋 Sistema encerrado."
