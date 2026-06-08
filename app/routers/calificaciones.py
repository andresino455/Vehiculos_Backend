from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.database import get_db
from app.models.calificacion import Calificacion
from app.models.incidente import Incidente
from app.core.dependencies import get_usuario_actual
from app.models.usuario import Usuario
from app.models.taller import Taller
from app.core.dependencies import get_taller_actual


router = APIRouter(prefix="/calificaciones", tags=["Calificaciones"])

class CalificacionCrear(BaseModel):
    incidente_id: UUID
    puntuacion: int
    comentario: Optional[str] = None

class CalificacionRespuesta(BaseModel):
    id: UUID
    incidente_id: UUID
    usuario_id: UUID
    taller_id: UUID
    puntuacion: int
    comentario: Optional[str]
    creado_en: datetime

    class Config:
        from_attributes = True


@router.post("/", response_model=CalificacionRespuesta, status_code=201)
def crear_calificacion(
    datos: CalificacionCrear,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual)
):
    if datos.puntuacion < 1 or datos.puntuacion > 5:
        raise HTTPException(status_code=400, detail="La puntuación debe ser entre 1 y 5")

    incidente = (
        db.query(Incidente)
        .filter(
            Incidente.id == datos.incidente_id,
            Incidente.usuario_id == usuario.id,
            Incidente.estado == "finalizado",
        )
        .first()
    )
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado o no está atendido")

    if not incidente.taller_id:
        raise HTTPException(status_code=400, detail="El incidente no tiene taller asignado")

    existente = db.query(Calificacion).filter(
        Calificacion.incidente_id == datos.incidente_id,
        Calificacion.usuario_id == usuario.id
    ).first()
    if existente:
        raise HTTPException(status_code=400, detail="Ya calificaste este servicio")

    calificacion = Calificacion(
        incidente_id=datos.incidente_id,
        usuario_id=usuario.id,
        taller_id=incidente.taller_id,
        puntuacion=datos.puntuacion,
        comentario=datos.comentario
    )
    db.add(calificacion)
    db.commit()
    db.refresh(calificacion)
    return calificacion


@router.get("/mis-calificaciones")
def mis_calificaciones(
    db: Session = Depends(get_db),
    taller: Taller = Depends(get_taller_actual)
):
    from app.models.taller import Taller as TallerModel
    calificaciones = db.query(Calificacion).filter(
        Calificacion.taller_id == taller.id
    ).order_by(Calificacion.creado_en.desc()).all()

    total = len(calificaciones)
    promedio = round(sum(c.puntuacion for c in calificaciones) / total, 1) if total > 0 else 0
    distribucion = {i: sum(1 for c in calificaciones if c.puntuacion == i) for i in range(1, 6)}

    return {
        "calificaciones": [
            {
                "id": str(c.id),
                "puntuacion": c.puntuacion,
                "comentario": c.comentario,
                "incidente_id": str(c.incidente_id),
                "creado_en": c.creado_en.isoformat()
            }
            for c in calificaciones
        ],
        "resumen": {
            "total": total,
            "promedio": promedio,
            "distribucion": distribucion
        }
    }
