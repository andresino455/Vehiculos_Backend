from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel
import os
import shutil
from app.database import get_db
from app.models.evidencia import Evidencia
from app.models.incidente import Incidente
from app.core.dependencies import get_usuario_actual
from app.models.usuario import Usuario

router = APIRouter(prefix="/evidencias", tags=["Evidencias"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class EvidenciaRespuesta(BaseModel):
    id: UUID
    incidente_id: UUID
    tipo: str
    url: Optional[str]
    transcripcion: Optional[str]
    analisis_ia: Optional[str]
    creado_en: datetime

    class Config:
        from_attributes = True


def disparar_analisis(incidente_id: str):
    import threading
    import time

    def analizar():
        time.sleep(3)
        from app.database import SessionLocal
        from app.services.ia_service import (
            transcribir_audio,
            analizar_imagen,
            generar_resumen,
        )
        from app.models.evidencia import Evidencia
        from app.models.incidente import Incidente
        from app.models.taller import Taller
        from app.models.notificacion import Notificacion
        from app.routers.incidentes import calcular_distancia

        db = SessionLocal()
        try:
            incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
            if not incidente:
                return

            evidencias = (
                db.query(Evidencia).filter(Evidencia.incidente_id == incidente_id).all()
            )

            print(
                f"[IA] Analizando {len(evidencias)} evidencias del incidente {incidente_id}"
            )

            transcripcion_total = ""
            clasificacion_imagen = ""

            for evidencia in evidencias:
                if evidencia.tipo == "audio" and evidencia.url:
                    print(f"[IA] Transcribiendo: {evidencia.url}")
                    transcripcion = transcribir_audio(evidencia.url)
                    evidencia.transcripcion = transcripcion
                    transcripcion_total += f" {transcripcion}"

                elif evidencia.tipo == "imagen" and evidencia.url:
                    print(f"[IA] Analizando imagen: {evidencia.url}")
                    resultado = analizar_imagen(evidencia.url)
                    evidencia.analisis_ia = (
                        f"{resultado.get('categoria')} - "
                        f"{resultado.get('descripcion')} "
                        f"(confianza: {resultado.get('confianza')})"
                    )
                    clasificacion_imagen = evidencia.analisis_ia

            db.commit()

            resumen = generar_resumen(
                descripcion_texto=incidente.descripcion_texto or "",
                transcripcion_audio=transcripcion_total.strip(),
                clasificacion_imagen=clasificacion_imagen,
                tipo_problema=incidente.tipo_problema or "",
            )

            print(f"[IA] Resultado: {resumen}")

            incidente.resumen_ia = resumen.get("resumen", "")
            incidente.clasificacion_ia = resumen.get("tipo_problema", "incierto")
            incidente.prioridad = resumen.get("prioridad", "media")

            if not incidente.tipo_problema or incidente.tipo_problema == "incierto":
                incidente.tipo_problema = resumen.get("tipo_problema", "incierto")

            db.commit()

            # Notificar talleres candidatos
            tipo_problema = incidente.tipo_problema or "general"
            talleres = db.query(Taller).filter(Taller.activo == True).all()
            talleres_candidatos = []

            for taller in talleres:
                if not taller.latitud or not taller.longitud:
                    continue
                distancia = calcular_distancia(
                    incidente.latitud,
                    incidente.longitud,
                    taller.latitud,
                    taller.longitud,
                )
                if distancia > 50:
                    continue
                tiene_servicio = True
                if taller.tipos_servicio and tipo_problema not in ["incierto", "otros"]:
                    tiene_servicio = tipo_problema in taller.tipos_servicio
                if tiene_servicio:
                    talleres_candidatos.append(
                        {"taller": taller, "distancia": distancia}
                    )

            talleres_candidatos.sort(key=lambda x: x["distancia"])

            for candidato in talleres_candidatos[:5]:
                t = candidato["taller"]
                notif = Notificacion(
                    destinatario_id=t.id,
                    tipo_destinatario="taller",
                    tipo="nueva_solicitud",
                    titulo="Nueva emergencia vehicular",
                    mensaje=(
                        f"Tipo: {incidente.tipo_problema} · "
                        f"Prioridad: {incidente.prioridad} · "
                        f"Distancia: {candidato['distancia']:.1f}km"
                    ),
                )
                db.add(notif)

            db.commit()
            print(f"[IA] Análisis completado")

        except Exception as e:
            print(f"[IA] Error: {e}")
            db.rollback()
        finally:
            db.close()

    threading.Thread(target=analizar, daemon=True).start()


@router.post("/imagen/{incidente_id}", response_model=EvidenciaRespuesta)
def subir_imagen(
    incidente_id: str,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual)
):
    incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    extension = archivo.filename.split(".")[-1]
    nombre_archivo = f"{uuid4()}.{extension}"
    ruta = os.path.join(UPLOAD_DIR, nombre_archivo)

    with open(ruta, "wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)

    evidencia = Evidencia(
        incidente_id=incidente_id,
        tipo="imagen",
        url=ruta
    )
    db.add(evidencia)
    db.commit()
    db.refresh(evidencia)

    # Disparar análisis IA después de subir
    disparar_analisis(incidente_id)

    return evidencia

@router.post("/audio/{incidente_id}", response_model=EvidenciaRespuesta)
def subir_audio(
    incidente_id: str,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual)
):
    incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    extension = archivo.filename.split(".")[-1]
    nombre_archivo = f"{uuid4()}.{extension}"
    ruta = os.path.join(UPLOAD_DIR, nombre_archivo)

    with open(ruta, "wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)

    evidencia = Evidencia(
        incidente_id=incidente_id,
        tipo="audio",
        url=ruta
    )
    db.add(evidencia)
    db.commit()
    db.refresh(evidencia)

    # Disparar análisis IA después de subir
    disparar_analisis(incidente_id)

    return evidencia

@router.post("/texto/{incidente_id}", response_model=EvidenciaRespuesta)
def agregar_texto(
    incidente_id: str,
    texto: str = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual)
):
    incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    evidencia = Evidencia(
        incidente_id=incidente_id,
        tipo="texto",
        transcripcion=texto
    )
    db.add(evidencia)
    db.commit()
    db.refresh(evidencia)
    return evidencia

@router.get("/{incidente_id}", response_model=list[EvidenciaRespuesta])
def listar_evidencias(
    incidente_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual)
):
    return db.query(Evidencia).filter(Evidencia.incidente_id == incidente_id).all()
