import uuid
from sqlalchemy import Column, SmallInteger, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class MetricaTaller(Base):
    __tablename__ = "metricas_talleres"

    id                       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    taller_id                = Column(UUID(as_uuid=True), ForeignKey("talleres.id", ondelete="CASCADE"), nullable=False)
    mes                      = Column(SmallInteger, nullable=False)
    anio                     = Column(SmallInteger, nullable=False)
    total_servicios          = Column(Integer, default=0)
    ingresos_brutos          = Column(Numeric(14, 2), default=0)
    comisiones_pagadas       = Column(Numeric(14, 2), default=0)
    tiempo_promedio_atencion = Column(Numeric(8, 2))
    calificacion_promedio    = Column(Numeric(3, 2))

    taller                   = relationship("Taller", back_populates="metricas")