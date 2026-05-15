# Use a imagem base oficial do Python slim
FROM python:3.11-slim

# Evita que o Python gere arquivos .pyc e permite que os logs apareçam imediatamente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Define o diretório de trabalho
WORKDIR /app

# Instala dependências do sistema necessárias para algumas bibliotecas Python e PostgreSQL
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instala o gerenciador de pacotes UV para instalações ultrarrápidas
RUN pip install uv

# Copia os arquivos de dependências
COPY pyproject.toml .
# Se houver um lockfile, descomente a linha abaixo
# COPY uv.lock . 

# Instala as dependências do projeto
RUN uv pip install --system .

# Copia o restante do código do projeto
COPY . .

# Expõe a porta do Streamlit
EXPOSE 8501

# O comando padrão é definido no docker-compose.yml para cada serviço
CMD ["python", "core/scheduler.py"]
