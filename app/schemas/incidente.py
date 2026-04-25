from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class IncidenteCrear(BaseModel):
    vehiculo_id: UUID
    latitud: float
    longitud: float
    descripcion_texto: Optional[str] = None
    tipo_problema: Optional[str] = None

class IncidenteRespuesta(BaseModel):
    id: UUID
    usuario_id: UUID
    vehiculo_id: UUID
    estado: str
    tipo_problema: Optional[str]
    prioridad: str
    latitud: float
    longitud: float
    descripcion_texto: Optional[str]
    resumen_ia: Optional[str]
    clasificacion_ia: Optional[str]
    creado_en: datetime

    class Config:
        from_attributes = True