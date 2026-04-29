import streamlit as st
import pandas as pd
import numpy as np

# Configuração da Página
st.set_page_config(page_title="AI Prediction Markets Dashboard", layout="wide", page_icon="📈")

# ─────────────────────────────────────────────────────────
# Dados Mockados (Simulando API / daily_signals.md)
# ─────────────────────────────────────────────────────────

def load_data():
    return pd.DataFrame([
        {
            "id": 1,
            "Mercado": "Trump to win 2024 Election?",
            "Categoria": "Política",
            "Odds Atuais (Implícita)": 0.45,
            "Prob. IA": 0.58,
            "Confiança": "Alta 🟢",
            "Análise": "Os modelos de sentimento e pesquisas agregadas em swing states mostram uma inclinação favorável não precificada pelo mercado atual.",
            "Link": "https://polymarket.com"
        },
        {
            "id": 2,
            "Mercado": "Bitcoin atinge $100k em 2024?",
            "Categoria": "Cripto",
            "Odds Atuais (Implícita)": 0.35,
            "Prob. IA": 0.42,
            "Confiança": "Média 🟡",
            "Análise": "A entrada de capital via ETFs sugere suporte, mas a probabilidade de cruzar a marca exata até dezembro sofre de resistência técnica forte.",
            "Link": "https://polymarket.com"
        },
        {
            "id": 3,
            "Mercado": "Fed corta juros em Junho?",
            "Categoria": "Economia",
            "Odds Atuais (Implícita)": 0.20,
            "Prob. IA": 0.15,
            "Confiança": "Alta 🟢",
            "Análise": "Inflação resiliente e dados de emprego fortes sugerem manutenção prolongada. O mercado ainda está otimista demais.",
            "Link": "https://polymarket.com"
        },
        {
            "id": 4,
            "Mercado": "Real Madrid vence a Champions?",
            "Categoria": "Esportes",
            "Odds Atuais (Implícita)": 0.30,
            "Prob. IA": 0.45,
            "Confiança": "Alta 🟢",
            "Análise": "Edge significativo detectado nos confrontos simulados contra o chaveamento atual.",
            "Link": "https://polymarket.com"
        },
        {
            "id": 5,
            "Mercado": "Ethereum ETF aprovado em Maio?",
            "Categoria": "Cripto",
            "Odds Atuais (Implícita)": 0.18,
            "Prob. IA": 0.22,
            "Confiança": "Baixa 🔴",
            "Análise": "Sinais regulatórios confusos da SEC, edge pequeno devido à alta volatilidade implícita.",
            "Link": "https://polymarket.com"
        }
    ])

df = load_data()

# Calcula Edge
df["Edge"] = df["Prob. IA"] - df["Odds Atuais (Implícita)"]

# ─────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────

st.sidebar.title("Filtros")

categorias = st.sidebar.multiselect(
    "Categoria",
    options=df["Categoria"].unique(),
    default=df["Categoria"].unique()
)

min_edge = st.sidebar.slider("Edge Mínimo (%)", 0, 30, 5) / 100.0

confianca_opcoes = ["Alta 🟢", "Média 🟡", "Baixa 🔴"]
confianca = st.sidebar.multiselect(
    "Nível de Confiança",
    options=confianca_opcoes,
    default=confianca_opcoes
)

valor_aposta = st.sidebar.number_input("Valor da Aposta Simulada ($)", min_value=10, max_value=500, value=100)

st.sidebar.divider()

# Calculadora de Kelly
st.sidebar.subheader("🧮 Calculadora de Kelly")
bankroll = st.sidebar.number_input("Bankroll Total ($)", min_value=100, value=1000)
kelly_prob_ia = st.sidebar.number_input("Probabilidade Estimada (IA)", min_value=0.01, max_value=0.99, value=0.58)
kelly_odds = st.sidebar.number_input("Odds Atuais do Mercado (0-1)", min_value=0.01, max_value=0.99, value=0.45)

# Cálculo Kelly (Fração = Edge / Odds_Lucro)
# Convertendo probabilidade implícita para odds decimais para a fórmula padrão de Kelly
b = (1 / kelly_odds) - 1
p = kelly_prob_ia
q = 1 - p
kelly_fraction = (p * b - q) / b

st.sidebar.markdown(f"**Edge:** {(p - kelly_odds)*100:.1f}%")

if kelly_fraction > 0:
    sugestao_bruta = kelly_fraction * bankroll
    sugestao_max_3 = min(kelly_fraction, 0.03) * bankroll
    
    st.sidebar.success(f"Tamanho Ideal (Kelly): **${sugestao_bruta:.2f}** ({kelly_fraction*100:.1f}%)")
    st.sidebar.info(f"Sugerido (Max 3%): **${sugestao_max_3:.2f}**")
    
    if kelly_fraction > 0.05:
        st.sidebar.warning("⚠️ O Critério de Kelly sugere mais de 5%. É altamente recomendável usar Kelly Fracionado (ex: 1/4 Kelly) para mitigar variância.")
else:
    st.sidebar.error("Sem edge positivo. Aposta não recomendada.")


# ─────────────────────────────────────────────────────────
# Main Content
# ─────────────────────────────────────────────────────────

st.title("🎯 AI Prediction Markets Dashboard")
st.markdown("Monitoramento de *Value Bets* e *Edge* em mercados preditivos em tempo real.")

# Aplicar Filtros
df_filtered = df[
    (df["Categoria"].isin(categorias)) &
    (df["Edge"].abs() >= min_edge) & # Absoluto caso queira apostar contra
    (df["Confiança"].isin(confianca))
].copy()

# Ordenar por maior edge
df_filtered = df_filtered.sort_values(by="Edge", ascending=False)

# Formatação
def color_edge(val):
    if val > 0.10:
        color = 'green'
    elif val >= 0.05:
        color = 'orange'
    else:
        color = 'red'
    return f'color: {color}; font-weight: bold;'

st.subheader("📊 Sinais Atuais")

if df_filtered.empty:
    st.info("Nenhum mercado corresponde aos filtros selecionados.")
else:
    for _, row in df_filtered.iterrows():
        edge_pct = row["Edge"] * 100
        
        # Cores para o Edge no cabeçalho do expander
        if edge_pct > 10:
            edge_emoji = "🟢"
        elif edge_pct >= 5:
            edge_emoji = "🟡"
        else:
            edge_emoji = "🔴"
            
        with st.expander(f"{row['Mercado']} | IA: {row['Prob. IA']*100:.0f}% | Mercado: {row['Odds Atuais (Implícita)']*100:.0f}% | Edge: {edge_pct:+.1f}% {edge_emoji}"):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"**Categoria:** {row['Categoria']}")
                st.markdown(f"**Confiança:** {row['Confiança']}")
                st.markdown(f"**Análise Completa da IA:**\n\n> {row['Análise']}")
            
            with col2:
                st.markdown("### Retorno Esperado")
                aposta = valor_aposta
                odd_decimal = 1 / row["Odds Atuais (Implícita)"]
                retorno = aposta * odd_decimal
                lucro = retorno - aposta
                st.metric("Se ganhar", f"${retorno:.2f}", f"+${lucro:.2f}")
                
            with col3:
                st.markdown("<br><br>", unsafe_allow_html=True)
                st.markdown(f"[🔗 Abrir no Polymarket]({row['Link']})", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────
# Histórico
# ─────────────────────────────────────────────────────────

st.divider()
st.subheader("📜 Histórico e Calibração")
st.markdown("Comparativo de previsões passadas para calibrar a eficácia da IA.")

historico_data = [
    {"Data": "2024-03-01", "Mercado": "Vencedor do Oscar de Melhor Filme", "Previsão IA": "Oppenheimer (85%)", "Mercado": "Oppenheimer (70%)", "Resultado": "✅ Acerto"},
    {"Data": "2024-02-15", "Mercado": "Aprovação ETF Bitcoin", "Previsão IA": "Sim (90%)", "Mercado": "Sim (60%)", "Resultado": "✅ Acerto"},
    {"Data": "2024-01-10", "Mercado": "Inflação CPI Janeiro", "Previsão IA": "Acima do esperado (60%)", "Mercado": "Dentro do esperado (50%)", "Resultado": "❌ Erro"}
]

st.table(pd.DataFrame(historico_data))
