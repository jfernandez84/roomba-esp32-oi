#!/usr/bin/env python3
"""Depuración de la visión: toma UNA foto, la GUARDA y se la pasa a varios modelos de visión.

Sirve para separar dos problemas: que la foto no sea buena, o que el modelo se invente lo que ve.
Compara la foto guardada con lo que dice cada modelo.

    venv/bin/python prueba_camara_modelos.py [ruta_de_la_foto]

La foto se envía a Mistral para analizarla. Esta prueba NO la borra: hazlo tú después.
"""
import os
import sys
import time

import camara

PATH = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/robot/foto_prueba.jpg")
MODELS = ("mistral-small-latest", "mistral-medium-latest", "ministral-14b-latest")
QUESTION = "Describe con detalle todo lo que ves en la imagen: qué hay, dónde, colores y si se ve nítida."

print("Capturando en %s ..." % PATH, flush=True)
camara.capture(PATH)
print("Foto guardada (%d bytes).\n" % os.path.getsize(PATH))

for model in MODELS:
    t0 = time.time()
    try:
        answer = camara.describe_image(PATH, QUESTION, model=model)
    except Exception as error:
        answer = "(falló: %s)" % str(error)[:120]
    print("[%s] (%.1f s)\n  %s\n" % (model, time.time() - t0, answer))
