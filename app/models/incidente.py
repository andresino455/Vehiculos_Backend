import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Incidente(Base):
    __tablename__ = "incidentes"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id        = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    vehiculo_id       = Column(UUID(as_uuid=True), ForeignKey("vehiculos.id"), nullable=False)
    taller_id         = Column(UUID(as_uuid=True), ForeignKey("talleres.id"), nullable=True)
    tecnico_id        = Column(UUID(as_uuid=True), ForeignKey("tecnicos.id"), nullable=True)
    estado            = Column(String(30), default="pendiente")
    tipo_problema     = Column(String(50), nullable=True)
    prioridad         = Column(String(20), default="media")
    latitud           = Column(Numeric(10, 7), nullable=False)
    longitud          = Column(Numeric(10, 7), nullable=False)
    descripcion_texto = Column(Text)
    resumen_ia        = Column(Text)
    clasificacion_ia  = Column(Text)
    creado_en         = Column(DateTime, server_default=func.now())
    actualizado_en    = Column(DateTime, server_default=func.now(), onupdate=func.now())
    completado_en     = Column(DateTime, nullable=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    usuario           = relationship("Usuario", back_populates="incidentes")
    vehiculo          = relationship("Vehiculo", back_populates="incidentes")
    taller            = relationship("Taller", back_populates="incidentes")
    tecnico           = relationship("Tecnico", back_populates="incidentes")
    evidencias        = relationship("Evidencia", back_populates="incidente")
    asignaciones      = relationship("Asignacion", back_populates="incidente")
    historial         = relationship("HistorialEstado", back_populates="incidente")
    pago              = relationship("Pago", back_populates="incidente", uselist=False)
    calificacion      = relationship("Calificacion", back_populates="incidente", uselist=False)
