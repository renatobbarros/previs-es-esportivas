#!/bin/bash

# Sports Edge AI - Iniciador Unificado (Linux/macOS)
# Este script inicia o monitor, a automação e o dashboard de uma vez.

# Garante que estamos na pasta do projeto
cd "$(dirname "$0")"

echo "--------------------------------------------------"
echo "🚀 INICIANDO SPORTS EDGE AI"
echo "--------------------------------------------------"

# Cria pasta de logs se não existir
mkdir -p logs

# 1. Iniciar Monitor de Notícias em background
echo "📡 [1/3] Iniciando Monitor de Notícias (Background)..."
~/.local/bin/uv run python src/news_monitor.py > logs/news_monitor.log 2>&1 &
NEWS_PID=$!

# 2. Iniciar Motor de Automação em background
echo "🤖 [2/3] Iniciando Motor de Automação (Background)..."
~/.local/bin/uv run python src/automation.py > logs/automation.log 2>&1 &
AUTO_PID=$!

# 3. Iniciar Dashboard (Este fica travado no terminal para você ver)
echo "🎯 [3/3] Iniciando Dashboard Streamlit..."
echo "--------------------------------------------------"
echo "✅ Sistema Rodando!"
echo "👉 Dashboard: http://localhost:8501"
echo "📝 Logs de fundo em: ./logs/"
echo "--------------------------------------------------"
echo "Pressione CTRL+C nesta janela para encerrar TODO o sistema."
echo "--------------------------------------------------"

# Executa o streamlit
~/.local/bin/uv run streamlit run dashboard/app.py

# Ao fechar o streamlit (CTRL+C), encerra os processos de fundo
echo ""
echo "Stopping background processes (PIDs: $NEWS_PID, $AUTO_PID)..."
kill $NEWS_PID $AUTO_PID
echo "👋 Sistema encerrado com sucesso."
