"""Modelos ORM de SQLAlchemy que mapean las tablas físicas de la base de datos."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.session import Base


class RouteModel(Base):
    """Mapeo a la tabla física 'rutas' con índices compuestos de alto rendimiento."""

    __tablename__ = "rutas"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    asignacion_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    vehiculo_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    conductor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    hora_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hora_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("idx_rutas_estado_hora_inicio", "estado", "hora_inicio"),
        Index("idx_rutas_asignacion_estado", "asignacion_id", "estado"),
        Index("idx_rutas_vehiculo_fecha", "vehiculo_id", "hora_inicio"),
    )


class OutboxModel(Base):
    """Mapeo a la tabla 'outbox_eventos' para el patrón Transactional Outbox."""

    __tablename__ = "outbox_eventos"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evento_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tipo_evento: Mapped[str] = mapped_column(String(64), nullable=False)
    routing_key: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDIENTE")
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("idx_outbox_estado", "estado", "created_at"),)


class ProcessedEventModel(Base):
    """Mapeo a la tabla 'eventos_procesados' para deduplicación idempotente."""

    __tablename__ = "eventos_procesados"

    evento_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tipo_evento: Mapped[str] = mapped_column(String(64), nullable=False)
    procesado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
