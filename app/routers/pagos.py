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
from app.models.taller import Taller
from app.core.dependencies import get_taller_actual

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


@router.get("/mis-cobros")
def mis_cobros(
    db: Session = Depends(get_db), taller: Taller = Depends(get_taller_actual)
):
    from app.models.incidente import Incidente

    pagos = (
        db.query(Pago)
        .join(Incidente, Pago.incidente_id == Incidente.id)
        .filter(Incidente.taller_id == taller.id)
        .order_by(Pago.creado_en.desc())
        .all()
    )

    total_bruto = sum(float(p.monto_total) for p in pagos)
    total_comision = sum(float(p.comision_plataforma) for p in pagos)
    total_neto = sum(float(p.monto_taller) for p in pagos)

    return {
        "pagos": [
            {
                "id": str(p.id),
                "incidente_id": str(p.incidente_id),
                "monto_total": float(p.monto_total),
                "comision_plataforma": float(p.comision_plataforma),
                "monto_taller": float(p.monto_taller),
                "estado": p.estado,
                "metodo_pago": p.metodo_pago,
                "creado_en": p.creado_en.isoformat(),
            }
            for p in pagos
        ],
        "resumen": {
            "total_servicios": len(pagos),
            "total_bruto": round(total_bruto, 2),
            "total_comision": round(total_comision, 2),
            "total_neto": round(total_neto, 2),
        },
    }


import stripe
from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentIntentRequest(BaseModel):
    incidente_id: UUID
    monto_total: float
    metodo_pago: str


class ConfirmarPagoRequest(BaseModel):
    incidente_id: UUID
    monto_total: float
    metodo_pago: str
    payment_intent_id: str


@router.post("/crear-intent")
def crear_payment_intent(
    datos: PaymentIntentRequest,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    incidente = (
        db.query(Incidente)
        .filter(Incidente.id == datos.incidente_id, Incidente.usuario_id == usuario.id)
        .first()
    )
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    if db.query(Pago).filter(Pago.incidente_id == datos.incidente_id).first():
        raise HTTPException(
            status_code=400, detail="Este incidente ya tiene un pago registrado"
        )

    # Convertir Bs a centavos USD (Stripe no acepta BOB, usamos USD en test)
    # 1 USD ≈ 6.96 BOB
    monto_usd = datos.monto_total / 6.96
    monto_centavos = int(monto_usd * 100)

    intent = stripe.PaymentIntent.create(
        amount=monto_centavos,
        currency="usd",
        metadata={
            "incidente_id": str(datos.incidente_id),
            "usuario_id": str(usuario.id),
            "monto_bs": str(datos.monto_total),
        },
    )
    return {"client_secret": intent.client_secret, "payment_intent_id": intent.id}


@router.post("/confirmar", response_model=PagoRespuesta, status_code=201)
def confirmar_pago(
    datos: ConfirmarPagoRequest,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    # Verificar con Stripe que el pago fue exitoso
    try:
        intent = stripe.PaymentIntent.retrieve(datos.payment_intent_id)
        if intent.status != "succeeded":
            raise HTTPException(
                status_code=400, detail="El pago no fue completado en Stripe"
            )
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    incidente = (
        db.query(Incidente)
        .filter(Incidente.id == datos.incidente_id, Incidente.usuario_id == usuario.id)
        .first()
    )
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    if db.query(Pago).filter(Pago.incidente_id == datos.incidente_id).first():
        raise HTTPException(
            status_code=400, detail="Este incidente ya tiene un pago registrado"
        )

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
        pagado_en=datetime.utcnow(),
    )
    db.add(pago)
    db.commit()
    db.refresh(pago)
    return pago
