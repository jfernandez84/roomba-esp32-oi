# Visión, privacidad y candados

El robot puede mirar con una cámara, y varios "candados" en el código impiden que haga cosas que nadie le pidió. Esta página recoge cómo funciona, qué se probó y qué no.

## Visión

Flujo: `conversar.py` pide una foto → [`camara.py`](../../jetson/robot/camara.py) la toma y la envía a un modelo de visión de Mistral (`mistral-medium-latest`) → recibe una descripción → el modelo de conversación la cuenta con sus palabras. La foto se borra del Jetson al instante, y **la imagen se envía a Mistral**.

- **Cámara de pruebas:** Logitech C170 (640×480, enfoque fijo), `/dev/video0`, capturada con `ffmpeg`. Es modesta; se cambiará por una mejor.
- **La exposición tarda en estabilizarse.** Midiendo el brillo medio, empieza en ~185 y baja a ~103 hacia el fotograma 40 (unos 2,7 s a 15 fps). Capturar antes da fotos sobreexpuestas, así que se descartan los primeros 40 fotogramas.
- **El modo MJPEG de esta cámara entrega los primeros fotogramas corruptos** (`No JPEG data found`); se usa YUYV sin comprimir.
- **Qué modelo de visión:** con la misma foto, `mistral-small` inventó objetos que no estaban (una gorra, un control remoto), `ministral-14b` confundió el respaldo de una silla con una capucha y `mistral-medium` fue el más fiel. Es **una sola foto**, no una evaluación general. Con `medium` siguen apareciendo confusiones del mismo tipo (el respaldo de la silla como "cabello largo").
- Una descripción que parece un invento puede ser correcta: en dos sesiones se dio por falso que el modelo viera "otra persona en una cama al fondo", y era real (otra persona de la casa). Conviene comprobarlo antes de juzgar al modelo.
- **Leer texto funciona** con letra grande (leyó el rótulo de una caja).

## De dónde sale la foto

El archivo `~/robot/camara.txt` del Jetson dice `local` (la cámara USB del Jetson, por defecto) o la dirección de una cámara remota. Si la remota no responde, el robot usa la del Jetson y lo muestra en la terminal.

### Cámara del Mac, mientras no haya una mejor

En el Mac:

```bash
python3 jetson/visor/camara_mac_servidor.py --host IP_DEL_JETSON --user USUARIO --key ~/.ssh/mi_clave
```

En el Jetson: `echo http://127.0.0.1:8766/foto > ~/robot/camara.txt` (y `echo local > ~/robot/camara.txt` para volver).

- [`foto_mac.swift`](../../jetson/visor/foto_mac.swift) saca una foto con AVFoundation (viene con macOS, hace falta Xcode para compilarlo; el servidor lo compila la primera vez). macOS pide permiso de cámara.
- [`camara_mac_servidor.py`](../../jetson/visor/camara_mac_servidor.py) sirve esa foto en `127.0.0.1` (solo el propio Mac) y abre un **túnel SSH inverso desde el Mac** hacia el Jetson. No se abre ningún puerto del Mac en la red ni el Jetson puede entrar al Mac: solo puede pedir una foto. La cámara se enciende unos 2 s por foto (3,1 a 3,4 s en total).
- El túnel se reconecta solo: una vez se cayó y el robot usó la cámara del Jetson sin que nadie lo notara.

### Visor en directo

[`visor_camara.py`](../../jetson/visor/visor_camara.py) muestra en el navegador del Mac lo que ve la cámara del Jetson, por el túnel SSH y con solo la biblioteca estándar. La cámara admite un programa a la vez: con el visor abierto, el robot no puede mirar.

## Candados

Las instrucciones al modelo no bastaron: incumplió varias, así que las reglas importantes están **en el código**. Cada una nació de un fallo real.

| Candado | Regla | Fallo que lo motivó |
|---|---|---|
| **Cámara** | Si la frase pide ver claramente ("¿qué ves?", "dime qué estoy sosteniendo"), el programa toma la foto él mismo. Si no, bloquea cualquier intento del modelo de usar la cámara | Tomó fotos sin que se las pidieran ("Perfecto.") y a veces no miraba cuando se lo pedían, inventando lo que sostenía la persona |
| **Cámara: muletillas y correcciones** | "lo que ves como..." dentro de una afirmación no cuenta; "¡Vamos a ver!" tampoco | Ambas abrieron la cámara sin que nadie lo pidiera |
| **Borrar memoria** | `olvidar` solo si la persona pide olvidar o borrar algo; `olvidar_todo` solo si antes pidió olvidar todo y ahora confirma con un sí | Con un ruido ("la delicia.") el modelo propuso borrar toda la memoria |
| **Guardar sin hacerlo** | Si dice que anotó algo y no llamó a `recordar`, se le obliga a llamarla (`tool_choice: "any"`) | Decía "anotado" sin guardar nada |
| **Ruido** | Se ignora lo que no tiene al menos 3 letras ("6", "eh"), salvo "sí", "no", "ok", "ya", "vale" | Respondió "¿En qué puedo ayudarte?" a un "6" |
| **Nombre** | Solo reacciona si oye su nombre (Roby, Robby, Robi, Robbie...) o durante 20 s tras hablar él. El primer filtro lo hace Vosk en local | Respondía a todo lo que oía, incluida una conversación telefónica de fondo |
| **Umbral de voz** | Tope de 1800 y ajuste continuo; avisa si no oye nada en 15 s | Midió 1209 de ruido al arrancar, el umbral subió a 3627 y no oía a nadie |
| **Longitud** | Máximo 3 frases, sin dejar una a medias | Un monólogo de ~170 palabras tardó 31 s en decirse |
| **Voz** | Tope de 15 s para la voz de Mistral y Piper de respaldo ya cargado | La API se quedó 60 s sin responder y el robot tardó 67 s en hablar |
| **Memoria** | Guarda con las palabras de la persona, sin interpretar; no guarda contraseñas | Guardó "le gusta" y "mascota" donde nadie lo dijo |

## Pruebas

- **Sin audio** (`jetson/robot/prueba_vision_texto.py`, sin cámara ni red): reglas de la cámara 21 de 21, borrado de memoria 10 de 10, detección del nombre 11 de 11, filtro de ruido 14 de 14, y recorte de respuestas. Con `--real` toma fotos de verdad.
- **Hablando:** la cámara se comprobó contando fotos: el servidor del Mac registró exactamente tantas fotos como peticiones de ver (5 y 5, después 2 y 2), y los intentos bloqueados no generaron ninguna.
- **No comprobado:** que el filtro del nombre ignore de verdad lo que se dice fuera de la ventana de conversación. En la prueba, todas las frases llegaron dentro de la ventana y el filtro nunca llegó a actuar.

## Privacidad

- **Qué sale a internet:** la imagen de cada foto (a Mistral), el texto de la conversación y de los recuerdos, el texto de cada respuesta (para la voz) y, con Voxtral, el audio de las frases detectadas. Con el filtro del nombre, el audio que no es para el robot se queda en el Jetson (Vosk, local).
- **Otras personas.** El micrófono recoge la voz de quien esté cerca y la cámara lo que haya delante. Antes del filtro del nombre, esas voces se enviaban a Voxtral, y las fotos incluyen a quien salga al fondo. Conviene **avisar a quienes viven en la casa** y encuadrar la cámara.
- Las fotos de prueba no se suben nunca (`.gitignore`) y se borran. Los recuerdos y la clave de Mistral viven solo en el Jetson.
- No se ha revisado la política de conservación de datos de Mistral.

## Límites

- La cámara actual es de baja calidad; cambia detalles del entorno (respaldo de silla, ropa de cama) por otras cosas.
- Las reglas de la cámara y del nombre son por palabras: una petición con otra redacción puede no activarse.
- El modelo de conversación casi nunca guarda un recuerdo por iniciativa propia; depende del control que lo obliga.
