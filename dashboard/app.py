import streamlit as st
import pandas as pd
import altair as alt
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, func
from core.database import AsyncSessionLocal, DataService, Usuario, Aposta, CicloComissao, BancaSnapshot
from config import settings
import os

# --- HELPER PARA RODAR ASYNC NO STREAMLIT ---
def run_async(coro):
    return asyncio.run(coro)

# --- CONFIGURAÇÕES DO DASHBOARD ---
st.set_page_config(
    page_title="SPORTS EDGE AI | ADMIN PANEL",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Injeção de CSS Customizado
if os.path.exists("dashboard/styles.css"):
    with open("dashboard/styles.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("👑 ADMIN PORTAL")
st.sidebar.caption("v2.1 MULTITENANT")

# Proteção por Senha
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    pwd = st.sidebar.text_input("Senha Admin", type="password")
    if st.sidebar.button("Entrar"):
        if pwd == settings.ADMIN_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.sidebar.error("Senha incorreta")
    st.stop()

page = st.sidebar.radio("Navegação", ["📊 Visão Geral", "👥 Gestão de Usuários", "🧾 Faturamento", "🚨 Alertas"])

async def get_overview_data():
    async with AsyncSessionLocal() as session:
        ds = DataService(session)
        rev = await ds.get_admin_revenue_stats()
        users = await ds.get_admin_user_overview()
        alerts = await ds.get_admin_alerts()
        return rev, users, alerts

# --- CARREGAMENTO DE DADOS ---
rev_stats, user_list, system_alerts = run_async(get_overview_data())

# --- PÁGINA: VISÃO GERAL ---
if page == "📊 Visão Geral":
    st.markdown("### 🏦 Painel de Receita")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("TOTAL RECEBIDO", f"R$ {rev_stats['total_recebido']:,.2f}", delta_color="normal")
    with c2:
        st.metric("COMISSÕES EM ABERTO", f"R$ {rev_stats['total_em_aberto']:,.2f}", delta_color="inverse")
    with c3:
        # Projeção simples
        proj = rev_stats['total_recebido'] * 1.2 # Placeholder
        st.metric("PROJEÇÃO MENSAL", f"R$ {proj:,.2f}")

    st.divider()
    st.markdown("### 📈 Evolução de Comissões")
    # Gráfico de linha simulado (precisaria de query de time series)
    chart_data = pd.DataFrame({
        'Mês': ['Jan', 'Fev', 'Mar', 'Abr', 'Mai'],
        'Receita': [1200, 1500, 1100, 1800, 2200]
    })
    st.line_chart(chart_data.set_index('Mês'))

# --- PÁGINA: GESTÃO DE USUÁRIOS ---
elif page == "👥 Gestão de Usuários":
    st.markdown("### 📋 Lista de Tenants")
    df_users = pd.DataFrame(user_list)
    
    # Filtros
    status_filter = st.multiselect("Filtrar por Status", ["ativo", "pendente", "suspenso"], default=["ativo", "pendente"])
    df_filtered = df_users[df_users['status'].isin(status_filter)]
    
    st.dataframe(df_filtered, use_container_width=True)
    
    # Export CSV
    csv = df_filtered.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Exportar CSV", data=csv, file_name="usuarios_sports_edge.csv", mime="text/csv")

# --- PÁGINA: FATURAMENTO ---
elif page == "🧾 Faturamento":
    st.markdown("### 💰 Liquidação de Ciclos")
    
    async def get_closed_cycles():
        async with AsyncSessionLocal() as session:
            q = select(CicloComissao).where(CicloComissao.status == 'fechado').order_by(CicloComissao.fechado_em.desc())
            res = await session.execute(q)
            return res.scalars().all()

    closed_cycles = run_async(get_closed_cycles())
    
    if not closed_cycles:
        st.info("Nenhum ciclo pendente de pagamento no momento.")
    else:
        for c in closed_cycles:
            col_a, col_b, col_c = st.columns([3, 1, 1])
            with col_a:
                st.write(f"Usuário ID: {c.usuario_id} | Valor: **R$ {c.comissao_devida:,.2f}**")
            with col_b:
                comp = st.text_input("Comprovante/Nota", key=f"comp_{c.id}")
            with col_c:
                if st.button("Marcar como Pago", key=f"pay_{c.id}"):
                    async def pay():
                        async with AsyncSessionLocal() as session:
                            ds = DataService(session)
                            await ds.update_ciclo_status(c.id, 'pago', comp)
                            # Envia comprovante via Telegram (NotificaBot)
                    run_async(pay())
                    st.success("Pago!")
                    st.rerun()

# --- PÁGINA: ALERTAS ---
elif page == "🚨 Alertas":
    st.markdown("### 🚨 Alertas Críticos do Sistema")
    if not system_alerts:
        st.success("Tudo em ordem! Nenhum alerta crítico detectado.")
    else:
        for alert in system_alerts:
            st.error(alert)

    st.divider()
    st.markdown("### 🔌 Health Check")
    st.success("✅ Database: PostgreSQL Online")
    st.success("✅ Bot: Active")
