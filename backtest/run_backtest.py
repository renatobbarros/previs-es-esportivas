"""
run_backtest.py — Motor de backtesting de estratégias de apostas
Avalia estratégias quantitativas em dados históricos com Flat Stake e Kelly Fracionado.
"""
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
from rich.console import Console
from rich.progress import track

# Adiciona o diretório raiz ao path para importar config
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import config

console = Console()

# Garante que os diretórios existam
config.BACKTEST_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────
# Utilitários de Cálculo
# ──────────────────────────────────────────

def calculate_kelly_stake(bankroll: float, prob: float, odd: float, fraction: float = 0.25, max_bet: float = 0.05) -> float:
    """Calcula a stake pelo Kelly Fracionado, com limite de banca."""
    b = odd - 1
    if b <= 0: return 0.0
    kelly_full = (prob * b - (1 - prob)) / b
    if kelly_full <= 0: return 0.0
    
    # Aplica fração e teto
    stake_pct = min(kelly_full * fraction, max_bet)
    return bankroll * stake_pct

def calculate_max_drawdown(bankroll_history: list[float]) -> float:
    """Calcula o maior rebaixamento (drawdown) percentual da banca."""
    if not bankroll_history: return 0.0
    arr = np.array(bankroll_history)
    peaks = np.maximum.accumulate(arr)
    drawdowns = (arr - peaks) / peaks
    return abs(float(drawdowns.min()))

# ──────────────────────────────────────────
# Estratégias
# ──────────────────────────────────────────

def run_strategy_1(df: pd.DataFrame, is_kelly: bool = False) -> dict:
    """
    Estratégia 1 — Valor simples
    Regra: Apostar quando melhor odd > 2.0 E resultado menos provável tem prob implícita > 25%
    Aposta feita no resultado de maior odd (Underdog).
    """
    bankroll = 100.0
    bets, wins = 0, 0
    pnl = 0.0
    history = [bankroll]
    leagues_pnl = {}
    market_pnl = {"H": 0.0, "D": 0.0, "A": 0.0}
    
    for _, row in df.iterrows():
        # Menor probabilidade (resultado menos provável)
        min_prob = min(row["Prob_H"], row["Prob_D"], row["Prob_A"])
        
        # Pega a maior odd do mercado (underdog)
        odds = {"H": row["MaxH"], "D": row["MaxD"], "A": row["MaxA"]}
        probs = {"H": row["Prob_H"], "D": row["Prob_D"], "A": row["Prob_A"]}
        
        best_outcome = max(odds, key=odds.get)
        best_odd = odds[best_outcome]
        best_prob = probs[best_outcome]
        
        if best_odd > 2.0 and min_prob > 0.25:
            stake = calculate_kelly_stake(bankroll, best_prob, best_odd) if is_kelly else 10.0
            if stake <= 0 or bankroll <= 0: continue
            
            won = row["FTR"] == best_outcome
            profit = stake * (best_odd - 1) if won else -stake
            
            bankroll += profit
            bets += 1
            if won: wins += 1
            pnl += profit
            history.append(bankroll)
            
            league = row["League"]
            leagues_pnl[league] = leagues_pnl.get(league, 0) + profit
            market_pnl[best_outcome] += profit
            
    return {"bets": bets, "wins": wins, "pnl": pnl, "history": history, "leagues": leagues_pnl, "markets": market_pnl}

def run_strategy_2(df: pd.DataFrame, is_kelly: bool = False) -> dict:
    """
    Estratégia 2 — Anti-favorito
    Regra: Sistematicamente apostar no empate ou visitante quando favorito tem odd < 1.50.
    Aposta feita no outcome (Draw ou Away) com maior EV.
    """
    bankroll = 100.0
    bets, wins = 0, 0
    pnl = 0.0
    history = [bankroll]
    leagues_pnl = {}
    market_pnl = {"H": 0.0, "D": 0.0, "A": 0.0}
    
    for _, row in df.iterrows():
        if row["MaxH"] < 1.50:
            # Casa é superfavorito. Avalia D e A
            ev_d = (row["Prob_D"] * row["MaxD"]) - 1
            ev_a = (row["Prob_A"] * row["MaxA"]) - 1
            
            bet_on = "D" if ev_d > ev_a else "A"
            odd = row["MaxD"] if bet_on == "D" else row["MaxA"]
            prob = row["Prob_D"] if bet_on == "D" else row["Prob_A"]
            
            stake = calculate_kelly_stake(bankroll, prob, odd) if is_kelly else 10.0
            if stake <= 0 or bankroll <= 0: continue
            
            won = row["FTR"] == bet_on
            profit = stake * (odd - 1) if won else -stake
            
            bankroll += profit
            bets += 1
            if won: wins += 1
            pnl += profit
            history.append(bankroll)
            
            league = row["League"]
            leagues_pnl[league] = leagues_pnl.get(league, 0) + profit
            market_pnl[bet_on] += profit
            
    return {"bets": bets, "wins": wins, "pnl": pnl, "history": history, "leagues": leagues_pnl, "markets": market_pnl}

def run_strategy_3(df: pd.DataFrame, is_kelly: bool = False) -> dict:
    """
    Estratégia 3 — Edge de mercado
    Regra: Apostar quando há discrepância > 8% entre Max e B365.
    """
    bankroll = 100.0
    bets, wins = 0, 0
    pnl = 0.0
    history = [bankroll]
    leagues_pnl = {}
    market_pnl = {"H": 0.0, "D": 0.0, "A": 0.0}
    
    for _, row in df.iterrows():
        for outcome in ["H", "D", "A"]:
            max_odd = row[f"Max{outcome}"]
            b365_odd = row[f"B365{outcome}"]
            prob = row[f"Prob_{outcome}"]
            
            if pd.notna(max_odd) and pd.notna(b365_odd) and b365_odd > 0:
                diff = (max_odd - b365_odd) / b365_odd
                if diff > 0.08:
                    stake = calculate_kelly_stake(bankroll, prob, max_odd) if is_kelly else 10.0
                    if stake <= 0 or bankroll <= 0: continue
                    
                    won = row["FTR"] == outcome
                    profit = stake * (max_odd - 1) if won else -stake
                    
                    bankroll += profit
                    bets += 1
                    if won: wins += 1
                    pnl += profit
                    history.append(bankroll)
                    
                    league = row["League"]
                    leagues_pnl[league] = leagues_pnl.get(league, 0) + profit
                    market_pnl[outcome] += profit
                    break # Faz apenas 1 aposta por jogo nesta estratégia
            
    return {"bets": bets, "wins": wins, "pnl": pnl, "history": history, "leagues": leagues_pnl, "markets": market_pnl}

# ──────────────────────────────────────────
# Geração de Relatório
# ──────────────────────────────────────────

def generate_ascii_chart(history: list[float], width: int = 40) -> str:
    """Gera um mini-gráfico ASCII da evolução da banca (amostragem semanal/chunks)."""
    if not history: return ""
    chunks = np.array_split(history, min(len(history), width))
    points = [chunk.mean() for chunk in chunks]
    
    min_val = min(points)
    max_val = max(points)
    range_val = max_val - min_val if max_val > min_val else 1
    
    # Níveis de caracteres (fino ao mais alto)
    chars = " ▂▃▄▅▆▇█"
    
    chart = ""
    for p in points:
        idx = int(((p - min_val) / range_val) * (len(chars) - 1))
        chart += chars[idx]
        
    return chart

def get_best_from_dict(d: dict) -> str:
    if not d: return "N/A"
    best_key = max(d, key=d.get)
    return f"{best_key} (R$ {d[best_key]:.2f})"

def run_all():
    console.print("[cyan]Carregando base de dados histórica...[/cyan]")
    files = list(config.HISTORICAL_DIR.glob("*.parquet"))
    
    if not files:
        console.print("[red]Arquivos .parquet não encontrados. Rode fetch_historical.py primeiro.[/red]")
        return
        
    df_list = [pd.read_parquet(f) for f in files]
    df_full = pd.concat(df_list, ignore_index=True)
    df_full = df_full.sort_values("Date").reset_index(drop=True)
    
    console.print(f"[green]Base carregada: {len(df_full)} jogos.[/green]")
    
    strategies = [
        ("Estratégia 1: Valor simples", run_strategy_1),
        ("Estratégia 2: Anti-favorito", run_strategy_2),
        ("Estratégia 3: Edge de mercado", run_strategy_3),
    ]
    
    results_flat = []
    results_kelly = []
    
    for name, func in track(strategies, description="Rodando backtests..."):
        r_flat = func(df_full, is_kelly=False)
        r_kelly = func(df_full, is_kelly=True)
        
        r_flat["name"] = name
        r_kelly["name"] = name
        
        results_flat.append(r_flat)
        results_kelly.append(r_kelly)
        
    # --- Formatação do Relatório ---
    md = [
        f"# 📊 Relatório de Backtest — Sports Edge AI",
        f"**Gerado em:** {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        f"**Total de jogos analisados:** {len(df_full)}",
        f"**Banca Inicial simulada:** R$ 100.00\n",
        "## Comparativo de Estratégias (Flat Stake R$ 10)\n",
        "| Estratégia | Apostas | Win Rate | ROI % | PnL Total | Max Drawdown |",
        "|---|---|---|---|---|---|"
    ]
    
    best_strat = None
    max_pnl = -999999
    
    for r in results_flat:
        roi = (r['pnl'] / (r['bets'] * 10)) * 100 if r['bets'] > 0 else 0
        wr = (r['wins'] / r['bets']) * 100 if r['bets'] > 0 else 0
        dd = calculate_max_drawdown(r['history']) * 100
        
        md.append(f"| {r['name']} | {r['bets']} | {wr:.1f}% | {roi:.1f}% | R$ {r['pnl']:.2f} | {dd:.1f}% |")
        
        if r['pnl'] > max_pnl and r['bets'] > 0:
            max_pnl = r['pnl']
            best_strat = r
            
    md.append("\n## Comparativo de Estratégias (Kelly Fracionado 25%)\n")
    md.append("| Estratégia | Apostas | PnL Total | Max Drawdown |")
    md.append("|---|---|---|---|")
    
    for r in results_kelly:
        dd = calculate_max_drawdown(r['history']) * 100
        md.append(f"| {r['name']} | {r['bets']} | R$ {r['pnl']:.2f} | {dd:.1f}% |")
        
    md.append("\n## Análise da Melhor Estratégia (Flat Stake)\n")
    if best_strat:
        roi = (best_strat['pnl'] / (best_strat['bets'] * 10)) * 100
        md.extend([
            f"**A Estratégia Vencedora foi:** {best_strat['name']} (ROI: {roi:.1f}%)",
            f"**Liga Mais Lucrativa:** {get_best_from_dict(best_strat['leagues'])}",
            f"**Melhor Tipo de Aposta (H/D/A):** {get_best_from_dict(best_strat['markets'])}\n",
            f"### Evolução da Banca",
            f"```text\nR$ 100 ├" + generate_ascii_chart(best_strat['history']) + "┤ R$ " + f"{100 + best_strat['pnl']:.2f}\n```\n",
            f"### 💡 Conclusão e Recomendação",
            f"> Com R$ 100 de banca, a estratégia **{best_strat['name']}** teria gerado **R$ {best_strat['pnl']:.2f}** "
            f"em {len(df_full)//50} meses simulados de jogos — use esta estratégia como referência principal para calibrar suas apostas."
        ])
    else:
        md.append("Nenhuma estratégia foi testada com sucesso.")
        
    md.append("\n> ⚠️ **Aviso:** Resultado histórico não garante resultado futuro. As linhas do mercado mudam de comportamento ao longo dos anos.")
    
    report_path = config.BACKTEST_DIR / "report.md"
    report_path.write_text("\n".join(md))
    console.print(f"[bold green]Relatório salvo com sucesso em:[/bold green] {report_path}")

if __name__ == "__main__":
    run_all()
