#!/usr/bin/env python3
"""Graba unos segundos con el micrófono de la cámara USB y los transcribe con Voxtral (Mistral).

Uso:
    python stt_cloud_test.py [segundos]

El dispositivo usa el nombre de la tarjeta (C170) en lugar de su número, porque el número
cambia al enchufar otros dispositivos de audio.
"""
import os
import subprocess
import sys
import tempfile

from mistral_client import transcribe

DEVICE = "plughw:CARD=C170,DEV=0"
SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
WAV = os.path.join(tempfile.gettempdir(), "stt_cloud_test.wav")

print("Habla ahora (%d s)..." % SECONDS, flush=True)
subprocess.check_call(
    ["arecord", "-D", DEVICE, "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", str(SECONDS), "-q", WAV]
)
print("Transcribiendo...", flush=True)
print("> " + transcribe(WAV, language="es"))
