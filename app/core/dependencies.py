from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import decode_token
from app.models.usuario import Usuario
from app.models.taller import Taller

def get_token(request: Request) -> str:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token no proporcionado")
    return auth.split(" ")[1]

def get_usuario_actual(token: str = Depends(get_token), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload or payload.get("tipo") != "usuario":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    usuario = db.query(Usuario).filter(Usuario.id == payload.get("sub")).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    return usuario

def get_taller_actual(token: str = Depends(get_token), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload or payload.get("tipo") != "taller":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    taller = db.query(Taller).filter(Taller.id == payload.get("sub")).first()
    if not taller:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Taller no encontrado")
    return taller