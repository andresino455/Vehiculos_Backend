from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional

class UsuarioRegistro(BaseModel):
    nombre: str
    apellido: str
    email: EmailStr
    telefono: Optional[str] = None
    password: str
    codigo_tenant: Optional[str] = None

class UsuarioLogin(BaseModel):
    email: EmailStr
    password: str

class UsuarioRespuesta(BaseModel):
    id: UUID
    nombre: str
    apellido: str
    email: str
    telefono: Optional[str]
    activo: bool
    creado_en: datetime

    class Config:
        from_attributes = True
