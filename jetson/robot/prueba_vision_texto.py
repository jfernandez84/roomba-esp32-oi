#!/usr/bin/env python3
"""Prueba la decisión de usar la cámara, SIN audio.

Parte A (siempre): comprueba con frases reales de una sesión qué decide el programa, sin cámara y sin
red: ¿se OBLIGA a mirar? ¿se PERMITE que el modelo mire? Es lo que protege la privacidad.

Parte B (solo con --real): manda las frases a conversar.respond() y toma fotos REALES con la cámara
cuando el programa decide mirar. Cada foto se envía a Mistral y se borra.

    venv/bin/python prueba_vision_texto.py [--real]
"""
import sys

import conversar

# (frase, ¿se obliga a mirar?, ¿se permite que el modelo mire?)
CASES = [
    ("Hola, Roby, dime si puedes ver.", False, True),
    ("Dime que te estoy sosteniendo con mi mano.", True, True),
    ("Lo estoy mostrando a la cámara en este momento.", True, True),
    ("Perfecto.", False, False),                    # el caso que falló: foto sin que nadie la pidiera
    ("Dime qué estoy sosteniendo con mi mano.", True, True),
    ("Necesito que me digas que estoy sosteniendo con mi mano.", True, True),
    ("¿Qué ves?", True, True),
    ("Mira esto y dime qué es.", True, True),
    ("¿Qué hay frente a ti?", True, True),
    ("¿Y ahora?", False, True),
    ("Está bien, pero lo que ves como cabello largo es el respaldo de mi silla.", False, False),   # corrección
    ("Una tela oscura sobre la cabeza.", False, False),                 # repetía lo que dijo el robot
    ("Sí, mira de nuevo, por favor.", False, True),                     # la decide el modelo, y está permitida
    ("Dime lo que ves.", True, True),                                   # "lo que ves" como petición sí se obliga
    ("¡Vamos a ver!", False, False),                # muletilla: una vez abrió la cámara sin que nadie la pidiera
    ("¿Puedes ver esto?", False, True),
    ("¿Qué hora es?", False, False),
    ("Cuéntame un chiste corto.", False, False),
    ("Gracias, muy bien.", False, False),
    ("Mira, te cuento algo: hoy fue un día largo.", False, False),   # "mira" suelto no es pedir que mire
    ("¿Qué temperatura hace?", False, False),
]

print("PARTE A: decisión sobre la cámara (sin cámara ni red)\n")
bad = 0
for phrase, want_force, want_allow in CASES:
    force, allow = conversar.look_decision(phrase)   # la misma regla que usa el programa
    good = (force == want_force) and (allow == want_allow)
    bad += not good
    print("%s %-62s se obliga: %-5s (esperado %-5s)  se permite: %-5s (esperado %s)" % (
        "OK " if good else "MAL", phrase, force, want_force, allow, want_allow))
print("\n%d de %d bien" % (len(CASES) - bad, len(CASES)))

print("\nPARTE A3: candado del borrado de memoria\n")


def said(*phrases):
    return [{"role": "user", "content": p} for p in phrases]


# (historial de lo que dijo la persona, herramienta, ¿debe permitirse?)
FORGET_CASES = [
    (said("la delicia."), "olvidar_todo", False),                     # el incidente: ruido mal reconocido
    (said("la delicia."), "olvidar", False),
    (said("Muy bien."), "olvidar", False),
    (said("Olvida todo."), "olvidar_todo", False),                    # falta confirmar
    (said("Olvida todo.", "Sí."), "olvidar_todo", True),              # pidió y confirmó
    (said("Olvida todo.", "No, déjalo."), "olvidar_todo", False),     # no confirmó
    (said("Hola.", "Sí."), "olvidar_todo", False),                    # un "sí" suelto no vale
    (said("Olvídalo del gato."), "olvidar", True),
    (said("Borra lo de Max."), "olvidar", True),
    (said("Olvida todo."), "olvidar", True),                          # olvidar() puntual sí, olvidar_todo no
]
forget_bad = 0
for history_said, tool, want in FORGET_CASES:
    got = conversar.forget_allowed(tool, history_said)
    forget_bad += got != want
    print("%s %-14s historial=%-34s permitido: %-5s (esperado %s)" % (
        "OK " if got == want else "MAL", tool, [m["content"] for m in history_said], got, want))
print("\n%d de %d bien" % (len(FORGET_CASES) - forget_bad, len(FORGET_CASES)))

print("\nPARTE A4: ¿le hablan al robot? (su nombre, y lo que NO debe activarlo)\n")
NAME_CASES = [
    ("Hola, Roby, ¿cómo estás?", True),
    ("Robbie, dime lo que estás viendo.", True),
    ("la robin cómo estás", True),
    ("Robi, ¿qué hora es?", True),
    ("hola robby", True),
    ("la delicia.", False),                  # ruido que casi borra la memoria
    ("¡Vamos a ver!", False),
    ("Salam.", False),
    ("Voy a construir un robot.", False),
    ("El robo fue ayer.", False),
    ("Dile que ya voy, estoy hablando con el robot de la tienda.", False),
]
name_bad = 0
for phrase, want in NAME_CASES:
    got = bool(conversar.WAKE_WORD.search(phrase))
    name_bad += got != want
    print("%s %-62s le hablan: %-5s (esperado %s)" % ("OK " if got == want else "MAL", phrase, got, want))
print("\n%d de %d bien" % (len(NAME_CASES) - name_bad, len(NAME_CASES)))

print("\nPARTE A5: ruido que el reconocimiento convierte en texto\n")
NOISE_CASES = [("6", True), ("12.", True), ("Eh.", True), ("Mm.", True), ("", True),
               ("Sí.", False), ("No.", False), ("Ok.", False), ("Vale.", False), ("Ya.", False),
               ("Hola.", False), ("Gracias.", False), ("¿Qué hora es?", False), ("Perfecto.", False)]
noise_bad = 0
for phrase, want in NOISE_CASES:
    got = conversar.is_noise(phrase)
    noise_bad += got != want
    print("%s %-22r es ruido: %-5s (esperado %s)" % ("OK " if got == want else "MAL", phrase, got, want))
print("\n%d de %d bien" % (len(NOISE_CASES) - noise_bad, len(NOISE_CASES)))

print("\nPARTE A2: recorte de respuestas desbocadas\n")
MONOLOGUE = ("Tienes un control remoto en la mano. ¿Quieres que lo mire? Si es así, dime qué quieres que vea. "
             "Si no, puedo describirlo brevemente: es rectangular, negro y con varios botones. ¿Te parece? "
             "Si quieres que lo examine con la cámara, solo dime. ¿Qué prefieres? ¿O necesitas ayuda con")
cut = conversar.shorten(MONOLOGUE)
n_sentences = len([s for s in cut.replace("?", ".").replace("!", ".").split(".") if s.strip()])
ok_cut = n_sentences <= 3 and cut[-1] in ".?!…"
print("%s monólogo de %d caracteres -> %d caracteres, %d frases:\n    %s" % (
    "OK " if ok_cut else "MAL", len(MONOLOGUE), len(cut), n_sentences, cut))
ok_short = conversar.shorten("Hola. Estoy bien.") == "Hola. Estoy bien."   # lo normal no se toca
print("%s una respuesta corta queda igual" % ("OK " if ok_short else "MAL"))

if "--real" in sys.argv:
    import herramientas
    print("\nPARTE B: con la cámara real\n")
    system = {"role": "system",
              "content": conversar.SYSTEM_PROMPT.format(nombre="Robi", ciudad=herramientas.DEFAULT_CITY)
              + "\n\n" + herramientas.memory.as_prompt()}
    history = []
    for phrase in ("¿Qué ves?", "Perfecto.", "¿Qué hora es?", "Dime qué estoy sosteniendo con mi mano."):
        history.append({"role": "user", "content": phrase})
        reply = conversar.respond(system, history)
        history.append({"role": "assistant", "content": reply})
        print("Tú: %s\n    Robi: %s\n" % (phrase, reply))
