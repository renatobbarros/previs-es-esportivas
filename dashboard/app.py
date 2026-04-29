"""
dashboard/app.py — Dashboard PRO do Sports Edge AI
Interface intuitiva com monitoramento de notícias e sinais integrados.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Garante que config possa ser importado
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import config

# Configuração da Página
st.set_page_config(
    page_title="Sports Edge AI PRO",
    page_icon="🎯",
    layout="wide"
)

# Estilo CSS Customizado para deixar mais intuitivo
st.markdown("""
    <style>
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    .urgent-card { background-color: #ffebee; padding: 15px; border-radius: 10px; border-left: 5px solid #f44336; margin-bottom: 10px; }
    .news-card { background-color: #e3f2fd; padding: 15px; border-radius: 10px; border-left: 5px solid #2196f3; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# Carregamento de Dados
# ─────────────────────────────────────────────────────────

def load_json(path: Path):
    if path.exists():
        try: return json.loads(path.read_text())
        except: return []
    return []

def get_latest_signals():
    files = sorted(list(config.SIGNALS_DIR.glob("signals_*.json")), reverse=True)
    return load_json(files[0]) if files else []

# ─────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────

st.sidebar.title("🚀 Central de Comando")
st.sidebar.markdown("Configure sua banca e preferências para cálculos automáticos.")

bankroll = st.sidebar.number_input("💸 Sua Banca Total (R$)", min_value=10.0, value=float(config.DEFAULT_BANKROLL))
st.sidebar.divider()

# Filtros Rápidos
st.sidebar.subheader("Filtros de Sinais")
min_edge_ui = st.sidebar.slider("Edge Mínimo (%)", 0, 30, 6)
conf_min_ui = st.sidebar.select_slider("Confiança Mínima", options=["Baixa", "Média", "Alta"], value="Média")

st.sidebar.divider()
st.sidebar.caption("O sistema atualiza sinais e notícias em tempo real no servidor.")

# ─────────────────────────────────────────────────────────
# UI Principal
# ─────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(["🔥 Sinais e Alertas", "📈 Performance", "🧮 Calculadoras", "📖 Guia"])

# ==========================================
# ABA 1: SINAIS E ALERTAS (AUTOMATIZADA)
# ==========================================
with tab1:
    col_main, col_news = st.columns([3, 1])

    with col_main:
        st.subheader("🎯 Oportunidades de Valor")
        signals = get_latest_signals()
        
        # Filtro de confiança para comparação
        conf_map = {"Baixa": 0, "Média": 1, "Alta": 2}
        conf_val_map = {"low": 0, "medium": 1, "high": 2}

        filtered = [
            s for s in signals 
            if s.get("edge", 0) >= min_edge_ui and 
            conf_val_map.get(s.get("confidence", "low"), 0) >= conf_map[conf_min_ui]
        ]

        if not filtered:
            st.info("Aguardando novas oportunidades de mercado que atinjam seus critérios...")
        else:
            for s in filtered:
                game = s.get("game_info", {})
                bet = s.get("best_bet")
                team_bet = game.get(f"{bet}_team") if bet in ["home", "away"] else "Empate"
                odd = game.get("best_odds", {}).get(bet, {}).get("odd", 0)
                book = game.get("best_odds", {}).get(bet, {}).get("bookmaker", "?")
                
                stake_pct = s.get("recommended_stake_pct", 0)
                stake_brl = (stake_pct / 100) * bankroll
                
                # Cabeçalho Intuitivo
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c1:
                        st.markdown(f"### {game.get('home_team')} x {game.get('away_team')}")
                        st.caption(f"🏆 {game.get('league')} | ⏰ {game.get('commence_time')}")
                    with c2:
                        st.metric("Aposta", team_bet, f"@{odd:.2f}")
                    with c3:
                        st.metric("Stake", f"R$ {stake_brl:.2f}", f"{stake_pct:.1f}%")

                    with st.expander("Ver Análise Estratégica"):
                        st.markdown(f"**Raciocínio:** {s.get('reasoning')}")
                        st.markdown(f"**📍 Onde apostar:** {book}")
                        
                        st.divider()
                        f1, f2 = st.columns(2)
                        f1.write("**✅ Por que apostar:**")
                        for kf in s.get("key_factors", []): f1.write(f"- {kf}")
                        f2.write("**⚠️ Riscos (Red Flags):**")
                        for rf in s.get("red_flags", []): f2.write(f"- {rf}")
                        
                        # Botão de Cópia Rápida (Simulado)
                        st.code(f"Aposta: {team_bet} | Odd: {odd} | Valor: R$ {stake_brl:.2f}", language="text")

    with col_news:
        st.subheader("🔔 Notícias de Última Hora")
        urgent = load_json(config.DATA_DIR / "urgent_alerts.json")
        news = load_json(config.DATA_DIR / "news_alerts.json")

        if not urgent and not news:
            st.caption("Nenhum alerta de impacto detectado recentemente.")
        
        for u in urgent[:3]:
            st.markdown(f"""<div class="urgent-card">
                <strong>🚨 URGENTE: {u['teams_affected'][0] if u['teams_affected'] else 'Esporte'}</strong><br>
                {u['title']}<br>
                <small>Impacto: {u['impact']} | Ação: {u['action']}</small>
            </div>""", unsafe_allow_html=True)
            
        for n in news[:5]:
            st.markdown(f"""<div class="news-card">
                <strong>🔹 {n['sport'].upper()}</strong><br>
                {n['title']}<br>
                <small>Impacto: {n['impact']}</small>
            </div>""", unsafe_allow_html=True)

# ==========================================
# ABA 2: PERFORMANCE
# ==========================================
with tab2:
    st.subheader("Análise de Resultados")
    HISTORICO_FILE = config.DATA_DIR / "historico_apostas.csv"
    
    if HISTORICO_FILE.exists():
        df = pd.read_csv(HISTORICO_FILE)
        
        # Dashboard de métricas no topo
        wins = len(df[df["Resultado"] == "✅ Ganhou"])
        losses = len(df[df["Resultado"] == "❌ Perdeu"])
        total = wins + losses
        win_rate = (wins/total*100) if total > 0 else 0
        lucro = df["Lucro (R$)"].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Win Rate", f"{win_rate:.1f}%", f"{wins}W - {losses}L")
        m2.metric("Lucro Acumulado", f"R$ {lucro:.2f}", delta_color="normal")
        m3.metric("ROI", f"{(lucro/(df['Stake (R$)'].sum())*100):.1f}%" if total > 0 else "0%")

        st.divider()
        st.markdown("### Histórico Detalhado")
        st.data_editor(df, use_container_width=True)
    else:
        st.info("Comece a registrar suas apostas para ver as métricas de performance aqui.")

# ==========================================
# ABA 3: CALCULADORAS
# ==========================================
with tab3:
    st.subheader("Calculadoras de Apoio")
    c1, c2 = st.columns(2)
    
    with c1:
        with st.container(border=True):
            st.markdown("### 🧮 Critério de Kelly")
            k_odd = st.number_input("Odd do Evento", value=2.0)
            k_prob = st.slider("Sua Probabilidade (%)", 1, 99, 55) / 100
            
            b = k_odd - 1
            f = (k_prob * b - (1 - k_prob)) / b
            
            if f > 0:
                st.success(f"Sugestão Kelly (25% Fracionado): **R$ {bankroll * f * 0.25:.2f}**")
                st.caption(f"Isso representa {(f*0.25*100):.1f}% da sua banca.")
            else:
                st.error("Sem vantagem matemática nesta odd/probabilidade.")

    with c2:
        # Espaço reservado para mais ferramentas
        pass

# ==========================================
# ABA 4: GUIA
# ==========================================
with tab4:
    st.markdown("""
    ### 📖 Como funciona a automação?
    1. **Monitor de Notícias:** Roda a cada 30min buscando lesões e furos de reportagem.
    2. **Busca de Odds:** O sistema varre as casas de apostas automaticamente a cada 2 horas.
    3. **Triagem de IA:** O Llama 3.1 analisa as odds e só libera os sinais que aparecem na Tab 1 se o 'Edge' for positivo.
    
    **Dica:** Sempre confira a aba de Notícias antes de colocar uma aposta, mesmo que o sinal da IA seja bom. Uma notícia de última hora pode ter mudado tudo!
    """)
