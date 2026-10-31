#!/usr/bin/env python3
"""Prueba la visión: toma UNA foto con la cámara, se la envía a Mistral y muestra lo que ve.

    venv/bin/python prueba_camara.py ["pregunta sobre la imagen"]

La foto se borra al terminar y se envía a Mistral para analizarla.
"""
import sys
import time

import camara

question = sys.argv[1] if len(sys.argv) > 1 else None
t0 = time.time()
print("Mirando...", flush=True)
answer = camara.look(question)
print("Veo: %s" % answer)
print("(tardó %.1f s)" % (time.time() - t0))
