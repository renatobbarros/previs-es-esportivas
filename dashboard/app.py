"""
dashboard/app.py — Dashboard PRO do Sports Edge AI
Interface única e intuitiva com monitoramento de notícias e sinais integrados.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import altair as alt
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

# Estilo CSS Customizado para o Modo Dark
st.markdown("""
    <style>
    /* Tipografia e espaçamentos - Cores para Modo Dark */
    .stMetric { background-color: #1e1e1e; padding: 15px; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
    .urgent-card { background-color: #3b1c1c; padding: 15px; border-radius: 12px; border-left: 6px solid #ff4d4f; margin-bottom: 15px; color: #fdfdfd; }
    .news-card { background-color: #142838; padding: 15px; border-radius: 12px; border-left: 6px solid #1890ff; margin-bottom: 15px; color: #fdfdfd; }
    h1, h2, h3 { font-family: 'Inter', sans-serif; font-weight: 600; color: #ffffff; }
    .section-title { margin-top: 40px; margin-bottom: 20px; font-size: 24px; font-weight: 700; color: #e5e7eb; border-bottom: 2px solid #374151; padding-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────
# Funções de Dados e Estado
# ─────────────────────────────────────────────────────────
HISTORICO_FILE = config.DATA_DIR / "historico_apostas.csv"

def load_json(path: Path):
    if path.exists():
        try: return json.loads(path.read_text())
        except: return []
    return []

def get_latest_signals():
    files = sorted(list(config.SIGNALS_DIR.glob("signals_*.json")), reverse=True)
    return load_json(files[0]) if files else []

def add_bet_to_history(game: str, bet: str, odd: float, stake: float, bankroll: float):
    novo_registro = {
        "Data": datetime.today().strftime("%Y-%m-%d"),
        "Jogo": game,
        "Aposta": bet,
        "Odd": odd,
        "Stake (R$)": stake,
        "Resultado": "⏳ Pendente",
        "Retorno (R$)": 0.0,
        "Lucro (R$)": 0.0,
        "Banca Acumulada": bankroll
    }
    if HISTORICO_FILE.exists():
        df_hist = pd.read_csv(HISTORICO_FILE)
        df_hist = pd.concat([df_hist, pd.DataFrame([novo_registro])], ignore_index=True)
    else:
        df_hist = pd.DataFrame([novo_registro])
    df_hist.to_csv(HISTORICO_FILE, index=False)

# ─────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎯 Controle da Banca")
    st.markdown("Ajuste sua banca para calibrar as stakes automáticas.")
    bankroll = st.number_input("💸 Sua Banca Total (R$)", min_value=10.0, value=float(config.DEFAULT_BANKROLL))
    
    st.divider()
    st.subheader("Filtros de Inteligência")
    min_edge_ui = st.slider("Edge Mínimo (%)", 0, 30, 6)
    conf_min_ui = st.select_slider("Confiança Mínima da IA", options=["Baixa", "Média", "Alta"], value="Média")
    
    with st.expander("💡 Entenda os Filtros"):
        st.markdown("""
        - **Edge**: É a "vantagem matemática" da IA. Exemplo: se a IA calcula que o time tem 60% de chance de ganhar, mas a odd da casa reflete apenas 50%, você tem um Edge (vantagem) de 10%.
        - **Confiança Mínima**: Nível de certeza da IA naquela previsão, baseado em volume de dados, lesões e histórico recente.
        """)
    
    st.divider()
    st.caption("O sistema monitora o mercado em tempo real.")

# ─────────────────────────────────────────────────────────
# UI Principal
# ─────────────────────────────────────────────────────────
st.title("Painel de Inteligência Sports Edge")
st.markdown("Bem-vindo ao seu ecossistema unificado de análises esportivas e controle de banca.")

# ==========================================
# SEÇÃO 1: NOTÍCIAS DE ÚLTIMA HORA
# ==========================================
urgent = load_json(config.DATA_DIR / "urgent_alerts.json")
news = load_json(config.DATA_DIR / "news_alerts.json")

if urgent or news:
    st.markdown('<div class="section-title">🔔 Radar de Notícias</div>', unsafe_allow_html=True)
    n1, n2 = st.columns([1, 1])
    with n1:
        for u in urgent[:2]:
            teams = u.get('teams_affected')
            team_str = teams[0] if teams else 'Esporte'
            st.markdown(f"""<div class="urgent-card">
                <strong>🚨 URGENTE: {team_str}</strong><br>
                {u.get('title', 'Sem título')}<br>
                <small>Impacto: {u.get('impact', 'N/A')} | Ação: {u.get('action', 'N/A')}</small>
            </div>""", unsafe_allow_html=True)
    with n2:
        for n in news[:2]:
            st.markdown(f"""<div class="news-card">
                <strong>🔹 {n.get('sport', 'other').upper()}</strong><br>
                {n.get('title', 'Sem título')}<br>
                <small>Impacto: {n.get('impact', 'N/A')}</small>
            </div>""", unsafe_allow_html=True)

# ==========================================
# SEÇÃO 2: PERFORMANCE & HISTÓRICO
# ==========================================
st.markdown('<div class="section-title">📊 Evolução da sua Banca</div>', unsafe_allow_html=True)

if HISTORICO_FILE.exists():
    df = pd.read_csv(HISTORICO_FILE)
    
    wins = len(df[df["Resultado"] == "✅ Ganhou"])
    losses = len(df[df["Resultado"] == "❌ Perdeu"])
    total_resolvidos = wins + losses
    win_rate = (wins/total_resolvidos*100) if total_resolvidos > 0 else 0
    lucro = df["Lucro (R$)"].sum()
    total_apostado = df[df["Resultado"] != "⏳ Pendente"]['Stake (R$)'].sum()
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Win Rate", f"{win_rate:.1f}%", f"{wins}W - {losses}L")
    m2.metric("Lucro Acumulado", f"R$ {lucro:.2f}", delta_color="normal")
    m3.metric("ROI", f"{(lucro/total_apostado*100):.1f}%" if total_apostado > 0 else "0%")
    m4.metric("Apostas Pendentes", f"{len(df[df['Resultado'] == '⏳ Pendente'])}")
    
    st.write("") 
    
    # Gráficos Altair
    df_chart = df.copy()
    df_chart['Data'] = pd.to_datetime(df_chart['Data'])
    daily_profit = df_chart.groupby('Data')['Lucro (R$)'].sum().reset_index()
    daily_profit['Lucro Acumulado'] = daily_profit['Lucro (R$)'].cumsum()
    
    if not daily_profit.empty:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("**Crescimento Acumulado**")
            area_chart = alt.Chart(daily_profit).mark_area(
                line={'color':'#1890ff'},
                color=alt.Gradient(
                    gradient='linear',
                    stops=[alt.GradientStop(color='#1890ff', offset=0),
                           alt.GradientStop(color='white', offset=1)],
                    x1=1, x2=1, y1=1, y2=0
                )
            ).encode(
                x=alt.X('Data:T', title='Data', axis=alt.Axis(format='%d/%m')),
                y=alt.Y('Lucro Acumulado:Q', title='Lucro Acumulado (R$)'),
                tooltip=['Data:T', 'Lucro Acumulado:Q']
            ).properties(height=250)
            st.altair_chart(area_chart, use_container_width=True)
            
        with c2:
            st.markdown("**Resultado Diário**")
            bar_chart = alt.Chart(daily_profit).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X('Data:T', title='Data', axis=alt.Axis(format='%d/%m')),
                y=alt.Y('Lucro (R$):Q', title='P&L (R$)'),
                color=alt.condition(
                    alt.datum['Lucro (R$)'] > 0,
                    alt.value('#52c41a'), 
                    alt.value('#ff4d4f')  
                ),
                tooltip=['Data:T', 'Lucro (R$):Q']
            ).properties(height=250)
            st.altair_chart(bar_chart, use_container_width=True)

    # Editor Planilha
    st.markdown("**Acompanhamento de Apostas** (Para apagar: marque a caixinha na primeira coluna da linha e aperte a tecla **Delete**)")
    edited_df = st.data_editor(
        df,
        column_config={
            "Resultado": st.column_config.SelectboxColumn(
                "Resultado da Aposta",
                options=["⏳ Pendente", "✅ Ganhou", "❌ Perdeu", "🔄 Reembolso"],
                required=True
            ),
            "Data": st.column_config.Column(disabled=True),
            "Retorno (R$)": st.column_config.Column(disabled=True),
            "Lucro (R$)": st.column_config.Column(disabled=True),
            "Banca Acumulada": st.column_config.Column(disabled=True)
        },
        use_container_width=True,
        hide_index=False, # Precisa ser False para a caixinha de exclusão aparecer
        num_rows="dynamic"
    )
    
    if not edited_df.equals(df):
        # Limpa linhas vazias que o usuário possa ter adicionado acidentalmente
        edited_df = edited_df.dropna(subset=['Jogo']).copy()
        
        for idx in edited_df.index:
            new_res = edited_df.at[idx, "Resultado"]
            try:
                odd = float(edited_df.at[idx, "Odd"])
            except (ValueError, TypeError):
                odd = 1.0
                edited_df.at[idx, "Odd"] = 1.0
                
            try:
                stake = float(edited_df.at[idx, "Stake (R$)"])
            except (ValueError, TypeError):
                stake = 0.0
                edited_df.at[idx, "Stake (R$)"] = 0.0
            
            if new_res == "✅ Ganhou":
                edited_df.at[idx, "Retorno (R$)"] = stake * odd
                edited_df.at[idx, "Lucro (R$)"] = (stake * odd) - stake
            elif new_res == "❌ Perdeu":
                edited_df.at[idx, "Retorno (R$)"] = 0.0
                edited_df.at[idx, "Lucro (R$)"] = -stake
            elif new_res == "🔄 Reembolso":
                edited_df.at[idx, "Retorno (R$)"] = stake
                edited_df.at[idx, "Lucro (R$)"] = 0.0
            else: 
                edited_df.at[idx, "Retorno (R$)"] = 0.0
                edited_df.at[idx, "Lucro (R$)"] = 0.0
        
        edited_df.to_csv(HISTORICO_FILE, index=False)
        st.success("Histórico e lucros atualizados com sucesso!")
        st.rerun()

else:
    st.info("Você ainda não tem apostas registradas. O dashboard de performance aparecerá aqui assim que a primeira aposta for feita.")

# ==========================================
# SEÇÃO 3: OPORTUNIDADES DA IA (SINAIS)
# ==========================================
st.markdown('<div class="section-title">🎯 Recomendações da IA (Value Bets)</div>', unsafe_allow_html=True)
signals = get_latest_signals()

conf_map = {"Baixa": 0, "Média": 1, "Alta": 2}
conf_val_map = {"low": 0, "medium": 1, "high": 2}

filtered = [
    s for s in signals 
    if s.get("edge", 0) >= min_edge_ui and 
    conf_val_map.get(s.get("confidence", "low"), 0) >= conf_map[conf_min_ui]
]

if not filtered:
    st.info("Aguardando novas oportunidades do mercado que batam seus filtros atuais de Edge e Confiança...")
else:
    cols = st.columns(len(filtered) if len(filtered) < 3 else 3)
    for i, s in enumerate(filtered):
        game = s.get("game_info", {})
        bet = s.get("best_bet")
        team_bet = game.get(f"{bet}_team") if bet in ["home", "away"] else "Empate"
        odd = game.get("best_odds", {}).get(bet, {}).get("odd", 0)
        book = "Betnacional" # Forçado para o usuário

        
        stake_pct = s.get("recommended_stake_pct", 0)
        stake_brl = (stake_pct / 100) * bankroll
        
        game_title = f"{game.get('home_team')} x {game.get('away_team')}"
        
        col_idx = i % 3
        with cols[col_idx]:
            with st.container(border=True):
                st.markdown(f"#### {game_title}")
                st.caption(f"🏆 {game.get('league')} | 🏠 {book}")
                
                st.metric("Recomendação", team_bet, f"@{odd:.2f}")
                
                st.write(f"**Stake Sugerida:** R$ {stake_brl:.2f} ({stake_pct:.1f}%)")
                st.write(f"**Edge Encontrado:** {s.get('edge', 0)*100:.1f}%")
                
                with st.expander("📝 Razão da IA"):
                    st.write(s.get('reasoning'))
                
                if st.button("✅ Registrar na Performance", key=f"auto_add_{i}_{game_title}", use_container_width=True, type="primary"):
                    add_bet_to_history(game_title, team_bet, odd, stake_brl, bankroll)
                    st.success(f"Aposta em '{team_bet}' registrada como Pendente!")
                    st.rerun()
