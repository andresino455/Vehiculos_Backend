import uuid
from sqlalchemy import Column, String, Boolean, SmallInteger, Numeric, DateTime
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Taller(Base):
    __tablename__ = "talleres"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre           = Column(String(200), nullable=False)
    razon_social     = Column(String(200))
    email            = Column(String(255), nullable=False, unique=True)
    telefono         = Column(String(20))
    password_hash    = Column(String, nullable=False)
    direccion        = Column(String)
    latitud          = Column(Numeric(10, 7))
    longitud         = Column(Numeric(10, 7))
    tipos_servicio   = Column(ARRAY(String))
    capacidad_max    = Column(SmallInteger, default=1)
    comision_pct     = Column(Numeric(5, 2), default=10.00)
    activo           = Column(Boolean, default=True)
    creado_en        = Column(DateTime, server_default=func.now())
    actualizado_en   = Column(DateTime, server_default=func.now(), onupdate=func.now())

    tecnicos         = relationship("Tecnico", back_populates="taller")
    incidentes       = relationship("Incidente", back_populates="taller")
    asignaciones     = relationship("Asignacion", back_populates="taller")
    calificaciones   = relationship("Calificacion", back_populates="taller")
    metricas         = relationship("MetricaTaller", back_populates="taller")