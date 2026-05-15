# 🚀 Sports Edge AI Pro v2.0

Sistema avançado de Value Betting multiesporte com orquestração de IA.

## 🛠️ Como Instalar

1. **Instale o UV**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. **Setup**: `python setup.py` (insira suas chaves)
3. **Dependências**: `uv sync`
4. **Iniciar**: `./start_all.sh`

## 📊 Estrutura
- `core/`: Motores de IA, Banco e Risco.
- `sports/`: Analisadores específicos por esporte.
- `dashboard/`: Interface Streamlit Pro.
- `analysis/`: Motor de Backtesting.

## 🚨 Troubleshooting
- **Erro de API**: Verifique o `.env`.
- **Database Locked**: `pkill -f python` e tente novamente.
