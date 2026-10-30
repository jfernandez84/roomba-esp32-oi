#!/usr/bin/env python3
"""Prueba la memoria SIN audio: manda frases escritas a conversar.respond() y muestra qué se guarda.

Usa un archivo de memoria temporal, así que no toca los recuerdos reales del robot.
    venv/bin/python prueba_memoria_texto.py
"""
import os
import tempfile

import conversar
import herramientas

herramientas.memory.path = os.path.join(tempfile.mkdtemp(), "memoria_prueba.json")

# (frase, ¿debería guardarse algo?)
CASES = [
    ("Me gusta la música clásica.", True),
    ("Mi cumpleaños es el 3 de marzo.", True),
    ("Tengo una hermana que se llama Dana.", True),
    ("Hoy hace calor.", False),
    ("Recuerda que el wifi de la casa se llama Casa5G.", True),
    ("Recuerda que la contraseña del wifi es abc12345.", False),   # no debe guardarla
    ("Mi perro se llama Rocky y tiene tres años.", True),
]

system_text = conversar.SYSTEM_PROMPT.format(nombre="Robi", ciudad=herramientas.DEFAULT_CITY)
history = []
ok = 0
for phrase, should_save in CASES:
    before = len(herramientas.memory.items())
    history.append({"role": "user", "content": phrase})
    system = {"role": "system", "content": system_text + "\n\n" + herramientas.memory.as_prompt()}
    reply = conversar.respond(system, history)
    history.append({"role": "assistant", "content": reply})
    saved = len(herramientas.memory.items()) > before
    good = saved == should_save
    ok += good
    print("%s Tú: %s\n    Robi: %s\n    guardó: %s (esperado: %s)\n" % (
        "OK " if good else "MAL", phrase, reply, saved, should_save))

print("Recuerdos al final:")
for item in herramientas.memory.items():
    print("  - " + item["texto"])
print("\n%d de %d casos bien" % (ok, len(CASES)))
