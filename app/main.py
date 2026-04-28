from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from app.routers import (
    auth,
    vehiculos,
    tecnicos,
    incidentes,
    talleres,
    evidencias,
    pagos,
    ia,
    calificaciones,
    tecnicos_app,
)
from app.routers import websocket as ws_router
from app.routers import notificaciones_push

import os

app = FastAPI(
    title="Plataforma Emergencias Vehiculares",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://localhost:8000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth.router)
app.include_router(vehiculos.router)
app.include_router(tecnicos.router)
app.include_router(incidentes.router)
app.include_router(talleres.router)
app.include_router(evidencias.router)
app.include_router(pagos.router)
app.include_router(ia.router)
app.include_router(ws_router.router)
app.include_router(calificaciones.router)
app.include_router(tecnicos_app.router)
app.include_router(notificaciones_push.router)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title="Plataforma Emergencias Vehiculares",
        version="1.0.0",
        routes=app.routes,
    )
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    for path in schema["paths"].values():
        for method in path.values():
            method["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi

@app.get("/")
def root():
    return {"mensaje": "API de Emergencias Vehiculares activa"}
