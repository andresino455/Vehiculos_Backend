import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Tecnico(Base):
    __tablename__ = "tecnicos"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    taller_id       = Column(UUID(as_uuid=True), ForeignKey("talleres.id", ondelete="CASCADE"), nullable=False)
    nombre          = Column(String(100), nullable=False)
    apellido        = Column(String(100), nullable=False)
    telefono        = Column(String(20))
    latitud_actual  = Column(Numeric(10, 7))
    longitud_actual = Column(Numeric(10, 7))
    estado          = Column(String(30), default="disponible")
    creado_en       = Column(DateTime, server_default=func.now())

    taller          = relationship("Taller", back_populates="tecnicos")
    incidentes      = relationship("Incidente", back_populates="tecnico")
    asignaciones    = relationship("Asignacion", back_populates="tecnico")