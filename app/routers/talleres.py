from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.database import get_db
from app.models.taller import Taller
from app.schemas.taller import TallerRespuesta
from app.core.dependencies import get_taller_actual

router = APIRouter(prefix="/talleres", tags=["Talleres"])

class TallerActualizar(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    tipos_servicio: Optional[List[str]] = None
    capacidad_max: Optional[int] = None

@router.get("/perfil", response_model=TallerRespuesta)
def obtener_perfil(taller: Taller = Depends(get_taller_actual)):
    return taller

@router.patch("/perfil", response_model=TallerRespuesta)
def actualizar_perfil(datos: TallerActualizar, db: Session = Depends(get_db), taller: Taller = Depends(get_taller_actual)):
    for campo, valor in datos.model_dump(exclude_none=True).items():
        setattr(taller, campo, valor)
    db.commit()
    db.refresh(taller)
    return taller

@router.get("/cercanos")
def talleres_cercanos(latitud: float, longitud: float, db: Session = Depends(get_db)):
    import math
    talleres = db.query(Taller).filter(Taller.activo == True, Taller.latitud != None).all()
    resultado = []
    for t in talleres:
        dlat = math.radians(float(t.latitud) - latitud)
        dlon = math.radians(float(t.longitud) - longitud)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(latitud)) * math.cos(math.radians(float(t.latitud))) * math.sin(dlon/2)**2
        distancia = 6371 * 2 * math.asin(math.sqrt(a))
        resultado.append({
            "id": str(t.id),
            "nombre": t.nombre,
            "telefono": t.telefono,
            "direccion": t.direccion,
            "latitud": float(t.latitud),
            "longitud": float(t.longitud),
            "tipos_servicio": t.tipos_servicio,
            "distancia_km": round(distancia, 2)
        })
    resultado.sort(key=lambda x: x["distancia_km"])
    return resultado[:10]