import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class HistorialEstado(Base):
    __tablename__ = "historial_estados"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incidente_id    = Column(UUID(as_uuid=True), ForeignKey("incidentes.id", ondelete="CASCADE"), nullable=False)
    estado_anterior = Column(String(30))
    estado_nuevo    = Column(String(30), nullable=False)
    actor_tipo      = Column(String(10))
    actor_id        = Column(UUID(as_uuid=True), nullable=True)
    nota            = Column(Text)
    creado_en       = Column(DateTime, server_default=func.now())

    incidente       = relationship("Incidente", back_populates="historial")