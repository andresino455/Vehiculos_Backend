from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.vehiculo import Vehiculo
from app.schemas.vehiculo import VehiculoCrear, VehiculoRespuesta
from app.core.dependencies import get_usuario_actual
from app.models.usuario import Usuario
from typing import List

router = APIRouter(prefix="/vehiculos", tags=["Vehículos"])

@router.post("/", response_model=VehiculoRespuesta, status_code=201)
def crear_vehiculo(datos: VehiculoCrear, db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_actual)):
    if db.query(Vehiculo).filter(Vehiculo.placa == datos.placa).first():
        raise HTTPException(status_code=400, detail="Ya existe un vehículo con esa placa")
    vehiculo = Vehiculo(
        usuario_id=usuario.id,
        marca=datos.marca,
        modelo=datos.modelo,
        anio=datos.anio,
        placa=datos.placa,
        color=datos.color,
        tipo=datos.tipo
    )
    db.add(vehiculo)
    db.commit()
    db.refresh(vehiculo)
    return vehiculo

@router.get("/", response_model=List[VehiculoRespuesta])
def listar_vehiculos(db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_actual)):
    return db.query(Vehiculo).filter(Vehiculo.usuario_id == usuario.id).all()

@router.get("/{vehiculo_id}", response_model=VehiculoRespuesta)
def obtener_vehiculo(vehiculo_id: str, db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_actual)):
    vehiculo = db.query(Vehiculo).filter(Vehiculo.id == vehiculo_id, Vehiculo.usuario_id == usuario.id).first()
    if not vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return vehiculo

@router.delete("/{vehiculo_id}", status_code=204)
def eliminar_vehiculo(vehiculo_id: str, db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_actual)):
    vehiculo = db.query(Vehiculo).filter(Vehiculo.id == vehiculo_id, Vehiculo.usuario_id == usuario.id).first()
    if not vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    db.delete(vehiculo)
    db.commit()