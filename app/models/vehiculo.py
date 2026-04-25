import uuid
from sqlalchemy import Column, String, SmallInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Vehiculo(Base):
    __tablename__ = "vehiculos"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    marca      = Column(String(100), nullable=False)
    modelo     = Column(String(100), nullable=False)
    anio       = Column(SmallInteger, nullable=False)
    placa      = Column(String(20), nullable=False, unique=True)
    color      = Column(String(50))
    tipo       = Column(String(50))
    creado_en  = Column(DateTime, server_default=func.now())

    usuario    = relationship("Usuario", back_populates="vehiculos")
    incidentes = relationship("Incidente", back_populates="vehiculo")