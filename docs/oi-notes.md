# Notas del Open Interface (Roomba 600)

Resumen de cómo se comporta el OI en esta placa, más lo que usa la librería. Los códigos vienen de la especificación OI de Create 2 / Roomba 600 (julio 2018), que no se incluye en el repositorio.

## Modos

`Off → Start → Passive → Safe / Full`.

- **Passive** se duerme a los ~5 min; dormido ignora `Start`. Hay que despertarlo por BRC.
- **Safe y Full** no se duermen, pero descargan la batería.
- **Safe** vuelve solo a Passive si hay rueda caída o acantilado activo. Con sensores sin conectar, o con ruedas colgando en la mesa de pruebas, Safe **no se mantiene**; Full sí.
- **Full** ignora ruedas caídas y acantilados. Úsalo con cuidado.
- Song, Play, LEDs y movimiento requieren Safe o Full.
- Los LEDs de dígitos solo existen en 560/570, no en este modelo.

## Opcodes usados

| Código | Comando |
|---|---|
| 7 | Reset |
| 128 | Start |
| 131 / 132 | Safe / Full |
| 137 | Drive |
| 139 | LEDs |
| 140 / 141 | Song / Play |
| 144 | PWM Motors (cepillo principal, lateral, aspiración) |
| 145 | Drive Direct (derecha, izquierda) |
| 148 | Stream |
| 149 | Query List |
| 150 | Pause/Resume Stream |
| 173 | Stop |

## Paquetes de sensor usados

| Paquete | Qué es | Bytes |
|---|---|---|
| 7 | Bumps y ruedas caídas | 1 |
| 9-12 | Acantilados digitales (izq, frontal izq, frontal der, der) | 1 c/u |
| 13 | Virtual wall | 1 |
| 18 | Botones | 1 |
| 21 | Estado de carga | 1 |
| 22 | Tensión (mV) | 2 |
| 24 | Temperatura de la batería (°C, con signo) | 1 |
| 28-31 | Señal de acantilados (0-4095) | 2 c/u |
| 35 | Modo OI (0 Off, 1 Passive, 2 Safe, 3 Full) | 1 |
| 43 / 44 | Encoder izquierdo / derecho (int16 con desbordamiento) | 2 c/u |

Bits del paquete 7: 0 bump derecho, 1 bump izquierdo, 2 rueda caída derecha, 3 rueda caída izquierda. En los acantilados digitales, **1 = vacío**.

## Stream

Se pide con `148, n, id1, id2, …`. Cada 15 ms llega una trama:

```
19, N, [id, datos…] × paquetes, checksum
```

`N` es el número de bytes entre `N` y el checksum. La suma de **todos** los bytes de la trama (incluidos `19`, `N` y el checksum) es 0 módulo 256. La librería descarta las tramas con checksum erróneo o con un id desconocido.

Con 115200 baudios entran como mucho unos 170 bytes cada 15 ms. Las tramas de los ejemplos (6 a 11 paquetes) caben de sobra. La librería sube el búfer de recepción del ESP32 a 1024 bytes.

No mezcles `startStream()` y `querySensors()`: las respuestas se confunden.

## Cosas aprendidas

- Si el stream muestra texto ASCII en lugar de datos (por ejemplo `Soft reset!`), el robot está arrancando o reiniciándose y hay que esperar o reenviar `Start`.
- **Despertar al arrancar:** el ESP32 debe mandar el pulso BRC antes de `Start`. Si no llegan tramas, los ejemplos repiten el despertar cada 3 s.
- **Órdenes de movimiento tardías:** desde el móvil, un `/drive` en vuelo puede llegar tras el `/stop` y volver a mover las ruedas hasta que salta el tiempo de seguridad. `WebControl` descarta 300 ms de órdenes tras un stop. Es el arreglo aplicado; no he confirmado que sea la única causa del movimiento residual.
