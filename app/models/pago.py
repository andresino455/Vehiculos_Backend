import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Pago(Base):
    __tablename__ = "pagos"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incidente_id        = Column(UUID(as_uuid=True), ForeignKey("incidentes.id"), nullable=False)
    usuario_id          = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    monto_total         = Column(Numeric(12, 2), nullable=False)
    comision_plataforma = Column(Numeric(12, 2), nullable=False)
    monto_taller        = Column(Numeric(12, 2), nullable=False)
    estado              = Column(String(20), default="pendiente")
    metodo_pago         = Column(String(50))
    referencia_externa  = Column(String(255))
    creado_en           = Column(DateTime, server_default=func.now())
    pagado_en           = Column(DateTime, nullable=True)

    incidente           = relationship("Incidente", back_populates="pago")
    usuario             = relationship("Usuario", back_populates="pagos")