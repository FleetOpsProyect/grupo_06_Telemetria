# ── Etapa 1: Construcción (Builder) ──────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Instalar dependencias del sistema requeridas para compilar paquetes C
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./

# Actualizar pip e instalar dependencias de producción
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ── Etapa 2: Imagen Final de Producción ───────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Instalar libpq para psycopg2 en tiempo de ejecución
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario y grupo sin privilegios para no correr como root
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -d /app appuser

# Copiar paquetes instalados desde la etapa builder
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin

# Copiar código fuente
COPY app/ ./app/
COPY alembic/ ./alembic/

# Configurar permisos
RUN chown -R appuser:appgroup /app

# Variables de entorno de ejecución de Python
ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Cambiar al usuario no-root
USER appuser

EXPOSE 8000

# Healthcheck interno del contenedor
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Comando de inicio del servidor ASGI Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
