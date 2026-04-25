from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from app.database import get_db
from app.models.incidente import Incidente
from app.models.taller import Taller
from app.models.tecnico import Tecnico
from app.models.asignacion import Asignacion
from app.models.historial_estado import HistorialEstado
from app.schemas.incidente import IncidenteCrear, IncidenteRespuesta
from app.core.dependencies import get_usuario_actual, get_taller_actual
from app.models.usuario import Usuario
import math

router = APIRouter(prefix="/incidentes", tags=["Incidentes"])

def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(float(lat2) - float(lat1))
    dlon = math.radians(float(lon2) - float(lon1))
    a = math.sin(dlat/2)**2 + math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

class AsignacionRespuesta(BaseModel):
    id: UUID
    incidente_id: UUID
    taller_id: UUID
    tecnico_id: Optional[UUID]
    estado: str
    distancia_km: Optional[float]
    tiempo_estimado_min: Optional[int]
    asignado_en: datetime

    class Config:
        from_attributes = True

class EstadoActualizar(BaseModel):
    estado: str
    nota: Optional[str] = None

@router.post("/", response_model=IncidenteRespuesta, status_code=201)
def crear_incidente(datos: IncidenteCrear, db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_actual)):
    incidente = Incidente(
        usuario_id=usuario.id,
        vehiculo_id=datos.vehiculo_id,
        latitud=datos.latitud,
        longitud=datos.longitud,
        descripcion_texto=datos.descripcion_texto,
        tipo_problema=datos.tipo_problema,
        estado="pendiente",
        prioridad="media"
    )
    db.add(incidente)
    db.commit()
    db.refresh(incidente)

    historial = HistorialEstado(
        incidente_id=incidente.id,
        estado_anterior=None,
        estado_nuevo="pendiente",
        actor_tipo="sistema"
    )
    db.add(historial)
    db.commit()

    return incidente

@router.get("/mis-incidentes", response_model=List[IncidenteRespuesta])
def mis_incidentes(db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_actual)):
    return db.query(Incidente).filter(Incidente.usuario_id == usuario.id).order_by(Incidente.creado_en.desc()).all()

@router.get("/disponibles", response_model=List[IncidenteRespuesta])
def incidentes_disponibles(db: Session = Depends(get_db), taller: Taller = Depends(get_taller_actual)):
    return db.query(Incidente).filter(Incidente.estado == "pendiente").order_by(Incidente.creado_en.desc()).all()

@router.get("/{incidente_id}", response_model=IncidenteRespuesta)
def obtener_incidente(incidente_id: str, db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_actual)):
    incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    return incidente

@router.patch("/{incidente_id}/estado")
def actualizar_estado(incidente_id: str, datos: EstadoActualizar, db: Session = Depends(get_db), taller: Taller = Depends(get_taller_actual)):
    estados_validos = ["pendiente", "en_proceso", "atendido", "cancelado"]
    if datos.estado not in estados_validos:
        raise HTTPException(status_code=400, detail="Estado inválido")
    incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    estado_anterior = incidente.estado
    incidente.estado = datos.estado
    if datos.estado == "atendido":
        incidente.completado_en = datetime.utcnow()
    db.commit()

    historial = HistorialEstado(
        incidente_id=incidente.id,
        estado_anterior=estado_anterior,
        estado_nuevo=datos.estado,
        actor_tipo="taller",
        actor_id=taller.id,
        nota=datos.nota
    )
    db.add(historial)
    db.commit()
    db.refresh(incidente)
    return incidente

@router.post("/{incidente_id}/asignar", response_model=AsignacionRespuesta)
def asignar_taller(incidente_id: str, db: Session = Depends(get_db), taller: Taller = Depends(get_taller_actual)):
    incidente = db.query(Incidente).filter(Incidente.id == incidente_id, Incidente.estado == "pendiente").first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado o no disponible")

    distancia = None
    tiempo_estimado = None
    if taller.latitud and taller.longitud:
        distancia = calcular_distancia(incidente.latitud, incidente.longitud, taller.latitud, taller.longitud)
        tiempo_estimado = int(distancia / 40 * 60)

    tecnico_disponible = db.query(Tecnico).filter(
        Tecnico.taller_id == taller.id,
        Tecnico.estado == "disponible"
    ).first()

    asignacion = Asignacion(
        incidente_id=incidente.id,
        taller_id=taller.id,
        tecnico_id=tecnico_disponible.id if tecnico_disponible else None,
        distancia_km=round(distancia, 2) if distancia else None,
        tiempo_estimado_min=tiempo_estimado
    )
    db.add(asignacion)

    incidente.taller_id = taller.id
    incidente.tecnico_id = tecnico_disponible.id if tecnico_disponible else None
    incidente.estado = "en_proceso"

    if tecnico_disponible:
        tecnico_disponible.estado = "ocupado"

    db.commit()
    db.refresh(asignacion)
    return asignacion

@router.get("/{incidente_id}/historial")
def historial_incidente(incidente_id: str, db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_actual)):
    historial = db.query(HistorialEstado).filter(HistorialEstado.incidente_id == incidente_id).order_by(HistorialEstado.creado_en).all()
    return historial