#!/usr/bin/env python3
"""Prueba la síntesis de voz de Mistral (Voxtral TTS) y la reproduce por HDMI.

Uso:
    python tts_cloud_test.py voice_483 [otra_voz ...]

Cada argumento es el identificador de una voz (por ejemplo "voice_483"), o su nombre. Dice la misma
frase con cada una.
"""
import os
import subprocess
import sys
import tempfile
import time

from mistral_client import speak

OUTPUT_DEVICE = "plughw:0,3"  # HDMI
TEXT = "Hola, soy tu robot. Hoy me siento con mucha energía. ¿Qué quieres que hagamos?"

voices = sys.argv[1:] or ["voice_483"]
for voice in voices:
    print("Voz: %s ..." % voice, flush=True)
    wav = os.path.join(tempfile.gettempdir(), "tts_cloud_test.wav")
    padded = wav + ".pad.wav"
    with open(wav, "wb") as f:
        f.write(speak(TEXT, voice_id=voice, fmt="wav"))
    subprocess.call(["sox", wav, padded, "pad", "0.6", "0"])  # el HDMI se come el inicio
    subprocess.call(["aplay", "-D", OUTPUT_DEVICE, "-q", padded])
    time.sleep(1)
print("Fin")
