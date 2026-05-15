import os
import sys
import asyncio
import pandas as pd
from datetime import datetime
from pathlib import Path

# Adiciona o diretório raiz ao path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import settings
from src.odds_fetcher import OddsFetcher
from src.telegram_bot import send_telegram_message

async def settle_bets():
    csv_path = settings.DATA_DIR / "historico_apostas.csv"
    if not csv_path.exists():
        print("Histórico de apostas não encontrado.")
        return

    df = pd.read_csv(csv_path)
    pending_mask = df['Resultado'] == '⏳ Pendente'
    if not pending_mask.any():
        print("Nenhuma aposta pendente para liquidar.")
        return

    print(f"Liquidando {pending_mask.sum()} apostas...")
    
    fetcher = OddsFetcher()
    # Usa todas as ligas configuradas
    sports_to_check = settings.ALL_LEAGUES
    
    all_scores = {}
    for sport in sports_to_check:
        scores = await fetcher.get_recent_scores(sport)
        for s in scores:
            key = f"{s['home_team']} x {s['away_team']}".lower()
            all_scores[key] = s

    settled_count = 0
    total_profit = 0

    for idx, row in df[pending_mask].iterrows():
        jogo_key = row['Jogo'].lower()
        # Tenta match exato ou parcial
        match = None
        for key, score_data in all_scores.items():
            if jogo_key in key or key in jogo_key:
                match = score_data
                break
        
        if match and match.get('completed'):
            home_score = int(match['scores'][0]['score'])
            away_score = int(match['scores'][1]['score'])
            total_goals = home_score + away_score
            
            aposta = row['Aposta']
            ganhou = False
            
            # Lógica simples de validação
            if "Abaixo de" in aposta:
                limit = float(aposta.split()[-1])
                if total_goals < limit: ganhou = True
            elif "Acima de" in aposta:
                limit = float(aposta.split()[-1])
                if total_goals > limit: ganhou = True
            else:
                # Vencedor (H2H)
                winner = match['home_team'] if home_score > away_score else match['away_team'] if away_score > home_score else "Empate"
                if aposta.lower() in winner.lower(): ganhou = True
            
            # Atualiza o DF
            if ganhou:
                df.at[idx, 'Resultado'] = '✅ Ganha'
                retorno = row['Stake (R$)'] * row['Odd']
                lucro = retorno - row['Stake (R$)']
            else:
                df.at[idx, 'Resultado'] = '❌ Perdida'
                retorno = 0.0
                lucro = -row['Stake (R$)']
            
            df.at[idx, 'Retorno (R$)'] = retorno
            df.at[idx, 'Lucro (R$)'] = lucro
            total_profit += lucro
            settled_count += 1

    if settled_count > 0:
        df.to_csv(csv_path, index=False)
        msg = (
            f"📊 *RELATÓRIO DE RESULTADOS*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Apostas liquidadas: *{settled_count}*\n"
            f"💰 Lucro/Prejuízo: *R$ {total_profit:.2f}*\n\n"
            f"Use /status no bot para ver sua banca atualizada."
        )
        await send_telegram_message(msg)
        print(f"Sucesso: {settled_count} apostas liquidadas.")
    else:
        print("Nenhum resultado finalizado encontrado para as apostas pendentes.")

if __name__ == "__main__":
    asyncio.run(settle_bets())
