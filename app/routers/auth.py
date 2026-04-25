from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.usuario import Usuario
from app.models.taller import Taller
from app.schemas.usuario import UsuarioRegistro, UsuarioLogin, UsuarioRespuesta
from app.schemas.taller import TallerRegistro, TallerLogin, TallerRespuesta
from app.schemas.token import Token
from app.core.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Autenticación"])

@router.post("/registro-usuario", response_model=UsuarioRespuesta, status_code=201)
def registro_usuario(datos: UsuarioRegistro, db: Session = Depends(get_db)):
    if db.query(Usuario).filter(Usuario.email == datos.email).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    usuario = Usuario(
        nombre=datos.nombre,
        apellido=datos.apellido,
        email=datos.email,
        telefono=datos.telefono,
        password_hash=hash_password(datos.password)
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario

@router.post("/login-usuario", response_model=Token)
def login_usuario(datos: UsuarioLogin, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == datos.email).first()
    if not usuario or not verify_password(datos.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    token = create_access_token({"sub": str(usuario.id), "tipo": "usuario"})
    return {"access_token": token, "token_type": "bearer", "tipo_usuario": "usuario"}

@router.post("/registro-taller", response_model=TallerRespuesta, status_code=201)
def registro_taller(datos: TallerRegistro, db: Session = Depends(get_db)):
    if db.query(Taller).filter(Taller.email == datos.email).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    taller = Taller(
        nombre=datos.nombre,
        razon_social=datos.razon_social,
        email=datos.email,
        telefono=datos.telefono,
        password_hash=hash_password(datos.password),
        direccion=datos.direccion,
        latitud=datos.latitud,
        longitud=datos.longitud,
        tipos_servicio=datos.tipos_servicio,
        capacidad_max=datos.capacidad_max
    )
    db.add(taller)
    db.commit()
    db.refresh(taller)
    return taller

@router.post("/login-taller", response_model=Token)
def login_taller(datos: TallerLogin, db: Session = Depends(get_db)):
    taller = db.query(Taller).filter(Taller.email == datos.email).first()
    if not taller or not verify_password(datos.password, taller.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    token = create_access_token({"sub": str(taller.id), "tipo": "taller"})
    return {"access_token": token, "token_type": "bearer", "tipo_usuario": "taller"}