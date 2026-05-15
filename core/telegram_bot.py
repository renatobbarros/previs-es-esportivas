import os
import asyncio
import html
import functools
from datetime import datetime, timedelta
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from telegram.constants import ParseMode
from sqlalchemy import select
from core.database import AsyncSessionLocal, DataService, Usuario, Sinal, Aposta
from config import settings
from core.logger import logger

# --- MIDDLEWARE / DECORATOR ---

def requer_usuario_ativo(func):
    """Decorator para garantir que apenas usuários cadastrados e ativos usem os comandos."""
    @functools.wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        tid = update.effective_user.id
        async with AsyncSessionLocal() as session:
            ds = DataService(session)
            user = await ds.get_user_by_telegram_id(tid)
            
            if not user:
                await update.message.reply_text("🚫 <b>Acesso Negado</b>\nVocê precisa de um convite para usar este bot.", parse_mode=ParseMode.HTML)
                return
            
            if user.status != 'ativo':
                await update.message.reply_text("⏳ <b>Acesso Pendente</b>\nSua conta ainda não foi ativada pelo administrador.", parse_mode=ParseMode.HTML)
                return
            
            # Passa o objeto user para o handler economizar uma query
            return await func(self, update, context, user=user, *args, **kwargs)
    return wrapper

# --- BOT CLASS ---

class SportsEdgeBot:
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.owner_id = settings.OWNER_TELEGRAM_ID

    def _escape(self, text):
        return html.escape(str(text))

    # --- COMANDOS MULTITENANT ---

    @requer_usuario_ativo
    async def status_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user: Usuario):
        async with AsyncSessionLocal() as session:
            ds = DataService(session)
            stats = await ds.get_user_stats(user.id)
            
            var_pct = ((user.banca_atual / user.banca_inicial) - 1) * 100
            # Comissão estimada (ex: 10% do lucro bruto acumulado ou algo similar)
            # Aqui simplificamos: 10% do lucro dos últimos 30 dias se positivo
            comissao = max(0, stats['profit_30d'] * user.profit_share_pct)

            msg = (
                f"<b>📊 STATUS DE {self._escape(user.nome.upper())}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Banca Atual: <b>R$ {user.banca_atual:,.2f}</b>\n"
                f"🌱 Banca Inicial: <b>R$ {user.banca_inicial:,.2f}</b>\n"
                f"📈 Variação: <b>{var_pct:+.2f}%</b>\n\n"
                f"🔥 Win Rate (30d): <b>{stats['win_rate_30d']:.1f}%</b>\n"
                f"📊 ROI (7d): <b>{stats['roi_7d']:.2f}%</b>\n\n"
                f"💸 Comissão Estimada: <b>R$ {comissao:,.2f}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    @requer_usuario_ativo
    async def apostashoje_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user: Usuario):
        async with AsyncSessionLocal() as session:
            # Busca sinais criados hoje
            hoje = datetime.now().date()
            q = select(Sinal).where(Sinal.criado_em >= hoje).order_by(Sinal.criado_em.asc())
            sinais = (await session.execute(q)).scalars().all()
            
            if not sinais:
                await update.message.reply_text("📭 Nenhum sinal gerado hoje até o momento.")
                return

            # Busca apostas que o usuário JÁ fez nesses sinais
            q_bets = select(Aposta).where(Aposta.usuario_id == user.id, Aposta.sinal_id.in_([s.id for s in sinais]))
            user_bets = {b.sinal_id: b for b in (await session.execute(q_bets)).scalars().all()}

            msg = "<b>📅 SINAIS DE HOJE</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            for s in sinais:
                status_icon = "⏳"
                if s.id in user_bets:
                    status_icon = "✅" if user_bets[s.id].resultado != 'perdeu' else "❌"
                
                msg += (
                    f"{status_icon} <b>{self._escape(s.jogo)}</b>\n"
                    f"✅ {s.odd:.2f} | Stake: R$ {s.stake_sugerida:,.2f}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                )
            
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    @requer_usuario_ativo
    async def minhasapostas_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user: Usuario):
        status_filter = context.args[0] if context.args else None
        page = int(context.args[1]) if len(context.args) > 1 else 1
        
        async with AsyncSessionLocal() as session:
            ds = DataService(session)
            apostas = await ds.get_user_history(user.id, status=status_filter, page=page)
            
            if not apostas:
                await update.message.reply_text("📭 Nenhuma aposta encontrada com esses filtros.")
                return

            msg = f"<b>📜 HISTÓRICO ({status_filter or 'TODAS'})</b>\n"
            msg += f"Página {page}\n━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for a in apostas:
                res_emoji = {"ganhou": "✅", "perdeu": "❌", "pendente": "⏳"}.get(a.resultado, "❓")
                lucro = a.lucro_liquido or 0
                msg += (
                    f"{res_emoji} {a.stake_real:,.2f} @ {a.resultado}\n"
                    f"💰 Lucro: <b>R$ {lucro:+.2f}</b>\n"
                    f"📅 {a.apostada_em.strftime('%d/%m %H:%M')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                )
            
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    @requer_usuario_ativo
    async def editarbanca_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user: Usuario):
        if not context.args:
            await update.message.reply_text("Use: /editarbanca {valor}\nEx: /editarbanca 150.50")
            return
            
        try:
            novo_valor = float(context.args[0].replace(',', '.'))
            if novo_valor < 0: raise ValueError
        except ValueError:
            await update.message.reply_text("Valor inválido.")
            return

        async with AsyncSessionLocal() as session:
            ds = DataService(session)
            # Re-fetch user to attach to current session
            db_user = await ds.get_user_by_telegram_id(user.telegram_id)
            delta = await ds.record_bankroll_adjustment(db_user, novo_valor, "ajuste_manual")
            
            await update.message.reply_text(f"✅ Banca ajustada para <b>R$ {novo_valor:,.2f}</b> (Delta: R$ {delta:+.2f})", parse_mode=ParseMode.HTML)
            
            # Notifica Admin
            admin_msg = f"⚠️ <b>AJUSTE DE BANCA</b>\nUsuário: @{user.username}\nNovo: R$ {novo_valor:,.2f}\nDelta: R$ {delta:+.2f}"
            await context.bot.send_message(chat_id=self.owner_id, text=admin_msg, parse_mode=ParseMode.HTML)

    # --- COMANDOS ADMIN E ONBOARDING (REAPROVEITADOS) ---
    # ... [Aqui entrariam os métodos de /start, /convidar, /ativar do passo anterior] ...
    # Para brevidade, focarei na estrutura de execução.

    async def fecharciclo_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != self.owner_id: return
        if not context.args: return
        
        uid = int(context.args[0])
        from core.comissao import CommissionManager
        stats, ciclo = await CommissionManager.fechar_ciclo_usuario(uid)
        
        msg = (
            f"<b>✅ CICLO FECHADO - USUÁRIO {uid}</b>\n\n"
            f"📈 Lucro Líquido: R$ {stats['lucro_liquido']:,.2f}\n"
            f"💸 Comissão (10%): <b>R$ {stats['comissao_devida']:,.2f}</b>\n\n"
            f"O usuário foi notificado."
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        
        # Notifica o usuário
        user_msg = (
            f"<b>🧾 FATURAMENTO SEMANAL</b>\n\n"
            f"Seu ciclo de {ciclo.inicio_ciclo.strftime('%d/%m')} a {ciclo.fim_ciclo.strftime('%d/%m')} foi fechado.\n"
            f"Lucro Líquido: R$ {stats['lucro_liquido']:,.2f}\n"
            f"Comissão Devida: <b>R$ {stats['comissao_devida']:,.2f}</b>\n\n"
            f"Por favor, realize o pagamento via PIX para manter sua conta ativa."
        )
        await context.bot.send_message(chat_id=ciclo.usuario_id, text=user_msg, parse_mode=ParseMode.HTML)

    async def send_signal(self, signal_data: dict):
        """Broadcast de sinal para todos os usuários ativos."""
        msg = (
            f"🎯 <b>NOVA OPORTUNIDADE ENCONTRADA</b>\n"
            f"⚽ <b>{self._escape(signal_data['match_description'])}</b>\n"
            f"🏆 {self._escape(signal_data['league'])}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Aposta: <b>{self._escape(signal_data['best_bet'])}</b>\n"
            f"📊 Odds: <b>{signal_data['recommended_odds']:.2f}</b>\n"
            f"🔥 Confiança: {signal_data['signal_quality']}\n"
            f"💰 Stake Sugerida: <b>R$ {signal_data['suggested_stake_units']:,.2f}</b>\n"
        )
        
        # Adiciona Line Movement se disponível
        if 'line_movement' in signal_data:
            msg += f"\n📈 Movimento: {signal_data['line_movement']}"
            
        msg += (
            f"\n\n🤖 <i>{self._escape(signal_data['reasoning'][:150])}...</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        
        keyboard = [
            [
                InlineKeyboardButton(f"✅ Apostei R$ {signal_data['suggested_stake_units']:.2f}", callback_data=f"bet_std_{signal_data['id']}"),
            ],
            [
                InlineKeyboardButton("✏️ Valor Diferente", callback_data=f"bet_custom_{signal_data['id']}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Busca todos os usuários ativos
        async with AsyncSessionLocal() as session:
            ds = DataService(session)
            # Simplificado: enviando apenas para o owner no teste, 
            # em prod buscaria todos os tid ativos
            await self.app.bot.send_message(
                chat_id=self.owner_id, 
                text=msg, 
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

    def run(self):
        self.app = ApplicationBuilder().token(self.token).build()
        
        # Handlers
        self.app.add_handler(CommandHandler("status", self.status_cmd))
        self.app.add_handler(CommandHandler("apostashoje", self.apostashoje_cmd))
        self.app.add_handler(CommandHandler("minhasapostas", self.minhasapostas_cmd))
        self.app.add_handler(CommandHandler("editarbanca", self.editarbanca_cmd))
        self.app.add_handler(CommandHandler("fecharciclo", self.fecharciclo_cmd))
        self.app.add_handler(CommandHandler("auditoria", self.auditoria_cmd))
        self.app.add_handler(CommandHandler("backtest", self.backtest_cmd))
        
        logger.info("bot_started", mode="multitenant_active")
        self.app.run_polling()

    async def backtest_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != self.owner_id: return
        dias = int(context.args[0]) if context.args else 7
        
        await update.message.reply_text(f"⏳ Rodando backtest dos últimos {dias} dias... Isso pode levar alguns segundos.")
        
        from core.backtesting import BacktestManager
        inicio = datetime.now() - timedelta(days=dias)
        fim = datetime.now()
        
        results = await BacktestManager.run_backtest(inicio, fim)
        msg = BacktestManager.format_report(results)
        
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    async def auditoria_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != self.owner_id: return
        if len(context.args) < 2:
            await update.message.reply_text("Use: /auditoria {usuario_id} {mes}")
            return

        uid = int(context.args[0])
        mes = int(context.args[1])
        
        async with AsyncSessionLocal() as session:
            ds = DataService(session)
            logs = await ds.get_audit_trail(uid, mes)
            
            if not logs:
                await update.message.reply_text(f"📭 Nenhum registro de auditoria para o usuário {uid} no mês {mes}.")
                return

            msg = f"<b>🕵️ AUDITORIA - USUÁRIO {uid} (Mês {mes})</b>\n\n"
            for l in logs[:10]: # Mostra apenas os últimos 10 para não exceder limite do Telegram
                msg += (
                    f"📅 {l.alterado_em.strftime('%d/%m %H:%M')}\n"
                    f"📦 Tabela: {l.tabela} | ID: {l.registro_id}\n"
                    f"👤 Por: {l.alterado_por}\n"
                    f"🔄 {l.campo_alterado}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                )
            
            # Verifica Integridade
            integ = await ds.verificar_integridade()
            status_icon = "✅" if integ['status'] == 'ok' else "🚨"
            msg += f"\n{status_icon} <b>INTEGRIDADE DA CADEIA: {integ['status'].upper()}</b>"
            
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        
        # Adicionar aqui os handlers de onboarding do passo anterior...
        
        logger.info("bot_started", mode="multitenant_active")
        app.run_polling()
