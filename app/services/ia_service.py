from google import genai
from google.genai import types
from app.core.config import settings
import json
import time

client = genai.Client(api_key=settings.GEMINI_API_KEY)

def analizar_imagen(ruta_imagen: str) -> dict:
    try:
        with open(ruta_imagen, "rb") as f:
            datos = f.read()

        extension = ruta_imagen.split(".")[-1].lower()
        mime_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp"
        }
        mime = mime_types.get(extension, "image/jpeg")

        prompt = """Analizá esta imagen de un vehículo con un problema mecánico.
        Respondé SOLO en este formato JSON exacto sin markdown ni backticks:
        {
            "categoria": "bateria|llanta|choque|motor|otros|incierto",
            "descripcion": "descripción breve del problema visible en máximo 2 oraciones",
            "confianza": "alta|media|baja"
        }"""

        for intento in range(3):
            try:
                respuesta = client.models.generate_content(
                    model="gemini-2.0-flash-lite",
                    contents=[
                        types.Part.from_bytes(data=datos, mime_type=mime),
                        prompt
                    ]
                )
                break
            except Exception as e:
                if "429" in str(e) and intento < 2:
                    print(f"[IA] Rate limit en imagen, esperando 35 segundos...")
                    time.sleep(35)
                else:
                    raise e

        texto = respuesta.text.strip()
        texto = texto.replace("```json", "").replace("```", "").strip()
        print(f"[IA] Análisis imagen: {texto}")
        return json.loads(texto)

    except Exception as e:
        print(f"[IA] Error analizando imagen: {e}")
        return {
            "categoria": "incierto",
            "descripcion": "No se pudo analizar la imagen",
            "confianza": "baja"
        }


def transcribir_audio(ruta_audio: str) -> str:
    try:
        with open(ruta_audio, "rb") as f:
            datos = f.read()

        extension = ruta_audio.split(".")[-1].lower()
        mime_types = {
            "mp3": "audio/mp3",
            "wav": "audio/wav",
            "m4a": "audio/m4a",
            "ogg": "audio/ogg",
            "webm": "audio/webm"
        }
        mime = mime_types.get(extension, "audio/mp3")

        for intento in range(3):
            try:
                respuesta = client.models.generate_content(
                    model="gemini-2.0-flash-lite",
                    contents=[
                        types.Part.from_bytes(data=datos, mime_type=mime),
                        "Transcribí este audio en español. Devolvé solo el texto transcripto sin explicaciones adicionales."
                    ]
                )
                break
            except Exception as e:
                if "429" in str(e) and intento < 2:
                    print(f"[IA] Rate limit en audio, esperando 35 segundos...")
                    time.sleep(35)
                else:
                    raise e

        print(f"[IA] Transcripción: {respuesta.text.strip()}")
        return respuesta.text.strip()

    except Exception as e:
        print(f"[IA] Error transcribiendo audio: {e}")
        return "No se pudo transcribir el audio"


def generar_resumen(
    descripcion_texto: str = "",
    transcripcion_audio: str = "",
    clasificacion_imagen: str = "",
    tipo_problema: str = ""
) -> dict:
    try:
        contexto = []
        if descripcion_texto:
            contexto.append(f"Descripción del usuario: {descripcion_texto}")
        if transcripcion_audio:
            contexto.append(f"Audio transcripto: {transcripcion_audio}")
        if clasificacion_imagen:
            contexto.append(f"Análisis de imagen: {clasificacion_imagen}")
        if tipo_problema:
            contexto.append(f"Tipo de problema reportado: {tipo_problema}")

        if not contexto:
            return {
                "resumen": "Sin información suficiente para generar resumen",
                "tipo_problema": "incierto",
                "prioridad": "media",
                "recomendacion": ""
            }

        prompt = f"""Sos un asistente experto en mecánica vehicular.
Analizá esta información de una emergencia vehicular:

{chr(10).join(contexto)}

Respondé SOLO en este formato JSON exacto sin markdown ni backticks:
{{
    "resumen": "resumen claro del problema en 2-3 oraciones",
    "tipo_problema": "bateria|llanta|choque|motor|otros|incierto",
    "prioridad": "alta|media|baja",
    "recomendacion": "recomendación breve para el taller en 1 oración"
}}

Criterios de prioridad:
- alta: accidente, choque, peligro para personas
- media: el vehículo no funciona pero no hay peligro
- baja: problema menor"""

        for intento in range(3):
            try:
                respuesta = client.models.generate_content(
                    model="gemini-2.0-flash-lite",
                    contents=prompt
                )
                break
            except Exception as e:
                if "429" in str(e) and intento < 2:
                    print(f"[IA] Rate limit en resumen, esperando 35 segundos...")
                    time.sleep(35)
                else:
                    raise e

        texto = respuesta.text.strip()
        texto = texto.replace("```json", "").replace("```", "").strip()
        print(f"[IA] Respuesta Gemini: {texto}")
        return json.loads(texto)

    except Exception as e:
        print(f"[IA] Error generando resumen: {e}")
        return {
            "resumen": "No se pudo generar el resumen automático",
            "tipo_problema": tipo_problema or "incierto",
            "prioridad": "media",
            "recomendacion": ""
        }