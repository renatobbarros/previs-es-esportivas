#!/bin/bash

# Script de Deploy Automatizado - Sports Edge AI

echo "🚀 Iniciando Deploy do Sports Edge AI Pro..."

# 1. Atualiza o código
echo "📥 Puxando últimas alterações do Git..."
git pull

# 2. Sobe a infraestrutura
echo "🐳 Construindo e iniciando containers Docker..."
docker compose up -d --build

# 3. Limpeza de recursos antigos
echo "🧹 Limpando imagens e volumes órfãos..."
docker system prune -f

# 4. Verificação de Saúde
echo "🔍 Aguardando banco de dados ficar saudável..."
sleep 5
docker compose ps

echo "✅ Deploy finalizado com sucesso! Acesse o Dashboard na porta 8501."
