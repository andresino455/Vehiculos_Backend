from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.tecnico import Tecnico
from app.models.incidente import Incidente
from app.models.historial_estado import HistorialEstado
from app.models.notificacion import Notificacion
from app.core.security import decode_token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime

router = APIRouter(prefix="/tecnico-app", tags=["App Técnico"])
security = HTTPBearer()

def get_tecnico_actual(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("tipo") != "tecnico":
        raise HTTPException(status_code=401, detail="Token inválido")
    tecnico = db.query(Tecnico).filter(Tecnico.id == payload.get("sub")).first()
    if not tecnico:
        raise HTTPException(status_code=401, detail="Técnico no encontrado")
    return tecnico

class UbicacionUpdate(BaseModel):
    latitud: float
    longitud: float

class FinalizarServicio(BaseModel):
    nota: Optional[str] = None

@router.get("/mi-incidente")
def get_mi_incidente(
    tecnico: Tecnico = Depends(get_tecnico_actual),
    db: Session = Depends(get_db)
):
    incidente = db.query(Incidente).filter(
        Incidente.tecnico_id == tecnico.id,
        Incidente.estado == "en_proceso"
    ).first()
    if not incidente:
        return {"incidente": None}
    return {"incidente": incidente}

@router.post("/finalizar/{incidente_id}")
def finalizar_incidente(
    incidente_id: str,
    datos: FinalizarServicio,
    tecnico: Tecnico = Depends(get_tecnico_actual),
    db: Session = Depends(get_db)
):
    incidente = db.query(Incidente).filter(
        Incidente.id == incidente_id,
        Incidente.tecnico_id == tecnico.id,
        Incidente.estado == "en_proceso"
    ).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    estado_anterior = incidente.estado
    incidente.estado = "atendido"
    incidente.completado_en = datetime.utcnow()

    tecnico.estado = "disponible"

    historial = HistorialEstado(
        incidente_id=incidente.id,
        estado_anterior=estado_anterior,
        estado_nuevo="atendido",
        actor_tipo="tecnico",
        actor_id=tecnico.id,
        nota=datos.nota
    )
    db.add(historial)

    notificacion = Notificacion(
        destinatario_id=incidente.usuario_id,
        tipo_destinatario="usuario",
        tipo="servicio_completado",
        titulo="Servicio completado",
        mensaje="El técnico finalizó el servicio. Podés calificar y realizar el pago."
    )
    db.add(notificacion)
    db.commit()

    usuario_id_str = str(incidente.usuario_id)
    incidente_id_str = str(incidente.id)

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
                        "tipo": "servicio_completado",
                        "titulo": "Servicio completado",
                        "mensaje": "El técnico finalizó el servicio. Podés calificar y realizar el pago.",
                        "incidente_id": incidente_id_str
                    }
                )
            )
            loop.close()
        except Exception as e:
            print(f"[WS] Error notificando: {e}")

    threading.Thread(target=enviar_ws, daemon=True).start()

    return {"mensaje": "Servicio finalizado correctamente"}

@router.patch("/ubicacion")
def actualizar_ubicacion(
    datos: UbicacionUpdate,
    tecnico: Tecnico = Depends(get_tecnico_actual),
    db: Session = Depends(get_db)
):
    tecnico.latitud_actual = datos.latitud
    tecnico.longitud_actual = datos.longitud
    db.commit()
    return {"mensaje": "Ubicación actualizada"}