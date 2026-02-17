# Dockerfile para API/Admin Panel (multi-stage)
FROM python:3.14.3-slim AS builder

LABEL maintainer="Pablo Cubides"
LABEL description="WhatsApp Chatbot Admin Panel & API"

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias Python en wheelhouse
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


FROM python:3.14.3-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -r -s /bin/bash appuser

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copiar código
COPY . .

# Crear directorios necesarios
RUN mkdir -p /app/data /app/logs /app/config && \
    chown -R appuser:appuser /app

# Cambiar a usuario no-root
USER appuser

# Exponer puerto
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8003/healthz || exit 1

# Comando por defecto
CMD ["gunicorn", "admin_panel:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8003", "--workers", "2", "--timeout", "120", "--graceful-timeout", "30"]
