# ⚽🏀 Sports Edge AI

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B.svg)
![AI](https://img.shields.io/badge/AI-Cerebras_Llama3.1-orange.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

O **Sports Edge AI** é um sistema completo e quantitativo de previsão de apostas esportivas projetado para encontrar ineficiências no mercado (*value bets*). Ele consolida odds de diversos bookmakers, utiliza métodos matemáticos rigorosos (remoção de margem/vig, Critério de Kelly) e conta com a inteligência artificial ultra-rápida do Cerebras para avaliar variáveis subjetivas e calcular probabilidades justas.

---

## 🎯 Funcionalidades

1. **Odds Fetcher Assíncrono:** Varre múltiplas casas de aposta via The Odds API buscando oportunidades em Futebol e NBA. Calcula automaticamente a ineficiência do mercado (Spread).
2. **AI Analyzer (Llama 3.1 8B via Cerebras):** Lê dados do mercado e gera análises profundas de Expected Value (EV), Edge, probabilidade teórica e recomenda stakes específicos com base em modelos de predição.
3. **News Monitor:** Triagem inteligente e ininterrupta de feeds RSS. A IA filtra e alerta sobre quebras que impactam drasticamente as odds nas próximas 48h (lesões, suspensões, mudança de treinador).
4. **Calculadora e Gestão de Banca (Kelly Criterion):** Módulo nativo para calibrar sua proteção de banca contra volatilidade recomendando parcelas ideais baseadas em Kelly Fracionado.
5. **Dashboard Web Interativo:** Painel Streamlit completo com filtros de ligas, histórico de apostas editável e rastreamento de ROI.
6. **Backtesting Engine:** Motor quantitativo que cruza estratégias com dados históricos do *football-data.co.uk* e valida o Expected Value no longo prazo simulando cenários reais.

---

## 🚀 Como Começar (Instalação)

### 1. Pré-requisitos
* Python 3.11 ou superior
* Gerenciador de pacotes [`uv`](https://docs.astral.sh/uv/) instalado. (Ou `pip` caso prefira adaptar o `pyproject.toml`).

### 2. Clonando o Repositório
```bash
git clone https://github.com/SEU_USUARIO/sports-edge-ai.git
cd sports-edge-ai
```

### 3. Instalação das Dependências
Utilize o `uv` para instalar tudo rapidamente:
```bash
uv sync
```
*(Se estiver usando PIP clássico: `pip install -e .` ou instale os pacotes listados no `pyproject.toml`)*

### 4. Configuração de Chaves (Gratuitas)
Copie o arquivo de exemplo para gerar as suas variáveis de ambiente:
```bash
cp .env.example .env
```
Abra o `.env` gerado e insira suas credenciais:
* **ODDS_API_KEY:** Crie uma conta em [the-odds-api.com](https://the-odds-api.com/) para varrer o mercado (Plano grátis tem 500 requests/mês).
* **CEREBRAS_API_KEY:** Crie uma conta em [cloud.cerebras.ai](https://cloud.cerebras.ai/) para utilizar o motor de Inteligência Artificial sem custo.

---

## 🎮 Como Usar

O projeto é fragmentado para que você possa rodar os módulos de acordo com sua necessidade de operação:

### A) Abrindo o Dashboard Principal (Recomendado)
Para a experiência visual onde você administra seus sinais, filtra, usa calculadoras de Kelly e acessa seu histórico de vitórias/derrotas:
```bash
uv run streamlit run dashboard/app.py
```
Acesse no seu navegador via: `http://localhost:8501`

### B) Motor de Sinais Quantitativo
Para forçar a IA a varrer o mercado agora em busca de novos edges (Salva o resultado e relatório Markdown na pasta `data/signals/`):
```bash
uv run python src/ai_analyzer.py
```

### C) Monitor Contínuo de Notícias RSS
Perfeito para rodar em *background* (ou em um Raspberry Pi/Servidor) e receber alertas caso estrelas da NBA ou do futebol se machuquem e alterem a precificação do mercado:
```bash
uv run python src/news_monitor.py
```

### D) Backtesting de Longo Prazo
Baixe o histórico gratuito de centenas de jogos e valide as estratégias pré-embutidas em `run_backtest.py`:
```bash
uv run python backtest/fetch_historical.py
uv run python backtest/run_backtest.py
```

---

## ⚠️ Disclaimer e Responsabilidade
Este é um **projeto de engenharia de software e ciência de dados**, focado em *backtesting* de algoritmos preditivos e estatística quantitativa.
* **Não é uma garantia de lucro.** O comportamento passado de um mercado dinâmico não assegura que as mesmas predições darão lucro futuro.
* As casas de apostas frequentemente ajustam linhas, e *Edges* são efêmeros.
* Jamais aposte valores que não está disposto a perder. Faça uma boa gestão de banca. A decisão final e o risco são exclusivamente seus.

## 🤝 Contribuindo
Fique à vontade para fazer `Forks`, enviar `Pull Requests`, abrir *issues* ou contribuir com melhorias nos prompts da IA e na engenharia dos módulos!
