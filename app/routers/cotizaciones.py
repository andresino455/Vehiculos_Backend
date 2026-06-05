from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.database import get_db
from app.models.incidente import Incidente
from app.models.taller import Taller
from app.models.notificacion import Notificacion
from app.core.dependencies import get_taller_actual, get_usuario_actual
from app.models.usuario import Usuario
import threading
import asyncio
import math

router = APIRouter(prefix="/cotizaciones", tags=["Cotizaciones"])

class CotizacionCrear(BaseModel):
    descripcion: str
    monto_estimado: float
    tiempo_estimado_horas: Optional[float] = None

class CotizacionRespuesta(BaseModel):
    id: UUID
    incidente_id: UUID
    taller_id: UUID
    descripcion: str
    monto_estimado: float
    tiempo_estimado_horas: Optional[float]
    estado: str
    creado_en: datetime

    class Config:
        from_attributes = True

def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(float(lat2) - float(lat1))
    dlon = math.radians(float(lon2) - float(lon1))
    a = math.sin(dlat/2)**2 + math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

@router.post("/{incidente_id}", status_code=201)
def crear_cotizacion(
    incidente_id: str,
    datos: CotizacionCrear,
    db: Session = Depends(get_db),
    taller: Taller = Depends(get_taller_actual)
):
    incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    cotizacion_id = db.execute(text("""
        INSERT INTO cotizaciones (id, incidente_id, taller_id, descripcion, monto_estimado, tiempo_estimado_horas)
        VALUES (uuid_generate_v4(), :inc_id, :tal_id, :desc, :monto, :tiempo)
        RETURNING id, incidente_id, taller_id, descripcion, monto_estimado, tiempo_estimado_horas, estado, creado_en
    """), {
        "inc_id": str(incidente_id),
        "tal_id": str(taller.id),
        "desc": datos.descripcion,
        "monto": datos.monto_estimado,
        "tiempo": datos.tiempo_estimado_horas
    }).fetchone()
    db.commit()

    # Notificar al usuario
    notif = Notificacion(
        destinatario_id=incidente.usuario_id,
        tipo_destinatario="usuario",
        tipo="nueva_cotizacion",
        titulo="💰 Nueva cotización recibida",
        mensaje=f"{taller.nombre} envió una cotización de Bs. {datos.monto_estimado}. Tiempo estimado: {datos.tiempo_estimado_horas} horas."
    )
    db.add(notif)
    db.commit()

    usuario_id_str = str(incidente.usuario_id)
    taller_nombre = taller.nombre
    monto = datos.monto_estimado
    inc_id_str = str(incidente_id)

    def enviar_ws():
        try:
            from app.routers.websocket import manager
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(manager.enviar_a(
                f"usuario_{usuario_id_str}",
                {
                    "tipo": "nueva_cotizacion",
                    "titulo": "💰 Nueva cotización",
                    "mensaje": f"{taller_nombre} cotizó Bs. {monto}",
                    "incidente_id": inc_id_str
                }
            ))
            loop.close()
        except Exception as e:
            print(f"[WS] Error: {e}")

    threading.Thread(target=enviar_ws, daemon=True).start()

    return {"id": str(cotizacion_id.id), "mensaje": "Cotización enviada"}

@router.get("/{incidente_id}")
def get_cotizaciones(
    incidente_id: str,
    db: Session = Depends(get_db)
):
    cotizaciones = db.execute(text("""
        SELECT c.id, c.incidente_id, c.taller_id, t.nombre as taller_nombre,
               c.descripcion, c.monto_estimado, c.tiempo_estimado_horas,
               c.estado, c.creado_en,
               t.latitud, t.longitud, t.tipos_servicio, t.telefono
        FROM cotizaciones c
        JOIN talleres t ON c.taller_id = t.id
        WHERE c.incidente_id = :inc_id
        ORDER BY c.creado_en DESC
    """), {"inc_id": incidente_id}).fetchall()

    return [
        {
            "id": str(c.id),
            "incidente_id": str(c.incidente_id),
            "taller_id": str(c.taller_id),
            "taller_nombre": c.taller_nombre,
            "taller_telefono": c.telefono,
            "descripcion": c.descripcion,
            "monto_estimado": float(c.monto_estimado),
            "tiempo_estimado_horas": float(c.tiempo_estimado_horas) if c.tiempo_estimado_horas else None,
            "estado": c.estado,
            "creado_en": c.creado_en.isoformat()
        }
        for c in cotizaciones
    ]

@router.patch("/{cotizacion_id}/responder")
def responder_cotizacion(
    cotizacion_id: str,
    accion: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual)
):
    if accion not in ["aceptar", "rechazar"]:
        raise HTTPException(status_code=400, detail="Acción inválida")

    cotizacion = db.execute(text("""
        SELECT c.*, i.usuario_id, i.id as inc_id
        FROM cotizaciones c
        JOIN incidentes i ON c.incidente_id = i.id
        WHERE c.id = :cot_id
    """), {"cot_id": cotizacion_id}).fetchone()

    if not cotizacion:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    if str(cotizacion.usuario_id) != str(usuario.id):
        raise HTTPException(status_code=403, detail="No autorizado")

    nuevo_estado = "aceptada" if accion == "aceptar" else "rechazada"

    db.execute(text("""
        UPDATE cotizaciones
        SET estado = :estado, respondida_en = NOW()
        WHERE id = :id
    """), {"estado": nuevo_estado, "id": cotizacion_id})

    if accion == "aceptar":
        # Asignar este taller al incidente
        db.execute(text("""
            UPDATE incidentes
            SET taller_id = :taller_id, estado = 'taller_asignado'
            WHERE id = :inc_id
        """), {"taller_id": str(cotizacion.taller_id), "inc_id": str(cotizacion.inc_id)})

        # Rechazar otras cotizaciones
        db.execute(text("""
            UPDATE cotizaciones
            SET estado = 'rechazada'
            WHERE incidente_id = :inc_id AND id != :cot_id
        """), {"inc_id": str(cotizacion.inc_id), "cot_id": cotizacion_id})

    db.commit()
    return {"mensaje": f"Cotización {nuevo_estado}"}

@router.get("/talleres-candidatos/{incidente_id}")
def get_talleres_candidatos(
    incidente_id: str,
    db: Session = Depends(get_db)
):
    incidente = db.execute(text("""
        SELECT latitud, longitud, tipo_problema, tenant_id
        FROM incidentes WHERE id = :id
    """), {"id": incidente_id}).fetchone()

    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    talleres = db.execute(text("""
        SELECT t.id, t.nombre, t.telefono, t.latitud, t.longitud,
               t.tipos_servicio, t.capacidad_max,
               COALESCE(AVG(c.puntuacion), 0) as calificacion_promedio,
               COUNT(DISTINCT i.id) as servicios_realizados
        FROM talleres t
        LEFT JOIN calificaciones c ON c.taller_id = t.id
        LEFT JOIN incidentes i ON i.taller_id = t.id AND i.estado = 'finalizado'
        WHERE t.activo = TRUE
        AND t.tenant_id = :tenant_id
        GROUP BY t.id
    """), {"tenant_id": str(incidente.tenant_id)}).fetchall()

    candidatos = []
    for t in talleres:
        if not t.latitud or not t.longitud:
            continue
        distancia = calcular_distancia(
            incidente.latitud, incidente.longitud,
            t.latitud, t.longitud
        )
        if distancia > 50:
            continue

        tiene_servicio = True
        if t.tipos_servicio and incidente.tipo_problema not in ['incierto', 'otros', None]:
            tiene_servicio = incidente.tipo_problema in t.tipos_servicio

        if tiene_servicio:
            candidatos.append({
                "id": str(t.id),
                "nombre": t.nombre,
                "telefono": t.telefono,
                "latitud": float(t.latitud),
                "longitud": float(t.longitud),
                "tipos_servicio": t.tipos_servicio,
                "distancia_km": round(distancia, 2),
                "tiempo_estimado_min": int(distancia / 40 * 60),
                "calificacion_promedio": round(float(t.calificacion_promedio), 1),
                "servicios_realizados": t.servicios_realizados
            })

    candidatos.sort(key=lambda x: x["distancia_km"])
    return candidatos[:10]