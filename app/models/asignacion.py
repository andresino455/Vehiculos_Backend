import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Asignacion(Base):
    __tablename__ = "asignaciones"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incidente_id        = Column(UUID(as_uuid=True), ForeignKey("incidentes.id", ondelete="CASCADE"), nullable=False)
    taller_id           = Column(UUID(as_uuid=True), ForeignKey("talleres.id"), nullable=False)
    tecnico_id          = Column(UUID(as_uuid=True), ForeignKey("tecnicos.id"), nullable=True)
    estado              = Column(String(20), default="propuesta")
    distancia_km        = Column(Numeric(8, 2))
    tiempo_estimado_min = Column(Integer)
    asignado_en         = Column(DateTime, server_default=func.now())
    aceptado_en         = Column(DateTime, nullable=True)
    rechazado_en        = Column(DateTime, nullable=True)

    incidente           = relationship("Incidente", back_populates="asignaciones")
    taller              = relationship("Taller", back_populates="asignaciones")
    tecnico             = relationship("Tecnico", back_populates="asignaciones")