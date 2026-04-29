"""
fetch_historical.py — Baixa e processa dados históricos de futebol (football-data.co.uk)
Gera arquivos .parquet com odds, resultados e probabilidades implícitas (no-vig) limpas.
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
from pathlib import Path

import httpx
import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Adiciona o diretório raiz ao path para importar config
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import config

console = Console()

# Garante que os diretórios existam
config.HISTORICAL_DIR.mkdir(parents=True, exist_ok=True)

URLS = {
    "premier_league_24_25": "https://www.football-data.co.uk/mmz4281/2425/E0.csv",
    "premier_league_23_24": "https://www.football-data.co.uk/mmz4281/2324/E0.csv",
    "la_liga_24_25": "https://www.football-data.co.uk/mmz4281/2425/SP1.csv",
    "bundesliga_24_25": "https://www.football-data.co.uk/mmz4281/2425/D1.csv",
    "brasileirao_24": "https://www.football-data.co.uk/new/BRA.csv",
}

def remove_vig(odds: list[float]) -> list[float]:
    """Calcula as probabilidades reais sem margem (no-vig) pelo método proporcional."""
    try:
        implied = [1 / o for o in odds if pd.notna(o) and o > 0]
        if len(implied) != len(odds):
            return [0.0] * len(odds)
        total = sum(implied)
        return [p / total for p in implied]
    except Exception:
        return [0.0] * len(odds)

async def download_and_process(name: str, url: str) -> None:
    """Baixa o CSV, limpa colunas e salva como Parquet."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

            df = pd.read_csv(io.StringIO(response.text))

            # Nem todos os arquivos têm as mesmas colunas. O Brasileirão as vezes tem 'Res' em vez de 'FTR'.
            # Mapeamento para garantir as colunas mínimas
            required_cols = ["Date", "HomeTeam", "AwayTeam", "FTR", "B365H", "B365D", "B365A"]
            
            # Brasileirao usa 'Res' em vez de 'FTR' em alguns arquivos da seção "new"
            if "Res" in df.columns and "FTR" not in df.columns:
                df = df.rename(columns={"Res": "FTR"})
            
            # Se faltar MaxH/D/A, preenche com as odds do B365
            if "MaxH" not in df.columns:
                df["MaxH"] = df["B365H"]
                df["MaxD"] = df["B365D"]
                df["MaxA"] = df["B365A"]

            # Filtra apenas os jogos que tem odds da bet365 e resultado final
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                console.print(f"[red]Colunas ausentes em {name}: {missing}[/red]")
                return

            df = df.dropna(subset=["FTR", "B365H", "B365D", "B365A"])

            # Mantém apenas colunas úteis
            keep_cols = [
                "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
                "B365H", "B365D", "B365A", "MaxH", "MaxD", "MaxA"
            ]
            # Algumas planilhas podem não ter gols FTHG/FTAG (ex: brasileirão as vezes usa HG/AG)
            if "HG" in df.columns and "FTHG" not in df.columns:
                df = df.rename(columns={"HG": "FTHG", "AG": "FTAG"})
            
            keep_cols = [c for c in keep_cols if c in df.columns]
            df = df[keep_cols].copy()

            # Adiciona colunas de no-vig
            home_prob, draw_prob, away_prob = [], [], []
            for _, row in df.iterrows():
                # Calcula no-vig usando as maiores odds de mercado se possível (ou B365)
                odds = [row["MaxH"], row["MaxD"], row["MaxA"]]
                probs = remove_vig(odds)
                home_prob.append(probs[0])
                draw_prob.append(probs[1])
                away_prob.append(probs[2])

            df["Prob_H"] = home_prob
            df["Prob_D"] = draw_prob
            df["Prob_A"] = away_prob
            
            # Adiciona nome da liga
            df["League"] = name

            out_path = config.HISTORICAL_DIR / f"{name}.parquet"
            # Formata data para datetime
            try:
                df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
            except Exception:
                pass
                
            df.to_parquet(out_path, index=False)
            return len(df)

    except Exception as e:
        console.print(f"[red]Erro ao processar {name}: {e}[/red]")
        return 0

async def main():
    console.print(f"\n[cyan]Iniciando download de {len(URLS)} bases históricas...[/cyan]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Baixando dados...", total=len(URLS))
        
        tasks = []
        for name, url in URLS.items():
            tasks.append(download_and_process(name, url))
            
        results = await asyncio.gather(*tasks)
        
        for _ in range(len(URLS)):
            progress.advance(task)

    total_games = sum(r for r in results if r)
    console.print(f"[bold green]✓ Download completo! Processados {total_games} jogos no total.[/bold green]")
    console.print(f"Arquivos Parquet salvos em: {config.HISTORICAL_DIR}")

if __name__ == "__main__":
    asyncio.run(main())
