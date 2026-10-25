# RoombaOI

Librería de Arduino para **ESP32** que habla con el Open Interface de un Roomba serie 600. Versión 0.1.0, sin versión estable: la API puede cambiar.

Los códigos y longitudes de paquete son los de la especificación OI de Create 2 / Roomba 600. Se ha probado solo en un Roomba 616 (placa R800) con el core esp32 3.3.12.

## Instalación

Copia o enlaza esta carpeta en tu carpeta de librerías de Arduino:

```bash
ln -s "$(pwd)" ~/Documents/Arduino/libraries/RoombaOI
```

## API

### Inicio

| Función | Descripción |
|---|---|
| `begin(port, rxPin, txPin, brcPin = -1, baud = 115200)` | Abre el puerto serie y sube el búfer de recepción a 1024 bytes. |
| `wake()` | Pulso bajo de 100 ms en BRC. BRC solo se baja, nunca se sube. |

### Modos

`start()`, `safe()`, `full()`, `stop()`, `reset()` y `mode()`. El modo que devuelve es el último comandado o, si el paquete 35 va en el stream, el que informa el robot.

### Actuadores

| Función | Descripción |
|---|---|
| `driveDirect(right, left)` | Velocidad de cada rueda en mm/s. |
| `drive(velocity, radius)` | Con constantes `RADIUS_STRAIGHT`, `RADIUS_SPIN_CCW` y `RADIUS_SPIN_CW`. |
| `stopMotors()` | Drive Direct a 0. |
| `setBrushes(main, side, vacuum = 0)` | PWM de los cepillos y la aspiración. |
| `setLeds(bits, color, intensity)` | LEDs de estado y de potencia. |
| `playNote(note, duration64ths)` | Define la canción 0 con una nota y la toca. Bloquea unos 50 ms. |

### Sensores

- `querySensors(ids, n, out, outLen, timeoutMs)`: lectura puntual bloqueante, con los datos concatenados en el orden pedido.
- `startStream(ids, n)` y `pauseStream(bool)`: stream cada 15 ms.
- `update()`: llamar en `loop()`. Procesa los bytes sin bloquear y valida el checksum.
- `getU8`, `getS8`, `getU16`, `getS16`: último valor recibido de un paquete. Devuelven `false` si no hay dato o la longitud no coincide.
- `takeNewFrame()`: `true` una vez por cada trama nueva.
- `lastFrameAgeMs()`, `framesOk()`, `framesBad()`, `rxBytes()`: diagnóstico.
- `packetLength(id)`: bytes de un paquete (0 si no está soportado). Los paquetes 0-6 (grupos) no están soportados.

No mezcles `startStream()` y `querySensors()` a la vez.

## Ejemplos

- [`SensorStream`](examples/SensorStream/SensorStream.ino): imprime modo, bumps, botones, tensión, temperatura y encoders.
- [`WebControl`](examples/WebControl/WebControl.ino): el ESP32 crea la red `Roomba-ESP32` y sirve una página con cuatro flechas y un control de velocidad. Las ruedas se paran al soltar o al pasar 400 ms sin órdenes. Cambia la clave por defecto.

## Limitaciones conocidas

- Solo ESP32 (usa `HardwareSerial::setRxBufferSize`).
- Sin reconexión automática dentro de la librería: los ejemplos reintentan el despertar si el stream se corta.
- No gestiona la carga de la batería ni las canciones múltiples.
