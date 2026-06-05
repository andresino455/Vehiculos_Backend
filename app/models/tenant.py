import uuid
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre      = Column(String(200), nullable=False)
    descripcion = Column(String)
    activo      = Column(Boolean, default=True)
    creado_en   = Column(DateTime, server_default=func.now())