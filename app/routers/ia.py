from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.incidente import Incidente
from app.models.evidencia import Evidencia
from app.core.dependencies import get_taller_actual
from app.models.taller import Taller
from app.services.ia_service import transcribir_audio, analizar_imagen, generar_resumen

router = APIRouter(prefix="/ia", tags=["Inteligencia Artificial"])

@router.post("/analizar/{incidente_id}")
def analizar_incidente(
    incidente_id: str,
    db: Session = Depends(get_db),
    taller: Taller = Depends(get_taller_actual)
):
    incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    evidencias = db.query(Evidencia).filter(
        Evidencia.incidente_id == incidente_id
    ).all()

    transcripcion_total = ""
    clasificacion_imagen = ""

    for evidencia in evidencias:
        if evidencia.tipo == "audio" and evidencia.url:
            transcripcion = transcribir_audio(evidencia.url)
            evidencia.transcripcion = transcripcion
            transcripcion_total += f" {transcripcion}"
        elif evidencia.tipo == "imagen" and evidencia.url:
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
        tipo_problema=incidente.tipo_problema or ""
    )

    incidente.resumen_ia = resumen.get("resumen", "")
    incidente.clasificacion_ia = resumen.get("tipo_problema", "")
    incidente.prioridad = resumen.get("prioridad", "media")

    if not incidente.tipo_problema or incidente.tipo_problema == "incierto":
        incidente.tipo_problema = resumen.get("tipo_problema", "incierto")

    db.commit()
    db.refresh(incidente)

    return {
        "resumen_ia": incidente.resumen_ia,
        "clasificacion_ia": incidente.clasificacion_ia,
        "prioridad": incidente.prioridad,
        "tipo_problema": incidente.tipo_problema,
        "recomendacion": resumen.get("recomendacion", ""),
        "evidencias_procesadas": len(evidencias)
    }