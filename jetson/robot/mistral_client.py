"""Cliente mínimo de la API de Mistral (transcripción y conversación) con requests.

Compatible con Python 3.6 (el del Jetson Nano con JetPack 4.6.x), donde el SDK oficial no instala.
La clave se lee de la variable de entorno MISTRAL_API_KEY o del archivo ~/robot/.env
(línea MISTRAL_API_KEY=...). Nunca se imprime ni se guarda en el repositorio.
"""
import base64
import os
import time

import requests

API = "https://api.mistral.ai/v1"
ENV_FILE = os.path.expanduser("~/robot/.env")


def api_key():
    key = os.environ.get("MISTRAL_API_KEY")
    if not key and os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line.startswith("MISTRAL_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise RuntimeError("Falta MISTRAL_API_KEY (variable de entorno o archivo %s)" % ENV_FILE)
    return key


def _headers(extra=None):
    headers = {"Authorization": "Bearer " + api_key()}
    if extra:
        headers.update(extra)
    return headers


def _check(response):
    if not response.ok:
        raise RuntimeError("Mistral respondió %d: %s" % (response.status_code, response.text[:300]))
    return response


def _request(send, retries=4):
    """Ejecuta send() y reintenta con pausa si Mistral responde 429 (límite de peticiones)."""
    for attempt in range(retries):
        response = send()
        if response.status_code != 429 or attempt == retries - 1:
            return response
        time.sleep(2 * (attempt + 1))
    return response


def list_models():
    """Nombres de los modelos que la clave puede usar."""
    r = _check(requests.get(API + "/models", headers=_headers(), timeout=20))
    return sorted(m["id"] for m in r.json().get("data", []))


def transcribe(wav_path, language="es", model="voxtral-mini-latest"):
    """Transcribe un archivo de audio. Devuelve el texto."""
    def send():
        with open(wav_path, "rb") as f:
            return requests.post(
                API + "/audio/transcriptions",
                headers=_headers(),
                data={"model": model, "language": language},
                files={"file": (os.path.basename(wav_path), f, "audio/wav")},
                timeout=60,
            )

    return _check(_request(send)).json().get("text", "").strip()


# mistral-small-latest razona mejor. ministral-8b-latest es más barato y tiene más peticiones por minuto.
# Con una cuenta sin crédito, small y medium daban 429 (límite 0); con crédito de pago por uso funcionan.
CHAT_MODEL = "mistral-small-latest"


def list_voices():
    """Voces disponibles para síntesis de voz (JSON tal como lo devuelve la API)."""
    r = _request(lambda: requests.get(API + "/audio/voices", headers=_headers(), timeout=20))
    return _check(r).json()


TTS_MODEL = "voxtral-mini-tts-3-0"  # "voxtral-mini-tts-latest" apuntaba a la v1 y rechazaba las voces nuevas


def speak(text, voice_id=None, model=TTS_MODEL, fmt="wav"):
    """Sintetiza voz con Voxtral TTS. Devuelve los bytes del audio (la API los manda en base64).

    voice_id acepta el identificador largo o el "slug" de la voz, por ejemplo "voice_483"."""
    body = {"input": text, "model": model, "response_format": fmt}
    if voice_id:
        body["voice_id"] = voice_id
    r = _request(
        lambda: requests.post(
            API + "/audio/speech",
            headers=_headers({"Content-Type": "application/json"}),
            json=body,
            timeout=60,
        )
    )
    return base64.b64decode(_check(r).json()["audio_data"])


def chat_message(messages, model=CHAT_MODEL, max_tokens=200, temperature=0.5, tools=None, tool_choice="auto"):
    """Conversación. Devuelve el mensaje completo del asistente (con tool_calls si pidió herramientas).

    tool_choice: "auto" (el modelo decide), "any" (obliga a llamar a alguna herramienta) o "none"."""
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice

    def send():
        return requests.post(
            API + "/chat/completions",
            headers=_headers({"Content-Type": "application/json"}),
            json=body,
            timeout=60,
        )

    return _check(_request(send)).json()["choices"][0]["message"]


def chat(messages, model=CHAT_MODEL, max_tokens=200, temperature=0.5):
    """Conversación sin herramientas. Devuelve solo el texto de la respuesta."""
    return (chat_message(messages, model, max_tokens, temperature).get("content") or "").strip()
