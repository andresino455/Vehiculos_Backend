import uuid
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    telefono = Column(String(20))
    password_hash = Column(String, nullable=False)
    foto_perfil = Column(String)
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, server_default=func.now())
    actualizado_en = Column(DateTime, server_default=func.now(), onupdate=func.now())
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    vehiculos      = relationship("Vehiculo", back_populates="usuario")
    incidentes     = relationship("Incidente", back_populates="usuario")
    pagos          = relationship("Pago", back_populates="usuario")
    calificaciones = relationship("Calificacion", back_populates="usuario")
