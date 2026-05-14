# Use a imagem base estável
FROM python:3.12-slim

# Define o diretório de trabalho
WORKDIR /app

# Instala dependências de sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala requisitos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código do projeto
COPY . .

# Garante permissões de execução
RUN chmod -R 755 /app

# Porta da API
EXPOSE 8000

# O comando padrão (será sobrescrito pelo docker-compose para o migrate)
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]