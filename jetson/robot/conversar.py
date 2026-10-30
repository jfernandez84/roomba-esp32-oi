#!/usr/bin/env python3
"""Conversación por voz con el robot: escucha, razona (con herramientas) y habla.

    escuchar  : micrófono de la cámara USB + detector de voz simple (por volumen)
    entender  : Voxtral de Mistral (nube, por defecto) o Vosk (local, con --stt vosk)
    razonar   : Mistral (nube) con herramientas: fecha y hora, clima, temporizadores (herramientas.py)
    hablar    : voz de Mistral (nube, por defecto) con Piper (local) como respaldo si falla;
                cada frase se reproduce por HDMI mientras se genera la siguiente

Se ejecuta con run_isolated.sh, porque Vosk y Piper necesitan librerías más nuevas que las del
Ubuntu 18.04 del Jetson Nano:
    sh ~/robot/run_isolated.sh ~/robot/conversar.py [--stt voxtral|vosk] [--voz mistral|piper]
                                                    [--voice-id voice_483] [--nombre Robi]

Para terminar: Ctrl+C, o decir "adiós" / "hasta luego".
Qué sale a internet: el texto de la conversación (a Mistral, para razonar), el texto de cada respuesta
(a Mistral, para la voz), las consultas de las herramientas (el clima va a Open-Meteo, con la ciudad) y,
con --stt voxtral, el audio de cada frase que dices (solo cuando se detecta voz, no el micrófono abierto
todo el tiempo). Con --stt vosk --voz piper solo sale el texto para razonar y las herramientas.
"""
import argparse
import audioop
import collections
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave

from herramientas import DEFAULT_CITY, TOOLS, execute, memory, timers
from mistral_client import chat_message, speak, transcribe

HOME = os.path.expanduser("~")
TTS = HOME + "/robot/tts"
FOCAL = TTS + "/focal"
PIPER_MODEL = TTS + "/voices/es_MX-claude-high.onnx"
VOSK_MODEL = HOME + "/robot/models/vosk-model-small-es-0.42"

MIC = "plughw:CARD=C170,DEV=0"   # micrófono de la cámara, por nombre y no por número
SPEAKER = "plughw:0,3"           # HDMI
RATE = 16000
FRAME_BYTES = 640                # 20 ms de audio a 16 kHz, 16 bits, mono
HDMI_SILENCE_S = 0.6             # el canal HDMI tarda en despertar y se come el inicio
MAX_TOOL_ROUNDS = 4              # vueltas máximas de llamadas a herramientas por pregunta

SYSTEM_PROMPT = (
    "Eres {nombre}, un robot doméstico amable y curioso. Hablas en español latino neutro. "
    "Tus respuestas se leen en voz alta, así que sé breve: una o dos frases cortas y naturales, "
    "nunca más de tres, sin emojis, sin listas ni formato. Si la persona dice solo \"sí\" o \"por "
    "favor\", responde en una frase. "
    "El texto que recibes viene de un reconocedor de voz: puede tener errores; interpreta lo que la "
    "persona quiso decir. "
    "Tú SÍ debes escribir tus respuestas con puntuación normal, con comas y puntos, porque se leen en "
    "voz alta y las pausas son importantes. "
    "Tienes herramientas para consultar la fecha y la hora, el clima de una ciudad y poner "
    "temporizadores o avisos. Úsalas siempre que haga falta y NUNCA inventes la hora, la fecha ni el "
    "clima: si preguntan por eso, llama a la herramienta y di lo que devuelve. Si preguntan por el "
    "clima sin decir ciudad, es el de {ciudad}. Cuando programes un temporizador, confirma en una frase "
    "cuánto falta. Los temporizadores se pierden si el robot se apaga. "
    "Cuando hables de números, redondéalos como lo haría una persona: di \"unos veinte grados\" en "
    "lugar de \"diecinueve con nueve décimas\", y no pronuncies decimales a menos que lo pidan. "
    "Tienes memoria: la lista de recuerdos está al final de estas instrucciones. Úsala con naturalidad, "
    "sin recitarla. Cuando te pidan que recuerdes algo, o cuenten un dato personal duradero (su nombre, "
    "familia, mascotas, gustos, rutinas), llama a la herramienta recordar con una frase corta en tercera "
    "persona y confirma con una sola palabra o frase breve, como \"Anotado.\". Solo puedes decir que "
    "anotaste algo si acabas de llamar a la herramienta recordar en este mismo turno: si no la llamaste, "
    "no se guardó. No guardes cosas pasajeras. "
    "NUNCA guardes contraseñas ni claves de ningún tipo, PIN, números de tarjetas o cuentas, "
    "documentos ni datos de salud: si te lo piden, di que eso no lo guardas. Los nombres de cosas, "
    "como el nombre de una red wifi, SÍ se pueden guardar mientras no incluyan la contraseña. "
    "Para olvidar algo concreto usa olvidar. Para borrar toda tu memoria, "
    "primero pregunta \"¿Seguro que quieres que olvide todo?\" y solo si responde que sí llama a "
    "olvidar_todo. "
    "Aparte de esas herramientas NO puedes hacer nada más: no puedes buscar en internet ni leer "
    "noticias, no puedes reproducir música ni cantar y no controlas ningún aparato. Nunca prometas "
    "algo que no puedas cumplir: si te piden algo fuera de tus herramientas, di que todavía no puedes. "
    "No inventes habilidades ni afirmes cosas del mundo real que no sepas. Si no sabes algo, dilo con "
    "sinceridad. "
    "Todavía no tienes un cuerpo que se mueva; si te piden moverte, di que pronto podrás hacerlo."
)

FAREWELL = ("adiós", "adios", "hasta luego", "nos vemos", "chao")


# --- Hablar -----------------------------------------------------------------------------------

def clean_for_speech(text):
    """Quita lo que suena mal al leerse: emojis, markdown y saltos de línea."""
    text = re.sub(u"[\U00010000-\U0010ffff]", "", text)
    text = re.sub(r"[*#_`~>]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text, min_len=25):
    """Divide en frases, juntando las muy cortas para no hacer trozos diminutos."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+", text) if p.strip()]
    chunks, current = [], ""
    for part in parts:
        current = (current + " " + part).strip()
        if len(current) >= min_len:
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


class Voice:
    """Voz de Mistral (nube) con Piper (local) de respaldo. Reproduce en un hilo aparte."""

    def __init__(self, engine, voice_id):
        self.engine = engine
        self.voice_id = voice_id
        self.out_dir = tempfile.mkdtemp(prefix="voz_")
        self.counter = 0
        self.first_audio_at = None
        self.piper = None
        if engine == "piper":
            self._start_piper()
        self.queue = queue.Queue()
        threading.Thread(target=self._play_loop, daemon=True).start()

    def _start_piper(self):
        """Piper se queda cargado en memoria una vez arrancado (carga unos 3 s)."""
        loader = FOCAL + "/lib/aarch64-linux-gnu/ld-2.31.so"
        libs = FOCAL + "/lib/aarch64-linux-gnu:" + FOCAL + "/usr/lib/aarch64-linux-gnu:" + TTS + "/piper"
        self.piper_log = open(self.out_dir + "/piper.log", "w")
        self.piper = subprocess.Popen(
            [loader, "--library-path", libs, TTS + "/piper/piper", "--model", PIPER_MODEL,
             "--espeak_data", TTS + "/piper/espeak-ng-data", "--output_dir", self.out_dir],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.piper_log, bufsize=0)

    def _synth_piper(self, sentence):
        if self.piper is None:
            print("Cargando Piper de respaldo...", flush=True)
            self._start_piper()
        self.piper.stdin.write((sentence + "\n").encode("utf-8"))
        self.piper.stdin.flush()
        return self.piper.stdout.readline().decode("utf-8").strip() or None

    def _synth_mistral(self, sentence):
        self.counter += 1
        path = "%s/mistral_%04d.wav" % (self.out_dir, self.counter)
        with open(path, "wb") as f:
            f.write(speak(sentence, voice_id=self.voice_id, fmt="wav"))
        return path

    def say(self, text):
        self.first_audio_at = None
        first = True
        min_len = 45 if self.engine == "mistral" else 25   # menos peticiones a la nube
        for sentence in split_sentences(clean_for_speech(text), min_len):
            path = None
            if self.engine == "mistral":
                try:
                    path = self._synth_mistral(sentence)
                except Exception as error:
                    print("La voz de Mistral falló (%s); uso Piper." % str(error)[:120], flush=True)
            if path is None:
                path = self._synth_piper(sentence)
            if path:
                self.queue.put((path, first))
                first = False
        self.queue.join()

    def _play_loop(self):
        while True:
            path, first = self.queue.get()
            try:
                to_play = path
                if first:
                    to_play = path + ".pad.wav"
                    subprocess.call(["sox", path, to_play, "pad", str(HDMI_SILENCE_S), "0"])
                    self.first_audio_at = time.time() + HDMI_SILENCE_S   # tras el silencio inicial
                subprocess.call(["aplay", "-D", SPEAKER, "-q", to_play])
                for f in {path, path + ".pad.wav"}:
                    if os.path.exists(f):
                        os.remove(f)
            finally:
                self.queue.task_done()

    def close(self):
        if self.piper is not None:
            try:
                self.piper.stdin.close()
                self.piper.terminate()
            except Exception:
                pass


# --- Escuchar (micrófono + detector de voz) ---------------------------------------------------

class Listener:
    def __init__(self):
        self.threshold = None

    def _open(self):
        return subprocess.Popen(
            ["arecord", "-D", MIC, "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw", "-q"],
            stdout=subprocess.PIPE)

    def calibrate_now(self):
        """Mide el ruido de fondo. Hay que llamarlo cuando el robot NO está hablando."""
        proc = self._open()
        try:
            self._calibrate(proc)
        finally:
            proc.terminate()

    def _calibrate(self, proc):
        for _ in range(10):   # los primeros fragmentos de arecord suelen traer un chasquido
            proc.stdout.read(FRAME_BYTES)
        levels = sorted(audioop.rms(proc.stdout.read(FRAME_BYTES), 2) for _ in range(50))
        ambient = levels[len(levels) // 2]
        self.threshold = max(400, ambient * 3)
        print("Ruido de fondo: %d  umbral de voz: %d" % (ambient, self.threshold))

    def listen(self, interrupt=None, max_seconds=15):
        """Devuelve el audio (bytes, 16 kHz mono) de una frase completa, o None.

        Si interrupt() devuelve True mientras nadie está hablando, termina y devuelve None
        (se usa para atender un temporizador que ha vencido)."""
        proc = self._open()
        try:
            if self.threshold is None:
                self._calibrate(proc)
            preroll = collections.deque(maxlen=15)   # 0,3 s antes de empezar a hablar
            frames, loud_run, quiet_run, speaking = [], 0, 0, False
            while True:
                data = proc.stdout.read(FRAME_BYTES)
                if len(data) < FRAME_BYTES:
                    return None
                loud = audioop.rms(data, 2) > self.threshold
                if not speaking:
                    if interrupt is not None and interrupt():
                        return None
                    preroll.append(data)
                    loud_run = loud_run + 1 if loud else 0
                    if loud_run >= 3:
                        speaking = True
                        frames = list(preroll)
                else:
                    frames.append(data)
                    quiet_run = 0 if loud else quiet_run + 1
                    if quiet_run >= 45 or len(frames) * 0.02 >= max_seconds:   # 0,9 s de pausa
                        break
            return b"".join(frames) if len(frames) * 0.02 >= 0.5 else None
        finally:
            proc.terminate()


# --- Entender (Vosk local o Voxtral en la nube) -----------------------------------------------

def make_transcriber(engine):
    if engine == "voxtral":
        def voxtral(audio):
            path = os.path.join(tempfile.gettempdir(), "conversar.wav")
            with wave.open(path, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(RATE)
                wav.writeframes(audio)
            return transcribe(path, language="es")
        return voxtral

    from vosk import KaldiRecognizer, Model, SetLogLevel
    SetLogLevel(-1)
    model = Model(VOSK_MODEL)

    def vosk(audio):
        recognizer = KaldiRecognizer(model, RATE)
        recognizer.AcceptWaveform(audio)
        return json.loads(recognizer.FinalResult()).get("text", "")
    return vosk


# --- Razonar con herramientas -----------------------------------------------------------------

# Si la respuesta dice que algo quedó anotado o guardado, esa acción tiene que haber ocurrido de verdad.
CLAIMS_SAVED = re.compile(
    r"\b(anot(ó|é|ad[oa]s?|aré)|guard(ó|é|ad[oa]s?|aré|o|amos)|lo recordar[eé]|ya lo (tengo|sé))\b",
    re.IGNORECASE)
REFUSES_SAVING = re.compile(r"\bno\b[^.]{0,25}\b(guard|anot|record)", re.IGNORECASE)   # "no lo guardo"
MEMORY_TOOLS = ("recordar", "olvidar", "olvidar_todo")
FALSE_CLAIM_WARNING = (
    "[Aviso del sistema] Dijiste que anotaste algo, pero no llamaste a la herramienta recordar, así "
    "que NO se guardó. Llama ahora a recordar con el dato que la persona acaba de contarte."
)
REMEMBER_ONLY = [t for t in TOOLS if t["function"]["name"] == "recordar"]


def respond(system, history):
    """Pregunta a Mistral y atiende las herramientas que pida hasta tener una respuesta en texto."""
    messages = [system] + history[-12:]
    used = set()
    force_remember = False
    forced_once = False   # solo se obliga una vez por pregunta
    for _ in range(MAX_TOOL_ROUNDS):
        if force_remember:
            # Solo se le permite la herramienta recordar y se le obliga a llamarla.
            message = chat_message(messages, max_tokens=150, temperature=0.2, tools=REMEMBER_ONLY,
                                   tool_choice="any")
            force_remember = False
        else:
            message = chat_message(messages, max_tokens=150, temperature=0.4, tools=TOOLS)
        calls = message.get("tool_calls")
        if not calls:
            reply = (message.get("content") or "").strip()
            claims_saved = CLAIMS_SAVED.search(reply) and not REFUSES_SAVING.search(reply)
            if claims_saved and not used.intersection(MEMORY_TOOLS) and not forced_once:
                print("   [aviso] dijo que anotó algo sin llamar a la herramienta; lo obligo a hacerlo", flush=True)
                messages.append({"role": "assistant", "content": reply})
                messages.append({"role": "user", "content": FALSE_CLAIM_WARNING})
                force_remember = True
                forced_once = True
                continue
            return reply
        messages.append(message)
        for call in calls:
            name = call["function"]["name"]
            arguments = call["function"].get("arguments", "")
            used.add(name)
            result = execute(name, arguments)
            print("   [herramienta] %s(%s) -> %s" % (name, arguments, result[:160]), flush=True)
            messages.append({"role": "tool", "name": name, "content": result, "tool_call_id": call["id"]})
    return "No logré completar eso. ¿Me lo puedes pedir de otra forma?"


# --- Bucle principal --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Conversación por voz con el robot")
    parser.add_argument("--stt", choices=("vosk", "voxtral"), default="voxtral")
    parser.add_argument("--voz", choices=("mistral", "piper"), default="mistral")
    parser.add_argument("--voice-id", default="voice_483", help="voz de Mistral (identificador o slug)")
    parser.add_argument("--nombre", default="Robi")
    args = parser.parse_args()

    print("Cargando voz y reconocimiento...", flush=True)
    voice = Voice(args.voz, args.voice_id)
    transcriber = make_transcriber(args.stt)
    listener = Listener()
    history = []
    print("Recuerdos guardados: %d (archivo: %s)" % (len(memory.items()), memory.path))

    try:
        listener.calibrate_now()   # antes de que el robot hable, para no medir su propia voz
        voice.say("Hola, soy %s. Ya puedo escucharte." % args.nombre)
        while True:
            print("\nEscuchando...", flush=True)
            time.sleep(0.4)   # que no se oiga la cola de su propia voz
            audio = listener.listen(interrupt=timers.has_due)

            for message in timers.pop_due():   # avisos de temporizadores vencidos
                print("   [aviso] %s" % message, flush=True)
                voice.say(message)
            if audio is None:
                continue

            t0 = time.time()
            text = transcriber(audio).strip()
            if not text:
                continue
            print("Tú: %s   (%.1f s)" % (text, time.time() - t0))
            if any(word in text.lower() for word in FAREWELL):
                voice.say("Hasta luego.")
                break

            history.append({"role": "user", "content": text})
            # Las instrucciones se rehacen en cada turno para incluir los recuerdos más recientes.
            system = {"role": "system",
                      "content": SYSTEM_PROMPT.format(nombre=args.nombre, ciudad=DEFAULT_CITY)
                      + "\n\n" + memory.as_prompt()}
            t1 = time.time()
            try:
                reply = respond(system, history)
            except Exception as error:
                print("Error de Mistral: %s" % error)
                history.pop()
                voice.say("No pude conectarme para pensar. Inténtalo de nuevo.")
                continue
            history.append({"role": "assistant", "content": reply})
            print("%s: %s   (%.1f s)" % (args.nombre, reply, time.time() - t1))
            t2 = time.time()
            voice.say(reply)
            first_word = (voice.first_audio_at - t2) if voice.first_audio_at else 0
            print("   (primera palabra a los %.1f s, hablar en total: %.1f s)" % (first_word, time.time() - t2))
    except KeyboardInterrupt:
        print("\nTerminado.")
    finally:
        voice.close()


if __name__ == "__main__":
    sys.exit(main())
