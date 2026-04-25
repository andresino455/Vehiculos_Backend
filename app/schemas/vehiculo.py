from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class VehiculoCrear(BaseModel):
    marca: str
    modelo: str
    anio: int
    placa: str
    color: Optional[str] = None
    tipo: Optional[str] = None

class VehiculoRespuesta(BaseModel):
    id: UUID
    usuario_id: UUID
    marca: str
    modelo: str
    anio: int
    placa: str
    color: Optional[str]
    tipo: Optional[str]
    creado_en: datetime

    class Config:
        from_attributes = True