import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Evidencia(Base):
    __tablename__ = "evidencias"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incidente_id  = Column(UUID(as_uuid=True), ForeignKey("incidentes.id", ondelete="CASCADE"), nullable=False)
    tipo          = Column(String(20), nullable=False)
    url           = Column(String)
    transcripcion = Column(Text)
    analisis_ia   = Column(Text)
    creado_en     = Column(DateTime, server_default=func.now())

    incidente     = relationship("Incidente", back_populates="evidencias")