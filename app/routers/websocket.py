from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, cliente_id: str):
        await websocket.accept()
        if cliente_id not in self.connections:
            self.connections[cliente_id] = []
        self.connections[cliente_id].append(websocket)
        print(f"[WS] Conectado: {cliente_id} — Total conexiones: {sum(len(v) for v in self.connections.values())}")

    def disconnect(self, websocket: WebSocket, cliente_id: str):
        if cliente_id in self.connections:
            self.connections[cliente_id].remove(websocket)
            if not self.connections[cliente_id]:
                del self.connections[cliente_id]
        print(f"[WS] Desconectado: {cliente_id}")

    async def enviar_a(self, cliente_id: str, mensaje: dict):
        if cliente_id in self.connections:
            import json
            for ws in self.connections[cliente_id]:
                try:
                    await ws.send_text(json.dumps(mensaje))
                except Exception as e:
                    print(f"[WS] Error enviando a {cliente_id}: {e}")

    async def broadcast_talleres(self, mensaje: dict):
        import json
        for cliente_id, conexiones in self.connections.items():
            if cliente_id.startswith("taller_"):
                for ws in conexiones:
                    try:
                        await ws.send_text(json.dumps(mensaje))
                    except Exception as e:
                        print(f"[WS] Error en broadcast: {e}")

manager = ConnectionManager()

@router.websocket("/ws/{tipo}/{cliente_id}")
async def websocket_endpoint(websocket: WebSocket, tipo: str, cliente_id: str):
    key = f"{tipo}_{cliente_id}"
    await manager.connect(websocket, key)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"[WS] Mensaje de {key}: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket, key)
        
@router.websocket("/ws/tecnico/{tecnico_id}")
async def websocket_tecnico(websocket: WebSocket, tecnico_id: str):
    await websocket.accept()
    print(f"[WS] Técnico conectado: {tecnico_id}")
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("tipo") == "ubicacion":
                # Actualizar ubicación en BD
                from app.database import SessionLocal
                from app.models.tecnico import Tecnico
                from app.models.incidente import Incidente
                db = SessionLocal()
                try:
                    tecnico = db.query(Tecnico).filter(Tecnico.id == tecnico_id).first()
                    if tecnico:
                        tecnico.latitud_actual = data["latitud"]
                        tecnico.longitud_actual = data["longitud"]
                        db.commit()

                        # Notificar al usuario del incidente activo
                        incidente = db.query(Incidente).filter(
                            Incidente.tecnico_id == tecnico_id,
                            Incidente.estado == "en_proceso"
                        ).first()
                        if incidente:
                            await manager.enviar_a(
                                f"usuario_{incidente.usuario_id}",
                                {
                                    "tipo": "ubicacion_tecnico",
                                    "latitud": data["latitud"],
                                    "longitud": data["longitud"],
                                    "tecnico_id": tecnico_id
                                }
                            )
                finally:
                    db.close()
    except WebSocketDisconnect:
        print(f"[WS] Técnico desconectado: {tecnico_id}")