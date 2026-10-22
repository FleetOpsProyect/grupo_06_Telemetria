"""Configuración global externalizada del microservicio."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Parámetros de configuración leídos desde variables de entorno o archivo .env."""

    # Configuración de la aplicación FastAPI
    app_name: str = Field(default="fleetops-telemetria", description="Nombre del servicio")
    environment: str = Field(default="development", description="Entorno de despliegue")
    debug: bool = Field(default=False, description="Modo debug")
    port: int = Field(default=8000, description="Puerto HTTP de escucha")
    api_v1_prefix: str = Field(default="/api/v1", description="Prefijo global para endpoints v1")

    # Base de Datos Relacional (PostgreSQL / SQLite en pruebas)
    database_url: str = Field(
        default="postgresql://telemetria_user:telemetria_password@localhost:5432/telemetria_db",
        description="URL de conexión SQLAlchemy",
    )
    db_pool_size: int = Field(default=10, description="Tamaño del pool de conexiones")
    db_max_overflow: int = Field(default=20, description="Sobrecarga máxima del pool")

    # Broker de Mensajería (RabbitMQ)
    rabbitmq_url: str = Field(
        default="amqp://guest:guest@localhost:5672/", description="URL AMQP del broker"
    )
    rabbitmq_exchange: str = Field(
        default="fleetops.events", description="Exchange topic de eventos de flota"
    )
    rabbitmq_queue: str = Field(default="q.telemetria", description="Cola principal para eventos")
    rabbitmq_dlq: str = Field(
        default="q.telemetria.dlq", description="Cola de mensajes muertos (DLQ)"
    )
    rabbitmq_prefetch_count: int = Field(
        default=10, description="Mensajes máximos no confirmados por consumidor"
    )

    # Parámetros del Circuit Breaker (Patrón de resiliencia)
    circuit_breaker_failure_threshold: int = Field(
        default=5, description="Fallos consecutivos para abrir circuito"
    )
    circuit_breaker_recovery_timeout_seconds: float = Field(
        default=30.0, description="Tiempo de espera en estado ABIERTO antes de reintentar"
    )

    # Seguridad JWT
    jwt_secret_key: str = Field(
        default="dev-secret-key-change-in-production-at-all-costs-32chars",
        description="Clave para verificar tokens JWT",
    )
    jwt_algorithm: str = Field(default="HS256", description="Algoritmo de firma JWT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Instancia singleton accesible globalmente
settings = Settings()
