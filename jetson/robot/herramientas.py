"""Herramientas que el robot puede usar durante la conversación (function calling de Mistral).

Cada herramienta es una función de Python más su descripción en TOOLS. El modelo decide cuándo
llamarlas; execute() las ejecuta y devuelve el resultado como texto JSON.

Herramientas de partida:
    fecha_hora    : fecha y hora del Jetson
    clima         : tiempo actual de una ciudad (Open-Meteo, sin clave, uso no comercial)
    temporizador  : avisa con voz cuando pasa el tiempo (se pierde si el programa se cierra)
    temporizadores_pendientes / cancelar_temporizadores
    recordar / olvidar / olvidar_todo : memoria persistente en ~/robot/memoria.json (se envía a
                    Mistral en las instrucciones de cada turno)

Para añadir una herramienta: escribe la función, descríbela en TOOLS y regístrala en FUNCTIONS.
"""
import json
import os
import threading
import time
import unicodedata

import requests

def _default_city():
    """Ciudad para el clima cuando no se dice ninguna: variable ROBOT_CITY o archivo ~/robot/ciudad.txt."""
    city = os.environ.get("ROBOT_CITY", "").strip()
    if not city:
        try:
            with open(os.path.expanduser("~/robot/ciudad.txt"), encoding="utf-8") as f:
                city = f.read().strip()
        except (IOError, OSError):
            city = ""
    return city or "Madrid"


DEFAULT_CITY = _default_city()

DAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
          "octubre", "noviembre", "diciembre")

# Códigos WMO del tiempo que devuelve Open-Meteo.
WEATHER_CODES = {
    0: "despejado", 1: "mayormente despejado", 2: "parcialmente nublado", 3: "nublado",
    45: "niebla", 48: "niebla con escarcha",
    51: "llovizna ligera", 53: "llovizna", 55: "llovizna intensa",
    56: "llovizna helada ligera", 57: "llovizna helada",
    61: "lluvia ligera", 63: "lluvia", 65: "lluvia fuerte",
    66: "lluvia helada ligera", 67: "lluvia helada fuerte",
    71: "nevada ligera", 73: "nevada", 75: "nevada fuerte", 77: "granos de nieve",
    80: "chubascos ligeros", 81: "chubascos", 82: "chubascos violentos",
    85: "chubascos de nieve ligeros", 86: "chubascos de nieve fuertes",
    95: "tormenta", 96: "tormenta con granizo ligero", 97: "tormenta fuerte", 99: "tormenta con granizo fuerte",
}


WEATHER_CACHE_S = 600
_weather_cache = {}   # ciudad en minúsculas -> (momento, resultado)


def _get(url, params, attempts=3, timeout=4):
    """GET con reintentos: Open-Meteo a veces tarda en responder y al siguiente intento va rápido."""
    last_error = None
    for _ in range(attempts):
        try:
            return requests.get(url, params=params, timeout=timeout)
        except requests.exceptions.RequestException as error:
            last_error = error
    raise last_error


def now_text():
    """Fecha y hora del Jetson en español."""
    t = time.localtime()
    return "%s %d de %s de %d, las %02d:%02d" % (
        DAYS[t.tm_wday], t.tm_mday, MONTHS[t.tm_mon - 1], t.tm_year, t.tm_hour, t.tm_min)


# --- Temporizadores ---------------------------------------------------------------------------

class Timers:
    """Lista de avisos pendientes. El bucle principal pregunta cuáles han vencido."""

    def __init__(self):
        self._lock = threading.Lock()
        self._items = []   # (momento_de_aviso, mensaje)

    def add(self, seconds, message):
        with self._lock:
            self._items.append((time.time() + seconds, message))

    def has_due(self):
        with self._lock:
            now = time.time()
            return any(due <= now for due, _ in self._items)

    def pop_due(self):
        with self._lock:
            now = time.time()
            due = [m for t, m in self._items if t <= now]
            self._items = [(t, m) for t, m in self._items if t > now]
            return due

    def pending(self):
        with self._lock:
            now = time.time()
            return [(int(t - now), m) for t, m in self._items]

    def clear(self):
        with self._lock:
            count = len(self._items)
            self._items = []
            return count


timers = Timers()


def _spoken_duration(seconds):
    seconds = int(seconds)
    if seconds >= 3600:
        return "%d horas y %d minutos" % (seconds // 3600, (seconds % 3600) // 60)
    if seconds >= 60:
        return "%d minutos y %d segundos" % (seconds // 60, seconds % 60) if seconds % 60 else "%d minutos" % (seconds // 60)
    return "%d segundos" % seconds


# --- Memoria persistente ----------------------------------------------------------------------

MEMORY_FILE = os.path.expanduser("~/robot/memoria.json")
MAX_MEMORIES_IN_PROMPT = 60
MAX_MEMORY_CHARS = 200


def _normalize(text):
    """Minúsculas y sin tildes, para comparar recuerdos."""
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn").strip()


class Memory:
    """Lista de hechos que el robot recuerda entre conversaciones, en un archivo JSON legible."""

    def __init__(self, path=MEMORY_FILE):
        self.path = path

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                items = json.load(f)
            return items if isinstance(items, list) else []
        except (IOError, OSError, ValueError):
            return []

    def _save(self, items):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    def items(self):
        return self._load()

    def add(self, text):
        """Guarda un hecho. Devuelve False si ya estaba."""
        text = " ".join(text.split())[:MAX_MEMORY_CHARS]
        items = self._load()
        if any(_normalize(item["texto"]) == _normalize(text) for item in items):
            return False
        items.append({"texto": text, "fecha": time.strftime("%Y-%m-%d")})
        self._save(items)
        return True

    def forget(self, text):
        """Borra los recuerdos que contienen todas las palabras de text. Devuelve cuántos."""
        words = _normalize(text).split()
        if not words:
            return 0
        items = self._load()
        kept = [i for i in items if not all(w in _normalize(i["texto"]) for w in words)]
        if len(kept) != len(items):
            self._save(kept)
        return len(items) - len(kept)

    def clear(self):
        count = len(self._load())
        self._save([])
        return count

    def as_prompt(self):
        """Texto con los recuerdos para añadir a las instrucciones del modelo."""
        items = self._load()[-MAX_MEMORIES_IN_PROMPT:]
        if not items:
            return "Todavía no recuerdas nada de esta persona."
        return "Esto es lo que recuerdas de esta persona y de su casa:\n" + "\n".join(
            "- %s (anotado el %s)" % (i["texto"], i.get("fecha", "?")) for i in items)


memory = Memory()


# --- Herramientas -----------------------------------------------------------------------------

def fecha_hora():
    return {"fecha_y_hora": now_text()}


def clima(ciudad=None):
    ciudad = (ciudad or DEFAULT_CITY).strip()
    cached = _weather_cache.get(ciudad.lower())
    if cached and time.time() - cached[0] < WEATHER_CACHE_S:
        return cached[1]
    result = _clima(ciudad)
    if "error" not in result:
        _weather_cache[ciudad.lower()] = (time.time(), result)
    return result


def _clima(ciudad):
    found = _get(
        "https://geocoding-api.open-meteo.com/v1/search",
        {"name": ciudad, "count": 1, "language": "es", "format": "json"})
    results = found.json().get("results") if found.ok else None
    if not results:
        return {"error": "No encontré la ciudad '%s'." % ciudad}
    name, lat, lon = results[0]["name"], results[0]["latitude"], results[0]["longitude"]

    r = _get(
        "https://api.open-meteo.com/v1/forecast",
        {"latitude": lat, "longitude": lon, "timezone": "auto",
         "current": "temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,weather_code"})
    if not r.ok:
        return {"error": "El servicio del clima respondió %d." % r.status_code}
    c = r.json()["current"]
    return {
        "ciudad": name,
        "temperatura_c": c["temperature_2m"],
        "sensacion_termica_c": c["apparent_temperature"],
        "humedad_porcentaje": c["relative_humidity_2m"],
        "viento_kmh": c["wind_speed_10m"],
        "condicion": WEATHER_CODES.get(c["weather_code"], "desconocida"),
    }


def temporizador(segundos, mensaje=None):
    segundos = int(segundos)
    if not 1 <= segundos <= 86400:
        return {"error": "El tiempo debe estar entre 1 segundo y 24 horas."}
    mensaje = (mensaje or "").strip() or "Se acabó el tiempo."
    timers.add(segundos, mensaje)
    return {"ok": True, "avisare_en": _spoken_duration(segundos), "mensaje": mensaje}


def temporizadores_pendientes():
    items = timers.pending()
    return {"pendientes": [{"faltan": _spoken_duration(s), "mensaje": m} for s, m in items]}


def cancelar_temporizadores():
    return {"cancelados": timers.clear()}


def mirar(pregunta=None):
    import camara   # se importa aquí para no cargar la cámara si nunca se usa
    try:
        return {"veo": camara.look(pregunta),
                "instruccion": "Cuenta solo lo que dice 'veo'. No añadas objetos ni personas que conozcas "
                               "por tus recuerdos: lo que no aparece ahí, no se ve."}
    except Exception as error:
        return {"error": "No pude usar la cámara: %s" % str(error)[:120]}


def recordar(dato):
    if memory.add(dato):
        return {"ok": True, "anotado": dato}
    return {"ok": True, "nota": "Ya lo recordaba."}


def olvidar(texto):
    return {"olvidados": memory.forget(texto)}


def olvidar_todo():
    return {"olvidados": memory.clear()}


FUNCTIONS = {
    "mirar": mirar,
    "recordar": recordar,
    "olvidar": olvidar,
    "olvidar_todo": olvidar_todo,
    "fecha_hora": fecha_hora,
    "clima": clima,
    "temporizador": temporizador,
    "temporizadores_pendientes": temporizadores_pendientes,
    "cancelar_temporizadores": cancelar_temporizadores,
}

TOOLS = [
    {"type": "function", "function": {
        "name": "mirar",
        "description": "Toma UNA foto con la cámara del robot y la analiza para describir lo que hay delante o "
                       "responder una pregunta sobre lo que se ve (objetos, personas, texto). Úsala SOLO cuando "
                       "la persona te pida expresamente que mires, veas, describas, leas o reconozcas algo. "
                       "Nunca la uses por iniciativa propia ni 'por si acaso'. La foto se envía a Mistral para "
                       "analizarla y no se guarda.",
        "parameters": {"type": "object", "properties": {
            "pregunta": {"type": "string",
                         "description": "Lo que la persona quiere saber de la imagen, con sus palabras. Si solo "
                                        "pidió mirar, no pongas este campo."}}}}},
    {"type": "function", "function": {
        "name": "recordar",
        "description": "Guarda un dato para recordarlo en futuras conversaciones. Úsala cuando te pidan "
                       "que recuerdes algo o cuando la persona cuente un dato personal duradero (su nombre, "
                       "familia, mascotas, gustos, rutinas). Escribe el dato como una frase corta y clara en "
                       "tercera persona, con las palabras exactas que dijo la persona y SIN interpretar ni "
                       "añadir nada: no cambies el tipo de dato (un gusto no es una mascota, ni un objeto es "
                       "una persona) ni digas que le gusta algo si no lo dijo (por ejemplo, con el "
                       "formato 'A la persona le gusta <algo>.' o 'La mascota de la persona se llama <nombre>.'; "
                       "esos marcadores no son datos reales). Nunca guardes contraseñas, números de tarjeta, "
                       "datos de salud ni nada sensible.",
        "parameters": {"type": "object", "properties": {
            "dato": {"type": "string", "description": "El dato a recordar, en una frase corta."}},
            "required": ["dato"]}}},
    {"type": "function", "function": {
        "name": "olvidar",
        "description": "Borra de la memoria los recuerdos que contengan las palabras indicadas. Úsala cuando "
                       "pidan olvidar algo concreto.",
        "parameters": {"type": "object", "properties": {
            "texto": {"type": "string", "description": "Palabras clave del recuerdo a olvidar, por ejemplo 'gato'."}},
            "required": ["texto"]}}},
    {"type": "function", "function": {
        "name": "olvidar_todo",
        "description": "Borra TODA la memoria. Solo llámala después de preguntar '¿Seguro que quieres que "
                       "olvide todo?' y de que la persona responda que sí.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "fecha_hora",
        "description": "Devuelve la fecha y la hora actuales. Úsala siempre que pregunten qué día u hora es.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "clima",
        "description": "Devuelve el tiempo actual (temperatura, sensación térmica, humedad, viento y "
                      "condición) de una ciudad. Úsala siempre que pregunten por el clima o la temperatura.",
        "parameters": {"type": "object", "properties": {
            "ciudad": {"type": "string",
                       "description": "Nombre de la ciudad. Si la persona no dice ninguna, no pongas este campo."}}}}},
    {"type": "function", "function": {
        "name": "temporizador",
        "description": "Programa un aviso: cuando pase el tiempo, el robot lo dirá en voz alta. Úsala para "
                       "temporizadores y recordatorios de corta duración. Convierte minutos u horas a segundos.",
        "parameters": {"type": "object", "properties": {
            "segundos": {"type": "integer", "description": "Segundos que faltan para el aviso."},
            "mensaje": {"type": "string", "description": "Lo que el robot debe decir al vencer, por ejemplo "
                                                         "'Es hora de alimentar al gato.'"}},
            "required": ["segundos"]}}},
    {"type": "function", "function": {
        "name": "temporizadores_pendientes",
        "description": "Lista los temporizadores y avisos que están pendientes.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "cancelar_temporizadores",
        "description": "Cancela todos los temporizadores pendientes.",
        "parameters": {"type": "object", "properties": {}}}},
]


def execute(name, arguments):
    """Ejecuta una herramienta pedida por el modelo. Devuelve siempre texto JSON, también si falla."""
    function = FUNCTIONS.get(name)
    if function is None:
        return json.dumps({"error": "No existe la herramienta '%s'." % name}, ensure_ascii=False)
    try:
        args = json.loads(arguments) if isinstance(arguments, str) and arguments.strip() else (arguments or {})
        result = function(**args)
    except Exception as error:
        result = {"error": "Falló la herramienta %s: %s" % (name, str(error)[:150])}
    return json.dumps(result, ensure_ascii=False)
