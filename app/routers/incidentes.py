from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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
from app.models.usuario import Usuario
import math
from app.core.security import decode_token

router = APIRouter(prefix="/incidentes", tags=["Incidentes"])


async def notificar_ws(cliente_id: str, mensaje: dict):
    try:
        from app.routers.websocket import manager

        await manager.enviar_a(cliente_id, mensaje)
    except Exception as e:
        print(f"[WS] Error notificando: {e}")


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


def analizar_y_notificar(incidente_id: str):
    from app.database import SessionLocal
    from app.services.ia_service import generar_resumen
    import threading
    import asyncio

    db = SessionLocal()
    try:
        incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
        if not incidente:
            return

        print(f"[IA] Analizando incidente {incidente_id}...")

        resumen = generar_resumen(
            descripcion_texto=incidente.descripcion_texto or "",
            tipo_problema=incidente.tipo_problema or "",
        )

        print(f"[IA] Resultado: {resumen}")

        incidente.resumen_ia = resumen.get("resumen", "")
        incidente.clasificacion_ia = resumen.get("tipo_problema", "incierto")
        incidente.prioridad = resumen.get("prioridad", "media")

        if not incidente.tipo_problema or incidente.tipo_problema == "incierto":
            incidente.tipo_problema = resumen.get("tipo_problema", "incierto")

        db.commit()

        tipo_problema = incidente.tipo_problema or "general"
        talleres = db.query(Taller).filter(Taller.activo == True).all()

        talleres_candidatos = []
        for taller in talleres:
            if not taller.latitud or not taller.longitud:
                continue

            distancia = calcular_distancia(
                incidente.latitud, incidente.longitud, taller.latitud, taller.longitud
            )

            if distancia > 50:
                continue

            tiene_servicio = True
            if taller.tipos_servicio and tipo_problema not in ["incierto", "otros"]:
                tiene_servicio = tipo_problema in taller.tipos_servicio

            if tiene_servicio:
                talleres_candidatos.append({"taller": taller, "distancia": distancia})

        talleres_candidatos.sort(key=lambda x: x["distancia"])

        print(f"[IA] Talleres candidatos encontrados: {len(talleres_candidatos)}")

        for candidato in talleres_candidatos[:5]:
            taller = candidato["taller"]
            notificacion = Notificacion(
                destinatario_id=taller.id,
                tipo_destinatario="taller",
                tipo="nueva_solicitud",
                titulo="Nueva emergencia vehicular",
                mensaje=(
                    f"Tipo: {incidente.tipo_problema} · "
                    f"Prioridad: {incidente.prioridad} · "
                    f"Distancia: {candidato['distancia']:.1f}km · "
                    f"{resumen.get('recomendacion', '')}"
                ),
            )
            db.add(notificacion)

        db.commit()
        print(f"[IA] Análisis completado para incidente {incidente_id}")

        # Notificar a talleres por WebSocket
        incidente_id_str = str(incidente.id)
        tipo_problema_final = incidente.tipo_problema
        prioridad_final = incidente.prioridad

        def broadcast():
            try:
                from app.routers.websocket import manager

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    manager.broadcast_talleres(
                        {
                            "tipo": "nuevo_incidente",
                            "titulo": "Nueva emergencia vehicular",
                            "mensaje": f"Tipo: {tipo_problema_final} · Prioridad: {prioridad_final}",
                            "incidente_id": incidente_id_str,
                        }
                    )
                )
                loop.close()
            except Exception as e:
                print(f"[WS] Error en broadcast: {e}")

        threading.Thread(target=broadcast, daemon=True).start()

    except Exception as e:
        print(f"[IA] Error: {e}")
        db.rollback()
    finally:
        db.close()


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
def crear_incidente(
    datos: IncidenteCrear,
    background_tasks: BackgroundTasks,
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
        estado="pendiente",
        prioridad="media",
    )
    db.add(incidente)
    db.commit()
    db.refresh(incidente)

    historial = HistorialEstado(
        incidente_id=incidente.id,
        estado_anterior=None,
        estado_nuevo="pendiente",
        actor_tipo="sistema",
    )
    db.add(historial)
    db.commit()

    # Analizar con IA y notificar talleres en segundo plano
    background_tasks.add_task(analizar_y_notificar, str(incidente.id))

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
    # Mostrar pendientes y los que este taller tiene en proceso
    incidentes = (
        db.query(Incidente)
        .filter(
            (Incidente.estado == "pendiente")
            | ((Incidente.estado == "en_proceso") & (Incidente.taller_id == taller.id))
        )
        .order_by(Incidente.creado_en.desc())
        .all()
    )
    return incidentes


@router.get("/mis-atenciones", response_model=List[IncidenteRespuesta])
def mis_atenciones(
    db: Session = Depends(get_db), taller: Taller = Depends(get_taller_actual)
):
    return (
        db.query(Incidente)
        .filter(Incidente.taller_id == taller.id)
        .order_by(Incidente.creado_en.desc())
        .all()
    )


@router.get("/{incidente_id}")
def obtener_incidente(
    incidente_id: str, db: Session = Depends(get_db), token: str = Depends(get_token)
):
    from app.core.security import decode_token

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

    if datos.estado in ["atendido", "cancelado"] and incidente.tecnico_id:
        tecnico = db.query(Tecnico).filter(Tecnico.id == incidente.tecnico_id).first()
        if tecnico:
            tecnico.estado = "disponible"

    historial = HistorialEstado(
        incidente_id=incidente.id,
        estado_anterior=estado_anterior,
        estado_nuevo=datos.estado,
        actor_tipo="taller",
        actor_id=taller.id,
        nota=datos.nota,
    )
    db.add(historial)

    mensajes_notif = {
        "atendido": {
            "titulo": "✅ Servicio completado",
            "mensaje": "Tu incidente fue atendido exitosamente. Podés calificar el servicio y realizar el pago.",
        },
        "cancelado": {
            "titulo": "❌ Servicio cancelado",
            "mensaje": f"Tu solicitud fue cancelada por el taller. {datos.nota or ''}",
        },
        "en_proceso": {
            "titulo": "🔧 Taller en camino",
            "mensaje": "El técnico está en camino a tu ubicación.",
        },
    }

    notif_data = mensajes_notif.get(datos.estado)
    if notif_data:
        notificacion = Notificacion(
            destinatario_id=incidente.usuario_id,
            tipo_destinatario="usuario",
            tipo=datos.estado,
            titulo=notif_data["titulo"],
            mensaje=notif_data["mensaje"],
        )
        db.add(notificacion)

    usuario_id_str = str(incidente.usuario_id)
    incidente_id_str = str(incidente.id)

    db.commit()
    db.refresh(incidente)

    if notif_data:
        import threading
        import asyncio

        def enviar_ws():
            try:
                from app.routers.websocket import manager

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    manager.enviar_a(
                        f"usuario_{usuario_id_str}",
                        {
                            "tipo": datos.estado,
                            "titulo": notif_data["titulo"],
                            "mensaje": notif_data["mensaje"],
                            "incidente_id": incidente_id_str,
                        },
                    )
                )
                loop.close()
            except Exception as e:
                print(f"[WS] Error notificando usuario: {e}")

        def enviar_push():
            try:
                from app.services.fcm_service import enviar_notificacion_push
                from app.database import SessionLocal

                db2 = SessionLocal()
                try:
                    enviar_notificacion_push(
                        db2,
                        usuario_id_str,
                        notif_data["titulo"],
                        notif_data["mensaje"],
                        {"incidente_id": incidente_id_str, "tipo": datos.estado},
                    )
                finally:
                    db2.close()
            except Exception as e:
                print(f"[FCM] Error: {e}")

        threading.Thread(target=enviar_ws, daemon=True).start()
        threading.Thread(target=enviar_push, daemon=True).start()

    return incidente


@router.post("/{incidente_id}/asignar", response_model=AsignacionRespuesta)
def asignar_taller(
    incidente_id: str,
    db: Session = Depends(get_db),
    taller: Taller = Depends(get_taller_actual),
):
    incidente = (
        db.query(Incidente)
        .filter(Incidente.id == incidente_id, Incidente.estado == "pendiente")
        .first()
    )
    if not incidente:
        raise HTTPException(
            status_code=404, detail="Incidente no encontrado o no disponible"
        )

    tecnico_disponible = (
        db.query(Tecnico)
        .filter(Tecnico.taller_id == taller.id, Tecnico.estado == "disponible")
        .first()
    )

    if not tecnico_disponible:
        raise HTTPException(
            status_code=400,
            detail="No tenés técnicos disponibles. Liberá un técnico antes de aceptar una solicitud.",
        )

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
    incidente.estado = "en_proceso"
    tecnico_disponible.estado = "ocupado"

    if taller.latitud and taller.longitud:
        tecnico_disponible.latitud_actual = taller.latitud
        tecnico_disponible.longitud_actual = taller.longitud

    notificacion = Notificacion(
        destinatario_id=incidente.usuario_id,
        tipo_destinatario="usuario",
        tipo="taller_asignado",
        titulo="¡Taller en camino!",
        mensaje=f"{taller.nombre} aceptó tu solicitud. Tiempo estimado: {tiempo_estimado} min.",
    )
    db.add(notificacion)

    taller_nombre = taller.nombre
    usuario_id_str = str(incidente.usuario_id)
    incidente_id_str = str(incidente.id)
    tiempo_est = tiempo_estimado

    db.commit()
    db.refresh(asignacion)

    import threading
    import asyncio

    def enviar_ws():
        try:
            from app.routers.websocket import manager

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                manager.enviar_a(
                    f"usuario_{usuario_id_str}",
                    {
                        "tipo": "taller_asignado",
                        "titulo": "¡Taller en camino!",
                        "mensaje": f"{taller_nombre} aceptó tu solicitud. Tiempo estimado: {tiempo_est} min.",
                        "incidente_id": incidente_id_str,
                    },
                )
            )
            loop.close()
        except Exception as e:
            print(f"[WS] Error notificando usuario: {e}")

    def enviar_push():
        try:
            from app.services.fcm_service import enviar_notificacion_push
            from app.database import SessionLocal

            db2 = SessionLocal()
            try:
                enviar_notificacion_push(
                    db2,
                    usuario_id_str,
                    "¡Taller en camino!",
                    f"{taller_nombre} aceptó tu solicitud. Tiempo estimado: {tiempo_est} min.",
                    {"incidente_id": incidente_id_str, "tipo": "taller_asignado"},
                )
            finally:
                db2.close()
        except Exception as e:
            print(f"[FCM] Error: {e}")

    threading.Thread(target=enviar_ws, daemon=True).start()
    threading.Thread(target=enviar_push, daemon=True).start()

    return asignacion


@router.get("/{incidente_id}/historial")
def historial_incidente(
    incidente_id: str, db: Session = Depends(get_db), token: str = Depends(get_token)
):
    from app.core.security import decode_token

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
