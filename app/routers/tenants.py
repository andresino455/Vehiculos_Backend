from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.database import get_db
from app.models.tenant import Tenant
from app.models.usuario import Usuario
from app.models.taller import Taller
from app.models.incidente import Incidente

router = APIRouter(prefix="/tenants", tags=["Tenants"])

class TenantCrear(BaseModel):
    nombre: str
    descripcion: Optional[str] = None

class TenantRespuesta(BaseModel):
    id: UUID
    nombre: str
    descripcion: Optional[str]
    activo: bool
    creado_en: datetime

    class Config:
        from_attributes = True


@router.get("/publicos")
def tenants_publicos(db: Session = Depends(get_db)):
    tenants = db.query(Tenant).filter(Tenant.activo == True).all()
    return [{"id": str(t.id), "nombre": t.nombre} for t in tenants]


@router.get("/", response_model=List[TenantRespuesta])
def listar_tenants(db: Session = Depends(get_db)):
    return db.query(Tenant).filter(Tenant.activo == True).all()


@router.post("/", response_model=TenantRespuesta, status_code=201)
def crear_tenant(datos: TenantCrear, db: Session = Depends(get_db)):
    tenant = Tenant(nombre=datos.nombre, descripcion=datos.descripcion)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


# DESPUÉS rutas dinámicas
@router.get("/{tenant_id}/estadisticas")
def estadisticas_tenant(tenant_id: str, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    total_talleres = db.query(Taller).filter(Taller.tenant_id == tenant_id).count()
    total_usuarios = db.query(Usuario).filter(Usuario.tenant_id == tenant_id).count()
    total_incidentes = db.query(Incidente).filter(Incidente.tenant_id == tenant_id).count()
    finalizados = db.query(Incidente).filter(
        Incidente.tenant_id == tenant_id,
        Incidente.estado == "finalizado"
    ).count()

    return {
        "tenant": {"id": str(tenant.id), "nombre": tenant.nombre},
        "total_talleres": total_talleres,
        "total_usuarios": total_usuarios,
        "total_incidentes": total_incidentes,
        "total_finalizados": finalizados,
        "tasa_finalizacion": round(finalizados / total_incidentes * 100, 1) if total_incidentes > 0 else 0
    }
