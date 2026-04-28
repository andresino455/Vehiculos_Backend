from groq import Groq
from app.core.config import settings
import json
import base64

client = Groq(api_key=settings.GROQ_API_KEY)

def analizar_imagen(ruta_imagen: str) -> dict:
    try:
        with open(ruta_imagen, "rb") as f:
            datos = f.read()

        imagen_base64 = base64.b64encode(datos).decode("utf-8")
        extension = ruta_imagen.split(".")[-1].lower()
        mime_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp"
        }
        mime = mime_types.get(extension, "image/jpeg")

        respuesta = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{imagen_base64}"},
                        },
                        {
                            "type": "text",
                            "text": """Analizá esta imagen de un vehículo con un problema mecánico.
Respondé SOLO en este formato JSON exacto sin markdown ni backticks:
{
    "categoria": "bateria|llanta|choque|motor|otros|incierto",
    "descripcion": "descripción breve del problema visible en máximo 2 oraciones",
    "confianza": "alta|media|baja"
}""",
                        },
                    ],
                }
            ],
            max_tokens=200,
        )

        texto = respuesta.choices[0].message.content.strip()
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
            transcripcion = client.audio.transcriptions.create(
                file=(ruta_audio.split("\\")[-1], f.read()),
                model="whisper-large-v3",
                language="es",
                response_format="text",
            )
        print(f"[IA] Transcripción: {transcripcion}")
        return transcripcion

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

        respuesta = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "Sos un experto en mecánica vehicular. Respondés siempre en JSON válido sin markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
            temperature=0.3,
        )

        texto = respuesta.choices[0].message.content.strip()
        texto = texto.replace("```json", "").replace("```", "").strip()
        print(f"[IA] Respuesta Groq: {texto}")
        return json.loads(texto)

    except Exception as e:
        print(f"[IA] Error generando resumen: {e}")
        return {
            "resumen": "No se pudo generar el resumen automático",
            "tipo_problema": tipo_problema or "incierto",
            "prioridad": "media",
            "recomendacion": ""
        }
