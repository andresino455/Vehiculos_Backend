from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.database import get_db
from app.models.pago import Pago
from app.models.incidente import Incidente
from app.models.taller import Taller
from app.core.dependencies import get_usuario_actual
from app.models.usuario import Usuario

router = APIRouter(prefix="/pagos", tags=["Pagos"])

class PagoCrear(BaseModel):
    incidente_id: UUID
    monto_total: float
    metodo_pago: str

class PagoRespuesta(BaseModel):
    id: UUID
    incidente_id: UUID
    usuario_id: UUID
    monto_total: float
    comision_plataforma: float
    monto_taller: float
    estado: str
    metodo_pago: Optional[str]
    creado_en: datetime

    class Config:
        from_attributes = True

@router.post("/", response_model=PagoRespuesta, status_code=201)
def crear_pago(datos: PagoCrear, db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_actual)):
    incidente = db.query(Incidente).filter(
        Incidente.id == datos.incidente_id,
        Incidente.usuario_id == usuario.id
    ).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    if db.query(Pago).filter(Pago.incidente_id == datos.incidente_id).first():
        raise HTTPException(status_code=400, detail="Este incidente ya tiene un pago registrado")

    comision = round(datos.monto_total * 0.10, 2)
    monto_taller = round(datos.monto_total - comision, 2)

    pago = Pago(
        incidente_id=datos.incidente_id,
        usuario_id=usuario.id,
        monto_total=datos.monto_total,
        comision_plataforma=comision,
        monto_taller=monto_taller,
        estado="completado",
        metodo_pago=datos.metodo_pago,
        pagado_en=datetime.utcnow()
    )
    db.add(pago)
    db.commit()
    db.refresh(pago)
    return pago

@router.get("/mis-pagos", response_model=list[PagoRespuesta])
def mis_pagos(db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_actual)):
    return db.query(Pago).filter(Pago.usuario_id == usuario.id).all()