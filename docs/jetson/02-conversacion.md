# Fase 2: el robot conversa y razona

El Jetson escucha, razona y habla, en español latino. Esta fase todavía no mueve la base del Roomba.

## Qué es local y qué va a la nube

| Pieza | Dónde | Qué sale de casa |
|---|---|---|
| Captar el sonido (micrófono de la cámara USB) | Local | Nada |
| **Entender** lo que dices: Voxtral (por defecto) | Nube (Mistral) | El audio de cada frase detectada (no el micrófono abierto todo el rato) |
| Entender con Vosk (opcional, `--stt vosk`) | Local | Nada |
| **Razonar**: Mistral Small | Nube | El texto de la conversación |
| **Hablar**: Piper, voz `es_MX-claude-high` | Local | Nada |
| Sonido de salida por HDMI | Local | Nada |

La clave de la API de Mistral se guarda en `~/robot/.env` del Jetson (permisos 600) y **nunca** en este repositorio. No he revisado la política de conservación de datos de Mistral.

## Por qué hay un lanzador "aislado"

El Jetson Nano trae Ubuntu 18.04 (glibc 2.27, `libstdc++` hasta `GLIBCXX_3.4.25`). Piper y Vosk están compilados para sistemas más nuevos y no arrancan:

```
version `GLIBC_2.29' not found
version `GLIBCXX_3.4.26' not found
```

La solución que funcionó sin tocar el sistema: [`jetson/scripts/fetch_focal_libs.sh`](../../jetson/scripts/fetch_focal_libs.sh) descarga `libc6`, `libstdc++6` y `libgcc-s1` de Ubuntu 20.04 a `~/robot/tts/focal`, y los programas se ejecutan con su cargador (`ld-2.31.so --library-path ...`). Lo usan [`say.sh`](../../jetson/scripts/say.sh) (Piper) y [`run_isolated.sh`](../../jetson/scripts/run_isolated.sh) (Python con Vosk).

## Archivos

| Archivo | Para qué |
|---|---|
| [`jetson/robot/conversar.py`](../../jetson/robot/conversar.py) | El bucle de conversación completo |
| [`jetson/robot/mistral_client.py`](../../jetson/robot/mistral_client.py) | Cliente mínimo de Mistral con `requests` (el SDK oficial no instala en Python 3.6) |
| `jetson/robot/api_check.py`, `voices_check.py`, `stt_cloud_test.py`, `stt_local_test.py`, `tts_cloud_test.py` | Pruebas sueltas |
| `jetson/scripts/say.sh`, `run_isolated.sh`, `fetch_focal_libs.sh` | Lanzadores de Piper y Vosk |

## Cómo ejecutarlo (en el Jetson)

```bash
sh ~/robot/run_isolated.sh ~/robot/conversar.py                    # Voxtral en la nube (por defecto)
sh ~/robot/run_isolated.sh ~/robot/conversar.py --stt vosk         # Vosk local
sh ~/robot/run_isolated.sh ~/robot/conversar.py --nombre Robi      # nombre del robot
```

Se termina con Ctrl+C o diciendo "adiós". Se necesitan los modelos en `~/robot/models/vosk-model-small-es-0.42` y `~/robot/tts/voices/es_MX-claude-high.onnx`.

## Resultados de las pruebas

- **Escuchar (Vosk):** modelo cargado en 1,6 a 2,1 s; reconoce 8 s de audio en unos 3,4 s. Acertó frases normales; se equivocó en alguna palabra ("hacen" por "hace"). No pone puntuación ni mayúsculas.
- **Escuchar (Voxtral):** acertó una frase de prueba con puntuación.
- **Razonar:** `mistral-small-latest` responde en unos 0,8 s. Con una cuenta **sin crédito**, Small y Medium daban error 429 (límite 0); los Ministral sí funcionaban. Con crédito de pago por uso, todos funcionan.
- **Hablar (Piper):** la voz `claude-high` suena bien. `ald-medium` sonó mal y se descartó. La síntesis es más lenta que el tiempo real (de 1,4 a 2,4 veces) porque el Jetson está en el modo de 5 W; las frases se generan y se reproducen en paralelo para reducir la espera.
- **Voz de Mistral (Voxtral TTS):** descartada: solo tiene 10 voces en inglés y suena con acento inglés.
- **HDMI:** se comía el inicio del audio; se arregla con 0,6 s de silencio inicial.

## Herramientas (function calling)

El modelo es solo el cerebro; las herramientas son sus manos. Se declaran en [`jetson/robot/herramientas.py`](../../jetson/robot/herramientas.py) y el modelo decide cuándo llamarlas (parámetro `tools` de la API de chat de Mistral). `conversar.py` ejecuta la herramienta pedida, devuelve el resultado con un mensaje de rol `tool` y repite hasta tener una respuesta en texto.

| Herramienta | Qué hace |
|---|---|
| `fecha_hora` | Fecha y hora del Jetson |
| `clima(ciudad)` | Tiempo actual vía Open-Meteo (sin clave, uso no comercial). Ciudad por defecto: la de `~/robot/ciudad.txt` del Jetson (o la variable `ROBOT_CITY`; si no hay ninguna, Madrid). Caché de 10 min y hasta 3 intentos de 4 s |
| `temporizador(segundos, mensaje)` | Avisa con voz cuando vence, sin que nadie le hable. Se pierde si se cierra el programa |
| `temporizadores_pendientes`, `cancelar_temporizadores` | Gestión de los temporizadores |

Resultado de la prueba: el robot llamó a `clima` y dijo "unos veinte grados", programó un temporizador de 30 s y habló solo al vencer, y ante "reproduce música de mi Spotify" respondió que todavía no puede.

Para añadir una herramienta: escribir la función, describirla en `TOOLS` y registrarla en `FUNCTIONS`. Si una herramienta falla, devuelve un error al modelo, que lo explica en vez de inventar un dato.

Lo que **no** sabe hacer (y no debe prometer): buscar en internet, música/Spotify, recordar entre conversaciones, ver, moverse.

## Memoria persistente

El robot recuerda datos entre conversaciones. Se guardan en `~/robot/memoria.json` del Jetson (un archivo de texto legible, permisos 600; se puede abrir, editar o borrar a mano). En cada turno, `conversar.py` añade la lista de recuerdos a las instrucciones del modelo, así que **los recuerdos se envían a Mistral en cada petición**.

Herramientas: `recordar(dato)`, `olvidar(texto)` (borra los recuerdos que contengan esas palabras, sin distinguir mayúsculas ni tildes) y `olvidar_todo` (el robot pregunta antes "¿Seguro?").

No guarda contraseñas, claves, PIN, números de tarjeta ni datos de salud, y lo rechaza aunque se lo pidan.

### Qué se comprobó
- Recuerda entre sesiones: tras cerrar y reabrir el programa, contestó "Tu gato se llama Tommy".
- Olvidar, olvidar todo con confirmación, y rechazar una contraseña: bien.
- Prueba sin audio (`jetson/robot/prueba_memoria_texto.py`, con memoria temporal): **6 de 7** frases bien en dos ejecuciones seguidas, pero **el caso que falla cambia de una ejecución a otra** (el modelo no es determinista en los casos dudosos, como el nombre de una red wifi).

### Fallos de los que se aprendió
- **Afirmaba haber anotado algo sin llamar a la herramienta** ("queda anotado" sin guardar nada). Pedírselo en las instrucciones no bastó. Ahora, si la respuesta dice que anotó o guardó algo y en ese turno no se llamó a `recordar`, se vuelve a preguntar permitiendo solo esa herramienta y obligando a usarla (`tool_choice: "any"`). No detecta una respuesta falsa que no use esas palabras.
- **Un ejemplo concreto en la descripción de la herramienta se coló en las respuestas** ("El gato de la persona se llama Luna" cuando se habló de un perro). Los ejemplos de las descripciones deben ser marcadores genéricos (`<nombre>`).
- A veces generaliza el dato ("mascota" en vez de "perro").

## Problemas conocidos y pendientes

- **Alimentación:** una fuente de 5 V y 4 A con conector cilíndrico (jumper en J48) permitiría el modo de 10 W y acelerar la voz. Con la actual el Jetson se apagó.
- **Más herramientas pendientes:** memoria persistente entre conversaciones, Spotify (requiere cuenta Premium y registrar una aplicación; sin verificar), calendario, domótica.
- **Latencia del clima:** Open-Meteo a veces tarda; una vez dio 8 s. Se mitigó con caché y reintentos.
- **Palabra de activación:** ahora escucha siempre. El micrófono abierto con altavoces puede oírse a sí mismo; se evita no escuchando mientras habla.
- **WiFi:** el Nano no trae adaptador; hace falta uno compatible para que el robot se mueva por la casa.
- **Integración con la base:** pendiente (Fase 3).
