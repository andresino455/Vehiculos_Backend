import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Calificacion(Base):
    __tablename__ = "calificaciones"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incidente_id = Column(UUID(as_uuid=True), ForeignKey("incidentes.id"), nullable=False)
    usuario_id   = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    taller_id    = Column(UUID(as_uuid=True), ForeignKey("talleres.id"), nullable=False)
    puntuacion   = Column(SmallInteger, nullable=False)
    comentario   = Column(Text)
    creado_en    = Column(DateTime, server_default=func.now())

    incidente    = relationship("Incidente", back_populates="calificacion")
    usuario      = relationship("Usuario", back_populates="calificaciones")
    taller       = relationship("Taller", back_populates="calificaciones")