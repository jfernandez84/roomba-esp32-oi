#!/usr/bin/env python3
"""Graba unos segundos con el micrófono de la cámara USB y los transcribe EN LOCAL con Vosk.

Se ejecuta con run_isolated.sh (ver ese script):
    sh ~/robot/run_isolated.sh ~/robot/stt_local_test.py [segundos]
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import wave

from vosk import KaldiRecognizer, Model, SetLogLevel

MODEL_DIR = os.path.expanduser("~/robot/models/vosk-model-small-es-0.42")
DEVICE = "plughw:CARD=C170,DEV=0"
SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 6
WAV = os.path.join(tempfile.gettempdir(), "stt_local_test.wav")

SetLogLevel(-1)
t0 = time.time()
model = Model(MODEL_DIR)
print("Modelo cargado en %.1f s" % (time.time() - t0), flush=True)

print("Habla ahora (%d s)..." % SECONDS, flush=True)
subprocess.check_call(
    ["arecord", "-D", DEVICE, "-f", "S16_LE", "-r", "16000", "-c", "1", "-d", str(SECONDS), "-q", WAV]
)

t1 = time.time()
recognizer = KaldiRecognizer(model, 16000)
with wave.open(WAV, "rb") as wav:
    while True:
        data = wav.readframes(4000)
        if not data:
            break
        recognizer.AcceptWaveform(data)
text = json.loads(recognizer.FinalResult()).get("text", "")
print("> " + text)
print("Reconocido en %.1f s" % (time.time() - t1))
