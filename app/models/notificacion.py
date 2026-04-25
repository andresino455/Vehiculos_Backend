import uuid
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base

class Notificacion(Base):
    __tablename__ = "notificaciones"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    destinatario_id   = Column(UUID(as_uuid=True), nullable=False)
    tipo_destinatario = Column(String(10), nullable=False)
    tipo              = Column(String(50), nullable=False)
    titulo            = Column(String(255), nullable=False)
    mensaje           = Column(Text, nullable=False)
    estado            = Column(String(20), default="enviada")
    creado_en         = Column(DateTime, server_default=func.now())
    leido_en          = Column(DateTime, nullable=True)
    