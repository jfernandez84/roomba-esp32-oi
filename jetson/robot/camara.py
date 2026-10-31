"""Visión del robot: toma una foto con la cámara USB y le pide a un modelo de Mistral que la describa.

Solo se llama cuando la persona lo pide (herramienta `mirar`). No hay vídeo continuo: se captura UN
fotograma, se envía a Mistral y se borra del Jetson al momento.
La imagen sale a internet (a Mistral) para poder analizarla.
"""
import base64
import os
import subprocess
import tempfile

import requests

from mistral_client import chat_message

CAMERA = "/dev/video0"        # Logitech C170
SIZE = "640x480"              # resolución real de la C170; más es interpolado
FRAMERATE = "15"              # menos ancho de banda USB que a 30 fps
WARMUP_FRAMES = 40            # la exposición tarda ~2,7 s en estabilizarse (medido: de 185 a ~103 de brillo medio)
# En una prueba con la misma foto, mistral-small inventó objetos que no estaban (una gorra, un control
# remoto, un escritorio con cajas), ministral-14b confundió el respaldo de una silla con una capucha y
# mistral-medium fue el más fiel.
VISION_MODEL = "mistral-medium-latest"

VISION_PROMPT = (
    "Eres los ojos de un robot doméstico. Mira la imagen y responde en español latino, en una o dos "
    "frases cortas y concretas, para ser leídas en voz alta. Describe SOLO lo que veas con seguridad: "
    "si no estás seguro de un detalle, no lo menciones y no lo adivines. Si la imagen está oscura, "
    "borrosa o no se distingue bien algo, dilo. No identifiques a nadie por su cara; puedes decir "
    "cuántas personas hay y qué hacen. Si hay texto legible y te lo piden, léelo tal cual."
)


SOURCE_FILE = os.path.expanduser("~/robot/camara.txt")


def source():
    """De dónde salen las fotos: "local" (la cámara USB del Jetson, por defecto) o una dirección http
    de una cámara remota, por ejemplo la del Mac (ver jetson/visor/camara_mac_servidor.py)."""
    try:
        with open(SOURCE_FILE, encoding="utf-8") as f:
            return f.read().strip() or "local"
    except (IOError, OSError):
        return "local"


def capture(path):
    """Guarda una foto JPEG en path, de la cámara remota si hay una configurada y responde, y si no de la
    cámara USB del Jetson."""
    url = source()
    if url.startswith("http"):
        try:
            response = requests.get(url, timeout=25)
            response.raise_for_status()
            with open(path, "wb") as f:
                f.write(response.content)
            return
        except Exception as error:
            print("   [cámara] la cámara remota no respondió (%s); uso la del Jetson" % str(error)[:90],
                  flush=True)
    capture_local(path)


def capture_local(path):
    """Guarda un fotograma JPEG de la cámara USB del Jetson (el último de una ráfaga corta, ya con la
    exposición ajustada)."""
    # YUYV sin comprimir: el modo MJPEG de esta cámara entrega los primeros fotogramas corruptos.
    subprocess.check_call(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "v4l2", "-input_format", "yuyv422",
         "-framerate", FRAMERATE, "-video_size", SIZE, "-i", CAMERA,
         "-frames:v", str(WARMUP_FRAMES), "-update", "1", "-y", path],
        timeout=20)


def describe_image(path, question=None, model=None):
    """Envía una foto ya guardada a un modelo de visión y devuelve su descripción."""
    question = (question or "").strip() or "¿Qué ves frente a ti?"
    with open(path, "rb") as f:
        image = base64.b64encode(f.read()).decode("ascii")
    message = chat_message(
        [{"role": "system", "content": VISION_PROMPT},
         {"role": "user", "content": [
             {"type": "text", "text": question},
             {"type": "image_url", "image_url": "data:image/jpeg;base64," + image}]}],
        model=model or VISION_MODEL, max_tokens=160, temperature=0.2)
    return (message.get("content") or "").strip()


def look(question=None):
    """Toma una foto y devuelve la descripción (o la respuesta a la pregunta). Borra la foto al terminar."""
    fd, path = tempfile.mkstemp(suffix=".jpg", prefix="foto_")
    os.close(fd)
    try:
        capture(path)
        return describe_image(path, question)
    finally:
        if os.path.exists(path):
            os.remove(path)
