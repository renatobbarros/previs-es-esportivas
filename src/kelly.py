"""
src/kelly.py — Cálculo do Critério de Kelly para gestão de banca.
Fórmula: f* = (bp - q) / b
Onde:
- f*: Fração da banca a apostar
- b: Odds decimais - 1 (lucro líquido por real apostado)
- p: Probabilidade de vitória estimada (0.0 a 1.0)
- q: Probabilidade de derrota (1 - p)
"""

def calculate_kelly(odds: float, estimated_prob: float, fractional_kelly: float = 0.25) -> float:
    """
    Calcula a porcentagem da banca para apostar.
    
    Args:
        odds: Odd decimal (ex: 2.10)
        estimated_prob: Probabilidade estimada pela IA (0.0 a 1.0)
        fractional_kelly: Multiplicador para reduzir a volatilidade (default 0.25)
        
    Returns:
        Porcentagem decimal da banca (ex: 0.05 para 5%)
    """
    if odds <= 1.0 or estimated_prob <= 0:
        return 0.0
    
    # b = Odds - 1
    b = odds - 1
    p = estimated_prob
    q = 1.0 - p
    
    # Kelly puro: (bp - q) / b
    kelly_pure = (b * p - q) / b
    
    # Se o valor esperado é negativo, não apostamos
    if kelly_pure <= 0:
        return 0.0
    
    # Aplica o Kelly fracionado
    recommended_stake = kelly_pure * fractional_kelly
    
    return round(recommended_stake, 4)

if __name__ == "__main__":
    # Exemplo: Odd 2.0 (50% mercado), IA diz 60% prob.
    # b = 1.0, p = 0.6, q = 0.4
    # Kelly = (1.0*0.6 - 0.4) / 1.0 = 0.2 (20% da banca)
    # 1/4 Kelly = 5%
    res = calculate_kelly(2.0, 0.60)
    print(f"Recomendação 1/4 Kelly: {res*100}%")
