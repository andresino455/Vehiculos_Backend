import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy.orm import Session
from sqlalchemy import text
import os

KEY_PATH = os.getenv("FIREBASE_KEY_PATH", "firebase-key.json")
_firebase_inicializado = False


def inicializar_firebase():
    global _firebase_inicializado
    if _firebase_inicializado:
        return
    print(f"[FCM] Buscando clave en: {KEY_PATH}")
    print(f"[FCM] Archivo existe: {os.path.exists(KEY_PATH)}")
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(KEY_PATH)
            firebase_admin.initialize_app(cred)
        _firebase_inicializado = True
        print("[FCM] Firebase Admin inicializado correctamente")
    except Exception as e:
        print(f"[FCM] Error inicializando Firebase: {e}")


def enviar_notificacion_push(
    db: Session,
    usuario_id: str,
    titulo: str,
    mensaje: str,
    data: dict = {}
):
    inicializar_firebase()
    if not _firebase_inicializado:
        print("[FCM] Firebase no inicializado, no se puede enviar push")
        return

    try:
        tokens = db.execute(
            text("SELECT token FROM tokens_fcm WHERE usuario_id = :uid"),
            {"uid": usuario_id}
        ).fetchall()

        if not tokens:
            print(f"[FCM] No hay tokens para usuario {usuario_id}")
            return

        for row in tokens:
            token = row[0]
            try:
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=titulo,
                        body=mensaje
                    ),
                    data={k: str(v) for k, v in data.items()},
                    android=messaging.AndroidConfig(
                        priority="high",
                        notification=messaging.AndroidNotification(
                            sound="default",
                            priority="high"
                        )
                    ),
                    token=token
                )
                response = messaging.send(message)
                print(f"[FCM] Push enviado: {response}")
            except Exception as e:
                print(f"[FCM] Error enviando a token: {e}")

    except Exception as e:
        print(f"[FCM] Error general: {e}")
