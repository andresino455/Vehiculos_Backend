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