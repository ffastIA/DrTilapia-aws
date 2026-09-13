FROM python:3.11-slim

WORKDIR /app

# Instala dependências de sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 1. Copia o arquivo de requisitos
COPY backend/requirements.txt .

# 2. Instala as versões "bloqueadas" primeiro
RUN pip install --no-cache-dir \
    sqlalchemy==2.0.29 \
    sqlmodel==0.0.16

# 3. Aguarda para garantir consistência
RUN sleep 1

# 4. Instala o resto
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia o código
COPY backend/ .

EXPOSE 8000

# Comando de execução do motor de IA
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]