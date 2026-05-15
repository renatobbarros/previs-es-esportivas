import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import select
from core.database import AsyncSessionLocal, Sinal, Aposta
from core.logger import logger

class BacktestManager:
    @staticmethod
    async def run_backtest(inicio: datetime, fim: datetime, filtros: dict = {}):
        async with AsyncSessionLocal() as session:
            # 1. Busca todos os sinais liquidados no período
            q = select(Sinal).where(
                Sinal.criado_em >= inicio,
                Sinal.criado_em <= fim,
                Sinal.resultado != 'pendente'
            )
            
            # Aplica filtros
            if filtros.get('esporte'):
                q = q.where(Sinal.esporte == filtros['esporte'])
            if filtros.get('edge_min'):
                q = q.where(Sinal.edge_pct >= filtros['edge_min'])
            if filtros.get('odd_min'):
                q = q.where(Sinal.odd >= filtros['odd_min'])
            if filtros.get('odd_max'):
                q = q.where(Sinal.odd <= filtros['odd_max'])
            
            res = await session.execute(q)
            sinais = res.scalars().all()

            if not sinais:
                return None

            # Converte para DataFrame para cálculos vetoriais
            df = pd.DataFrame([{
                'id': s.id,
                'odd': float(s.odd),
                'prob_real': float(s.prob_real),
                'resultado': s.resultado,
                'edge': float(s.edge_pct)
            } for s in sinais])

            # Cálculos de Performance
            df['profit'] = np.where(df['resultado'] == 'ganhou', df['odd'] - 1, 
                           np.where(df['resultado'] == 'perdeu', -1, 0))
            
            total_sinais = len(df)
            wins = len(df[df['resultado'] == 'ganhou'])
            win_rate = (wins / total_sinais) if total_sinais > 0 else 0
            
            roi_medio = df['profit'].mean() * 100
            roi_mediano = df['profit'].median() * 100
            std_dev = df['profit'].std()
            sharpe = (roi_medio / (std_dev * 100)) if std_dev > 0 else 0

            # Drawdown Máximo (Sequência de perdas)
            current_dd = 0
            max_dd = 0
            for p in df['profit']:
                if p <= 0:
                    current_dd += 1
                else:
                    max_dd = max(max_dd, current_dd)
                    current_dd = 0
            max_dd = max(max_dd, current_dd)

            # Análise de Calibração
            bins = [0.5, 0.6, 0.7, 0.8, 1.0]
            df['prob_bin'] = pd.cut(df['prob_real'], bins=bins)
            calibration = df.groupby('prob_bin', observed=False).agg(
                count=('id', 'count'),
                win_rate_real=('profit', lambda x: (x > 0).mean()),
                prob_media=('prob_real', 'mean')
            ).to_dict('index')

            return {
                "periodo": f"{inicio.date()} a {fim.date()}",
                "total": total_sinais,
                "win_rate": win_rate,
                "roi_medio": roi_medio,
                "sharpe": sharpe,
                "max_dd": max_dd,
                "calibration": calibration
            }

    @staticmethod
    def format_report(results: dict) -> str:
        if not results:
            return "❌ Nenhum dado encontrado para o período."

        msg = (
            f"<b>📊 BACKTEST: {results['periodo']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Total Sinais: <b>{results['total']}</b>\n"
            f"🔥 Win Rate: <b>{results['win_rate']:.1% Rose}</b>\n"
            f"💰 ROI Médio: <b>{results['roi_medio']:+.2f}%</b>\n"
            f"📈 Sharpe Ratio: <b>{results['sharpe']:.2f}</b>\n"
            f"📉 Max Drawdown: <b>{results['max_dd']} perdas</b>\n\n"
            f"<b>🎯 CALIBRAÇÃO DO MODELO:</b>\n"
        )

        for bin_range, stats in results['calibration'].items():
            if stats['count'] > 0:
                diff = (stats['win_rate_real'] - stats['prob_media']) * 100
                alert = "⚠️ Over" if diff < -10 else ""
                msg += f"• {bin_range}: {stats['win_rate_real']:.1%} (Est: {stats['prob_media']:.1%}) {alert}\n"

        return msg
