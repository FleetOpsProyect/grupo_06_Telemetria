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

    # Mensajería en AWS (SNS para publicar, SQS para consumir)
    aws_region: str = Field(default="us-east-2", description="Región AWS de SNS y SQS")
    aws_endpoint_url: str | None = Field(
        default=None, description="Endpoint alterno (LocalStack o pruebas); vacío en AWS real"
    )
    sns_topic_arn: str = Field(
        default="", description="ARN del tópico SNS donde Telemetría publica sus eventos"
    )
    sqs_queue_url: str = Field(
        default="", description="URL de la cola SQS de la que Telemetría consume eventos"
    )
    sqs_wait_time_seconds: int = Field(
        default=20, description="Espera de long polling por cada lectura de SQS (0-20 s)"
    )
    sqs_max_messages: int = Field(
        default=10, description="Mensajes máximos por lectura de SQS (1-10)"
    )
    outbox_dispatch_interval_seconds: float = Field(
        default=5.0, description="Cada cuántos segundos se publican los eventos del outbox"
    )
    messaging_workers_enabled: bool = Field(
        default=True,
        description="Arranca el publicador del outbox y el consumidor SQS junto con la app",
    )

    # Integracion sincrona con el MS de Asignaciones (HU-01)
    assignments_base_url: str = Field(
        default="http://localhost:8001/api/v1",
        description="URL base del microservicio de Asignaciones",
    )
    assignments_get_path: str = Field(
        default="/asignaciones/{asignacion_id}", description="Ruta para obtener asignación por ID"
    )
    assignments_timeout_seconds: float = Field(
        default=2.0,
        description="Tiempo de espera para llamadas HTTP al microservicio de Asignaciones",
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

    @property
    def messaging_configured(self) -> bool:
        """Indica si hay tópico SNS y cola SQS configurados."""
        return bool(self.sns_topic_arn and self.sqs_queue_url)


# Instancia singleton accesible globalmente
settings = Settings()
