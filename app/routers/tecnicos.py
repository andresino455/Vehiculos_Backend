from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.database import get_db
from app.models.tecnico import Tecnico
from app.core.dependencies import get_taller_actual
from app.models.taller import Taller

router = APIRouter(prefix="/tecnicos", tags=["Técnicos"])

class TecnicoCrear(BaseModel):
    nombre: str
    apellido: str
    telefono: Optional[str] = None

class TecnicoRespuesta(BaseModel):
    id: UUID
    taller_id: UUID
    nombre: str
    apellido: str
    telefono: Optional[str]
    latitud_actual: Optional[float]
    longitud_actual: Optional[float]
    estado: str
    creado_en: datetime

    class Config:
        from_attributes = True

class UbicacionActualizar(BaseModel):
    latitud: float
    longitud: float

@router.post("/", response_model=TecnicoRespuesta, status_code=201)
def crear_tecnico(datos: TecnicoCrear, db: Session = Depends(get_db), taller: Taller = Depends(get_taller_actual)):
    tecnico = Tecnico(
        taller_id=taller.id,
        nombre=datos.nombre,
        apellido=datos.apellido,
        telefono=datos.telefono
    )
    db.add(tecnico)
    db.commit()
    db.refresh(tecnico)
    return tecnico

@router.get("/", response_model=List[TecnicoRespuesta])
def listar_tecnicos(db: Session = Depends(get_db), taller: Taller = Depends(get_taller_actual)):
    return db.query(Tecnico).filter(Tecnico.taller_id == taller.id).all()

@router.patch("/{tecnico_id}/ubicacion", response_model=TecnicoRespuesta)
def actualizar_ubicacion(tecnico_id: str, datos: UbicacionActualizar, db: Session = Depends(get_db), taller: Taller = Depends(get_taller_actual)):
    tecnico = db.query(Tecnico).filter(Tecnico.id == tecnico_id, Tecnico.taller_id == taller.id).first()
    if not tecnico:
        raise HTTPException(status_code=404, detail="Técnico no encontrado")
    tecnico.latitud_actual = datos.latitud
    tecnico.longitud_actual = datos.longitud
    db.commit()
    db.refresh(tecnico)
    return tecnico

@router.patch("/{tecnico_id}/estado", response_model=TecnicoRespuesta)
def actualizar_estado(tecnico_id: str, estado: str, db: Session = Depends(get_db), taller: Taller = Depends(get_taller_actual)):
    if estado not in ["disponible", "ocupado", "inactivo"]:
        raise HTTPException(status_code=400, detail="Estado inválido")
    tecnico = db.query(Tecnico).filter(Tecnico.id == tecnico_id, Tecnico.taller_id == taller.id).first()
    if not tecnico:
        raise HTTPException(status_code=404, detail="Técnico no encontrado")
    tecnico.estado = estado
    db.commit()
    db.refresh(tecnico)
    return tecnico