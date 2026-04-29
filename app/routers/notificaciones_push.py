from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, ForeignKey, text
from pydantic import BaseModel
from app.database import get_db, Base
from app.core.dependencies import get_usuario_actual
from app.models.usuario import Usuario
import uuid

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones Push"])

class TokenFCM(BaseModel):
    token: str
    plataforma: str = "android"

@router.post("/registrar-token")
def registrar_token(
    datos: TokenFCM,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual)
):
    db.execute(
        text("""
            INSERT INTO tokens_fcm (id, usuario_id, token, plataforma)
            VALUES (:id, :usuario_id, :token, :plataforma)
            ON CONFLICT (usuario_id, token) DO NOTHING
        """),
        {
            "id": str(uuid.uuid4()),
            "usuario_id": str(usuario.id),
            "token": datos.token,
            "plataforma": datos.plataforma
        }
    )
    db.commit()
    return {"mensaje": "Token registrado"}


@router.post("/test-push/{usuario_id}")
def test_push(usuario_id: str, db: Session = Depends(get_db)):
    from app.services.fcm_service import enviar_notificacion_push

    enviar_notificacion_push(
        db,
        usuario_id,
        "🚗 Prueba de notificación",
        "Si ves esto, las notificaciones push funcionan",
        {"tipo": "test"},
    )
    return {"mensaje": "Push enviado"}
