from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional, List

class TallerRegistro(BaseModel):
    nombre: str
    razon_social: Optional[str] = None
    email: EmailStr
    telefono: Optional[str] = None
    password: str
    direccion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    tipos_servicio: Optional[List[str]] = None
    capacidad_max: int = 1

class TallerLogin(BaseModel):
    email: EmailStr
    password: str

class TallerRespuesta(BaseModel):
    id: UUID
    nombre: str
    email: str
    telefono: Optional[str]
    direccion: Optional[str]
    latitud: Optional[float]
    longitud: Optional[float]
    tipos_servicio: Optional[List[str]]
    capacidad_max: int
    activo: bool
    creado_en: datetime

    class Config:
        from_attributes = True