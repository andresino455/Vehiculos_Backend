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
from app.models.notificacion import Notificacion
from app.schemas.incidente import IncidenteCrear, IncidenteRespuesta
from app.core.dependencies import get_usuario_actual, get_taller_actual, get_token
from app.core.security import decode_token
from app.models.usuario import Usuario
import math
import threading
import asyncio

router = APIRouter(prefix="/incidentes", tags=["Incidentes"])

ESTADOS_VALIDOS = [
    "pendiente",
    "buscando_taller",
    "taller_asignado",
    "en_camino",
    "en_atencion",
    "finalizado",
    "cancelado",
]


def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(float(lat2) - float(lat1))
    dlon = math.radians(float(lon2) - float(lon1))
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(float(lat1)))
        * math.cos(math.radians(float(lat2)))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def enviar_ws_async(cliente_id: str, mensaje: dict):
    def run():
        try:
            from app.routers.websocket import manager

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(manager.enviar_a(cliente_id, mensaje))
            loop.close()
        except Exception as e:
            print(f"[WS] Error: {e}")

    threading.Thread(target=run, daemon=True).start()


def enviar_push_async(
    db_session, usuario_id: str, titulo: str, mensaje: str, data: dict = {}
):
    def run():
        try:
            from app.services.fcm_service import enviar_notificacion_push
            from app.database import SessionLocal

            db2 = SessionLocal()
            try:
                enviar_notificacion_push(db2, usuario_id, titulo, mensaje, data)
            finally:
                db2.close()
        except Exception as e:
            print(f"[FCM] Error: {e}")

    threading.Thread(target=run, daemon=True).start()


def registrar_historial(
    db,
    incidente_id,
    estado_anterior,
    estado_nuevo,
    actor_tipo,
    actor_id=None,
    nota=None,
):
    historial = HistorialEstado(
        incidente_id=incidente_id,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        actor_tipo=actor_tipo,
        actor_id=actor_id,
        nota=nota,
    )
    db.add(historial)


def notificar_usuario(
    usuario_id: str, incidente_id: str, estado: str, mensaje_extra: str = ""
):
    mensajes = {
        "buscando_taller": (
            "🔍 Buscando taller",
            "Estamos buscando el taller más cercano para atenderte.",
        ),
        "taller_asignado": (
            "✅ Taller asignado",
            f"Un taller aceptó tu solicitud. {mensaje_extra}",
        ),
        "en_camino": (
            "🚗 Técnico en camino",
            f"El técnico está en camino a tu ubicación. {mensaje_extra}",
        ),
        "en_atencion": (
            "🔧 En atención",
            "El técnico llegó y está atendiendo tu vehículo.",
        ),
        "finalizado": (
            "✅ Servicio finalizado",
            "Tu vehículo fue atendido. Podés calificar y pagar.",
        ),
        "cancelado": (
            "❌ Servicio cancelado",
            f"Tu solicitud fue cancelada. {mensaje_extra}",
        ),
    }
    if estado not in mensajes:
        return
    titulo, cuerpo = mensajes[estado]
    ws_msg = {
        "tipo": estado,
        "titulo": titulo,
        "mensaje": cuerpo,
        "incidente_id": incidente_id,
    }
    enviar_ws_async(f"usuario_{usuario_id}", ws_msg)
    enviar_push_async(
        None, usuario_id, titulo, cuerpo, {"incidente_id": incidente_id, "tipo": estado}
    )


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


class RechazoRequest(BaseModel):
    motivo: Optional[str] = None


@router.post("/", response_model=IncidenteRespuesta, status_code=201)
def crear_incidente(
    datos: IncidenteCrear,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    incidente = Incidente(
        usuario_id=usuario.id,
        vehiculo_id=datos.vehiculo_id,
        latitud=datos.latitud,
        longitud=datos.longitud,
        descripcion_texto=datos.descripcion_texto,
        tipo_problema=datos.tipo_problema,
        estado="buscando_taller",
        prioridad="media",
        tenant_id=usuario.tenant_id,
    )
    db.add(incidente)
    db.commit()
    db.refresh(incidente)
    registrar_historial(db, incidente.id, None, "buscando_taller", "sistema")
    db.commit()
    notificar_usuario(str(incidente.usuario_id), str(incidente.id), "buscando_taller")
    return incidente


@router.get("/mis-incidentes", response_model=List[IncidenteRespuesta])
def mis_incidentes(
    db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_actual)
):
    return (
        db.query(Incidente)
        .filter(Incidente.usuario_id == usuario.id)
        .order_by(Incidente.creado_en.desc())
        .all()
    )


@router.get("/disponibles", response_model=List[IncidenteRespuesta])
def incidentes_disponibles(
    db: Session = Depends(get_db), taller: Taller = Depends(get_taller_actual)
):
    return (
        db.query(Incidente)
        .filter(
            Incidente.tenant_id == taller.tenant_id,
            (Incidente.estado == "buscando_taller")
            | (
                (Incidente.estado.in_(["taller_asignado", "en_camino", "en_atencion"]))
                & (Incidente.taller_id == taller.id)
            ),
        )
        .order_by(Incidente.creado_en.desc())
        .all()
    )


@router.get("/mis-atenciones", response_model=List[IncidenteRespuesta])
def mis_atenciones(
    db: Session = Depends(get_db), taller: Taller = Depends(get_taller_actual)
):
    return (
        db.query(Incidente)
        .filter(
            Incidente.taller_id == taller.id, Incidente.tenant_id == taller.tenant_id
        )
        .order_by(Incidente.creado_en.desc())
        .all()
    )


@router.get("/{incidente_id}")
def obtener_incidente(
    incidente_id: str, db: Session = Depends(get_db), token: str = Depends(get_token)
):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido")

    incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    resultado = {
        "id": str(incidente.id),
        "usuario_id": str(incidente.usuario_id),
        "vehiculo_id": str(incidente.vehiculo_id),
        "taller_id": str(incidente.taller_id) if incidente.taller_id else None,
        "tecnico_id": str(incidente.tecnico_id) if incidente.tecnico_id else None,
        "estado": incidente.estado,
        "tipo_problema": incidente.tipo_problema,
        "prioridad": incidente.prioridad,
        "latitud": float(incidente.latitud),
        "longitud": float(incidente.longitud),
        "descripcion_texto": incidente.descripcion_texto,
        "resumen_ia": incidente.resumen_ia,
        "clasificacion_ia": incidente.clasificacion_ia,
        "creado_en": incidente.creado_en.isoformat() if incidente.creado_en else None,
        "completado_en": (
            incidente.completado_en.isoformat() if incidente.completado_en else None
        ),
        "tecnico": None,
    }

    if incidente.tecnico_id:
        tecnico = db.query(Tecnico).filter(Tecnico.id == incidente.tecnico_id).first()
        if tecnico:
            resultado["tecnico"] = {
                "id": str(tecnico.id),
                "nombre": tecnico.nombre,
                "apellido": tecnico.apellido,
                "telefono": tecnico.telefono,
                "estado": tecnico.estado,
                "latitud_actual": (
                    float(tecnico.latitud_actual) if tecnico.latitud_actual else None
                ),
                "longitud_actual": (
                    float(tecnico.longitud_actual) if tecnico.longitud_actual else None
                ),
            }

    return resultado


@router.patch("/{incidente_id}/estado")
def actualizar_estado(
    incidente_id: str,
    datos: EstadoActualizar,
    db: Session = Depends(get_db),
    taller: Taller = Depends(get_taller_actual),
):
    if datos.estado not in ESTADOS_VALIDOS:
        raise HTTPException(
            status_code=400, detail=f"Estado inválido. Válidos: {ESTADOS_VALIDOS}"
        )

    incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    estado_anterior = incidente.estado
    incidente.estado = datos.estado

    if datos.estado == "finalizado":
        incidente.completado_en = datetime.utcnow()

    if datos.estado in ["finalizado", "cancelado"] and incidente.tecnico_id:
        tecnico = db.query(Tecnico).filter(Tecnico.id == incidente.tecnico_id).first()
        if tecnico:
            tecnico.estado = "disponible"

    registrar_historial(
        db, incidente.id, estado_anterior, datos.estado, "taller", taller.id, datos.nota
    )
    db.commit()
    db.refresh(incidente)

    usuario_id_str = str(incidente.usuario_id)
    incidente_id_str = str(incidente.id)
    notificar_usuario(usuario_id_str, incidente_id_str, datos.estado, datos.nota or "")

    return incidente


@router.post("/{incidente_id}/asignar", response_model=AsignacionRespuesta)
def asignar_taller(
    incidente_id: str,
    db: Session = Depends(get_db),
    taller: Taller = Depends(get_taller_actual),
):
    incidente = (
        db.query(Incidente)
        .filter(Incidente.id == incidente_id, Incidente.estado == "buscando_taller")
        .first()
    )
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no disponible")

    tecnico_disponible = (
        db.query(Tecnico)
        .filter(Tecnico.taller_id == taller.id, Tecnico.estado == "disponible")
        .first()
    )

    if not tecnico_disponible:
        raise HTTPException(status_code=400, detail="No tenés técnicos disponibles")

    distancia = None
    tiempo_estimado = None
    if taller.latitud and taller.longitud:
        distancia = calcular_distancia(
            incidente.latitud, incidente.longitud, taller.latitud, taller.longitud
        )
        tiempo_estimado = int(distancia / 40 * 60)

    asignacion = Asignacion(
        incidente_id=incidente.id,
        taller_id=taller.id,
        tecnico_id=tecnico_disponible.id,
        distancia_km=round(distancia, 2) if distancia else None,
        tiempo_estimado_min=tiempo_estimado,
    )
    db.add(asignacion)

    incidente.taller_id = taller.id
    incidente.tecnico_id = tecnico_disponible.id
    incidente.estado = "taller_asignado"
    tecnico_disponible.estado = "ocupado"

    if taller.latitud and taller.longitud:
        tecnico_disponible.latitud_actual = taller.latitud
        tecnico_disponible.longitud_actual = taller.longitud

    notificacion = Notificacion(
        destinatario_id=incidente.usuario_id,
        tipo_destinatario="usuario",
        tipo="taller_asignado",
        titulo="✅ Taller asignado",
        mensaje=f"{taller.nombre} aceptó tu solicitud. Tiempo estimado: {tiempo_estimado} min.",
    )
    db.add(notificacion)

    taller_nombre = taller.nombre
    usuario_id_str = str(incidente.usuario_id)
    incidente_id_str = str(incidente.id)

    registrar_historial(
        db, incidente.id, "buscando_taller", "taller_asignado", "taller", taller.id
    )
    db.commit()
    db.refresh(asignacion)

    notificar_usuario(
        usuario_id_str,
        incidente_id_str,
        "taller_asignado",
        f"{taller_nombre} acepto. Tiempo estimado: {tiempo_estimado} min.",
    )

    return asignacion


@router.post("/{incidente_id}/rechazar")
def rechazar_incidente(
    incidente_id: str,
    datos: RechazoRequest,
    db: Session = Depends(get_db),
    taller: Taller = Depends(get_taller_actual),
):
    incidente = (
        db.query(Incidente)
        .filter(Incidente.id == incidente_id, Incidente.estado == "buscando_taller")
        .first()
    )
    if not incidente:
        raise HTTPException(
            status_code=404, detail="Incidente no disponible para rechazar"
        )

    from sqlalchemy import text

    db.execute(
        text(
            "INSERT INTO rechazos_taller (id, incidente_id, taller_id, motivo) VALUES (uuid_generate_v4(), :inc, :tal, :mot)"
        ),
        {"inc": str(incidente.id), "tal": str(taller.id), "mot": datos.motivo},
    )

    registrar_historial(
        db,
        incidente.id,
        "buscando_taller",
        "buscando_taller",
        "taller",
        taller.id,
        f"Rechazado por {taller.nombre}: {datos.motivo or 'sin motivo'}",
    )
    db.commit()

    return {"mensaje": "Solicitud rechazada"}


@router.get("/{incidente_id}/historial")
def historial_incidente(
    incidente_id: str, db: Session = Depends(get_db), token: str = Depends(get_token)
):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido")

    historial = (
        db.query(HistorialEstado)
        .filter(HistorialEstado.incidente_id == incidente_id)
        .order_by(HistorialEstado.creado_en)
        .all()
    )
    return historial
