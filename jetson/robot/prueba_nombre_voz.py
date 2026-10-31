#!/usr/bin/env python3
"""Prueba con voz real del filtro del nombre: qué oye Vosk y si el robot se daría por llamado.

No usa Mistral ni la nube: solo el micrófono y Vosk (local). Di frases con y sin el nombre.

    sh ~/robot/run_isolated.sh ~/robot/prueba_nombre_voz.py
"""
from conversar import WAKE_WORD, Listener, make_transcriber


def main():
    print("Cargando Vosk...", flush=True)
    transcribe = make_transcriber("vosk")
    listener = Listener()
    listener.calibrate_now()
    called = ignored = 0
    print("Listo. Habla (Ctrl+C para terminar).", flush=True)
    try:
        while True:
            audio = listener.listen()
            if audio is None:
                continue
            heard = transcribe(audio)
            match = WAKE_WORD.search(heard)
            if match:
                called += 1
            else:
                ignored += 1
            print("   Vosk oyó: \"%s\"  ->  %s" % (heard, "LLAMADO (%s)" % match.group(0) if match else "ignorado"),
                  flush=True)
    except KeyboardInterrupt:
        print("\nLlamado %d veces, ignorado %d." % (called, ignored))


if __name__ == "__main__":
    main()
