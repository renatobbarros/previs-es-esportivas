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
    st.subheader("🔍 Filtros de Oportunidades")
    
    # Filtro de Probabilidade (Predictability +65)
    min_prob_ui = st.slider("Probabilidade Mínima (%)", 0, 100, 50, help="Filtra apenas previsões com alta chance de acerto. Nota: NBA costuma ter probs menores (55-60%).")
    
    # Filtro de Odds
    odd_range = st.slider("Faixa de Odds (@)", 1.0, 10.0, (1.20, 4.0), step=0.1)
    min_odd, max_odd = odd_range
    
    # Filtro de Edge e Confiança
    min_edge_ui = st.slider("Edge Mínimo (%)", 0, 30, 6)
    conf_min_ui = st.select_slider("Confiança Mínima da IA", options=["Baixa", "Média", "Alta"], value="Média")
    
    # Filtro de Data, Esporte e Mercado
    date_filter = st.selectbox("Período dos Jogos", ["Todos", "Hoje", "Amanhã"])
    sport_filter = st.multiselect("Esportes", ["Futebol", "Basquete"], default=["Futebol", "Basquete"])
    market_filter = st.multiselect("Mercados de Interesse", ["Vencedor (ML)", "Gols/Pontos (Over/Under)", "Handicap (Spread)"], default=["Vencedor (ML)", "Gols/Pontos (Over/Under)"])
    
    with st.expander("💡 Entenda os Filtros"):
        st.markdown(f"""
        - **Vencedor (ML)**: Aposta direta em quem ganha o jogo.
        - **Gols/Pontos**: Aposta se o jogo terá mais ou menos pontos/gols que o sugerido.
        - **Handicap**: Vantagem ou desvantagem de pontos para um time (Ignorado se não selecionado).
        - **Esportes**: Filtre entre **NBA/NBB** e os campeonatos de **Futebol**.
        - **Probabilidade**: Chance matemática da previsão acontecer.
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
    
    # Converte tipos para garantir compatibilidade com o editor do Streamlit
    df['Data'] = pd.to_datetime(df['Data']).dt.date
    df['Odd'] = pd.to_numeric(df['Odd'], errors='coerce')
    df['Stake (R$)'] = pd.to_numeric(df['Stake (R$)'], errors='coerce')
    
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
            "Data": st.column_config.DateColumn("Data", format="YYYY-MM-DD"),
            "Odd": st.column_config.NumberColumn("Odd", min_value=1.01, format="%.2f"),
            "Stake (R$)": st.column_config.NumberColumn("Stake (R$)", min_value=0.0, format="%.2f"),
            "Retorno (R$)": st.column_config.Column("Retorno (R$)", disabled=True),
            "Lucro (R$)": st.column_config.Column("Lucro (R$)", disabled=True),
            "Banca Acumulada": st.column_config.Column("Banca Acumulada", disabled=True)
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

# 1. Processamento e Normalização Inicial
processed_signals = []
for s in signals:
    game = s.get("game_info", {})
    market = s.get("market")
    outcome = s.get("outcome")
    outcome_lower = str(outcome).lower().strip()
    
    # Busca de Odd robusta
    m_odds = game.get("best_odds", {}).get(market, {})
    odd_data = m_odds.get(outcome)
    if not odd_data:
        if outcome_lower == "casa": odd_data = m_odds.get("home")
        elif outcome_lower == "home": odd_data = m_odds.get("casa")
        elif outcome_lower == "fora": odd_data = m_odds.get("away")
        elif outcome_lower == "away": odd_data = m_odds.get("fora")
        elif outcome_lower == "empate": odd_data = m_odds.get("draw")
        elif outcome_lower == "draw": odd_data = m_odds.get("empate")
    
    odd = odd_data.get("odd", 0.0) if isinstance(odd_data, dict) else 0.0
    
    # Cálculo de Probabilidade
    prob = s.get("prob", 0)
    if prob <= 0 and market == "h2h":
        h2h_mc = game.get("market_consensus", {}).get("h2h", {})
        m_prob = h2h_mc.get(f"{outcome_lower}_prob", 0) * 100
        if m_prob <= 0:
            alt_key = "home" if outcome_lower == "casa" else "away" if outcome_lower == "fora" else "draw"
            m_prob = h2h_mc.get(f"{alt_key}_prob", 0) * 100
        if m_prob > 0:
            prob = m_prob + s.get("edge", 0)
    
    # Resolve Nome (Prioridade para o 'best_bet' estilo Betnacional)
    team_bet = s.get("best_bet")
    if not team_bet or any(x in team_bet.lower() for x in ["casa", "home", "fora", "away", "draw", "empate", "under", "over", "subir"]):
        if outcome_lower in ["casa", "home"]: team_bet = game.get("home_team", "Casa")
        elif outcome_lower in ["fora", "away"]: team_bet = game.get("away_team", "Fora")
        elif outcome_lower in ["empate", "draw"]: team_bet = "Empate"
        else: 
            # Garante que o número (point) apareça em Totals
            clean_outcome = str(outcome).replace("Over", "Acima de").replace("Under", "Abaixo de").replace("Subir o Ponto", "Acima de").replace("Aposta no Under", "Abaixo de").replace("Sub ", "Abaixo de ")
            team_bet = clean_outcome
    
    # Limpeza final de segurança para garantir o formato "Acima de X"
    if market == "totals" and "de" in team_bet and not any(char.isdigit() for char in team_bet):
        point_val = str(outcome).split()[-1] # Tenta pegar o número do final do outcome original
        team_bet = f"{team_bet} {point_val}"

    # Data do Jogo
    dt_str = game.get("commence_time", "")
    try: dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except: dt_obj = datetime.max

    # Adiciona ao lote processado
    s_processed = s.copy()
    s_processed.update({
        "norm_odd": odd,
        "norm_prob": prob,
        "norm_team": team_bet,
        "dt_obj": dt_obj
    })
    processed_signals.append(s_processed)

# 2. Aplicação de Filtros
filtered = []
hoje = datetime.now().date()
for s in processed_signals:
    # Filtro de Confiança e Edge
    if s.get("edge", 0) < min_edge_ui: continue
    if conf_val_map.get(s.get("confidence", "low"), 0) < conf_map[conf_min_ui]: continue
    
    # Filtro de Probabilidade
    if s.get("norm_prob", 0) < min_prob_ui: continue
    
    # Filtro de Odds
    if not (min_odd <= s.get("norm_odd", 0) <= max_odd): continue
    
    # Filtro de Data
    dt_jogo = s["dt_obj"].date()
    if date_filter == "Hoje" and dt_jogo != hoje: continue
    if date_filter == "Amanhã" and dt_jogo != hoje + pd.Timedelta(days=1): continue
    
    # Filtro de Esporte
    s_sport = s.get("game_info", {}).get("sport", "").lower()
    esporte_alvo = "Futebol" if ("soccer" in s_sport or "football" in s_sport) else "Basquete" if "basketball" in s_sport else "Outros"
    if esporte_alvo not in sport_filter: continue
    
    # Filtro de Mercado
    s_market = s.get("market")
    if "Vencedor (ML)" in market_filter and "Gols/Pontos (Over/Under)" not in market_filter and "Handicap (Spread)" not in market_filter:
        if s_market != "h2h": continue
    if "Gols/Pontos (Over/Under)" in market_filter and "Vencedor (ML)" not in market_filter and "Handicap (Spread)" not in market_filter:
        if s_market != "totals": continue
    
    # Lógica de exclusão robusta
    if "Handicap (Spread)" not in market_filter and s_market == "spreads": continue
    if "Vencedor (ML)" not in market_filter and s_market == "h2h": continue
    if "Gols/Pontos (Over/Under)" not in market_filter and s_market == "totals": continue
    
    if not market_filter: continue
    
    filtered.append(s)

# Ordenação Cronológica
filtered = sorted(filtered, key=lambda x: x["dt_obj"])

if not filtered:
    st.info("Aguardando novas oportunidades do mercado que batam seus filtros atuais de Edge e Confiança...")
else:
    # Layout em Grid (3 colunas)
    for row_idx in range(0, len(filtered), 3):
        cols = st.columns(3)
        for col_idx, s_idx in enumerate(range(row_idx, min(row_idx + 3, len(filtered)))):
            s = filtered[s_idx]
            game = s.get("game_info", {})
            market = s.get("market")
            outcome = s.get("outcome")
            
            # Usa valores normalizados
            team_bet = s["norm_team"]
            odd = s["norm_odd"]
            prob = s["norm_prob"]
            book = "Betnacional"
            
            stake_pct = s.get("recommended_stake_pct", 0)
            stake_brl = max(1.0, (stake_pct / 100) * bankroll) # Mínimo de R$ 1,00 para Betnacional
            display_date = s["dt_obj"].strftime("%d/%m — %H:%M") if s["dt_obj"] != datetime.max else "Data Indisp."

            game_title = f"{game.get('home_team')} x {game.get('away_team')}"
            
            with cols[col_idx]:
                with st.container(border=True):
                    # Header do Card com Data e Badge de Probabilidade
                    prob_html = f"""
                        <span style="background-color: #1e3a8a; color: #93c5fd; padding: 2px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: bold; border: 1px solid #3b82f6;">
                            {prob:.0f}% Chance
                        </span>
                    """ if prob > 0 else ""

                    st.markdown(f"""
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <span style="font-size: 0.85rem; color: #9ca3af; font-weight: 500;">📅 {display_date}</span>
                            {prob_html}
                        </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"#### {game_title}")
                    st.caption(f"🏆 {game.get('league')} | 🏠 {book}")
                    
                    st.metric("Recomendação", team_bet, f"@{odd:.2f}".replace('.', ','))
                    
                    st.write(f"**Stake Sugerida:** R$ {stake_brl:.2f} ({stake_pct:.1f}%)")
                    st.write(f"**Edge Encontrado:** {s.get('edge', 0)*100:.1f}%")
                    
                    with st.expander("📝 Razão da IA"):
                        st.write(s.get('reasoning'))
                    
                    if st.button("✅ Registrar", key=f"auto_add_{s_idx}_{game_title}", use_container_width=True, type="primary"):
                        add_bet_to_history(game_title, team_bet, odd, stake_brl, bankroll)
                        st.success(f"Aposta em '{team_bet}' registrada!")
                        st.rerun()
                    
    # --- Calendário de Eventos Futuros ---
    st.markdown('<div class="section-title">📅 Agenda de Eventos Futuros</div>', unsafe_allow_html=True)
    st.markdown("Acompanhe o horário das partidas recomendadas pela IA.")
    
    agenda_data = []
    for s in filtered:
        game = s.get("game_info", {})
        dt_str = game.get("commence_time", "")
        # Tenta parsear a data para ordenar corretamente
        try:
            dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            display_date = dt_obj.strftime("%d/%m/%Y às %H:%M")
        except:
            dt_obj = datetime.max  # Coloca os desconhecidos no final
            display_date = dt_str
            
        # Extrai informações específicas para o card da agenda (Usa os valores já normalizados)
        item_team = s.get("norm_team", s.get("outcome"))
        # Limpeza final para termos técnicos que escaparam
        item_team = str(item_team).replace("Sub ", "Abaixo de ").replace("Subir o Ponto", "Acima de").replace("Aposta no Under", "Abaixo de").replace(" pontos", "")
        
        item_stake_brl = max(1.0, (s.get("recommended_stake_pct", 0) / 100) * bankroll)
        
        agenda_data.append({
            "dt_obj": s.get("dt_obj", datetime.max),
            "Horário (BRT)": display_date,
            "Esporte/Liga": game.get('league', 'Desconhecido'),
            "Jogo": f"{game.get('home_team')} x {game.get('away_team')}",
            "Quem Apostar": item_team,
            "Quanto Apostar": f"R$ {item_stake_brl:.2f}",
            "Perspectiva": f"{s.get('edge', 0)*100:.1f}% de Edge",
            "prob": s.get("norm_prob", 0)
        })
        
    if agenda_data:
        # Ordena a agenda pelo objeto datetime real (do mais próximo para o mais distante)
        agenda_data = sorted(agenda_data, key=lambda x: x["dt_obj"])
        
        # Visualização em Grid
        agenda_cols = st.columns(3 if len(agenda_data) >= 3 else len(agenda_data))
        for i, item in enumerate(agenda_data):
            with agenda_cols[i % len(agenda_cols)]:
                with st.container(border=True):
                    # Badge de Probabilidade para Agenda
                    prob = item.get("prob", 0)
                    prob_html = f"""
                        <div style="text-align: right; margin-bottom: -20px;">
                            <span style="background-color: #064e3b; color: #6ee7b7; padding: 2px 8px; border-radius: 6px; font-size: 0.7rem; font-weight: bold; border: 1px solid #10b981;">
                                {prob:.0f}% Chance
                            </span>
                        </div>
                    """ if prob > 0 else ""
                    
                    st.markdown(prob_html, unsafe_allow_html=True)
                    st.markdown(f"**{item['Jogo']}**")
                    st.caption(f"⏰ {item['Horário (BRT)']} | 🏆 {item['Esporte/Liga']}")
                    st.write(f"👉 **Em quem:** {item['Quem Apostar']}")
                    st.write(f"💰 **Quanto:** {item['Quanto Apostar']}")
                    st.write(f"📈 **Edge:** {item['Perspectiva']}")
    else:
        st.info("Nenhum evento agendado nos filtros atuais.")
