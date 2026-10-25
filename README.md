# Roomba 616 + ESP32

Reutilizar la **placa principal de un Roomba 616** (serie R800, STM32F103ZET6) como base móvil, controlada desde un **ESP32** por el puerto **Open Interface (OI)**. Se mantiene el firmware original de iRobot: el ESP32 solo le habla por serie, sin tocar el STM32.

> Proyecto de aficionado, en marcha. Todo lo que aquí se afirma sobre el hardware sale de pruebas sobre **una** placa; lo que no se ha comprobado está marcado como tal. Úsalo bajo tu responsabilidad (ver [Seguridad](#seguridad)).

## Qué hay

| Carpeta | Contenido |
|---|---|
| [`RoombaOI/`](RoombaOI/) | Librería de Arduino para ESP32: modos, movimiento, cepillos, LEDs, lectura de sensores y stream con checksum. |
| [`RoombaOI/examples/SensorStream`](RoombaOI/examples/SensorStream/SensorStream.ino) | Imprime por serie los sensores leídos por stream. No mueve nada. |
| [`RoombaOI/examples/WebControl`](RoombaOI/examples/WebControl/WebControl.ino) | Control desde el móvil por WiFi (el ESP32 crea su propia red). |
| [`roomba_test/`](roomba_test/roomba_test.ino) | Sketch de pruebas por monitor serie, usado para descubrir cómo responde el hardware. |
| [`docs/`](docs/) | [Hardware y hallazgos](docs/hardware.md), [notas del OI](docs/oi-notes.md) y [estado del proyecto](docs/estado.md). |

## Estado

Comprobado en mi placa:

- Comunicación OI (Start, Reset, Safe/Full, sensores, stream con checksum).
- Motores de **las dos ruedas** y sus **encoders**.
- Motores de los **dos cepillos** (PWM).
- **Parachoques**, **4 sensores de acantilado**, **ruedas caídas**, **3 botones**, **termistor** (con una resistencia, ver docs).
- Control por **WiFi** desde el móvil con parada de seguridad.

Sin probar o pendiente: sensor IR omnidireccional (sin mando ni base), carga de la batería, altavoz externo, aspiración. Más detalle en [docs/estado.md](docs/estado.md).

## Cableado mínimo ESP32 ↔ mini-DIN del Roomba

| Mini-DIN | Señal | ESP32 |
|---|---|---|
| 1 y 2 | Vpwr (~12 V o más) | **No conectar nunca** |
| 3 | RXD del Roomba | GPIO17 (TX2) |
| 4 | TXD del Roomba (3,3 V) | 1 kΩ en serie → GPIO16 (RX2) |
| 5 | BRC | 1 kΩ → GPIO4 (solo se baja a 0, nunca se sube) |
| 6 o 7 | GND | GND |

- 115200 baudios, 8N1, sin control de flujo.
- La salida TXD del Roomba ya es de 3,3 V: **no** hace falta divisor de tensión.
- **BRC es necesario** para despertar el robot: si se duerme (Passive tras unos minutos), ignora `Start` hasta que se le da un pulso bajo por BRC o se pulsa un botón.
- Alimentación usada en las pruebas: adaptador de 12 V / 1,25 A por los contactos grandes de la batería (no por los pads VBAT/GND de la placa). Detalles en [docs/hardware.md](docs/hardware.md).

## Primeros pasos

Necesitas el IDE de Arduino (o `arduino-cli`) con el core **esp32** instalado (probado con 3.3.12).

1. Enlaza o copia la librería a tu carpeta de librerías:
   ```bash
   ln -s "$(pwd)/RoombaOI" ~/Documents/Arduino/libraries/RoombaOI
   ```
2. Abre `RoombaOI/examples/SensorStream` y súbelo a un **ESP32 Dev Module**. En el monitor serie (115200) deberías ver una línea cada 0,5 s con `ok` creciendo y `mal=0`.
3. Para el control web, sube `WebControl`, conecta el móvil a la red `Roomba-ESP32` (clave `roomba1234`, **cámbiala**) y abre `http://192.168.4.1`.

Con `arduino-cli`:

```bash
arduino-cli compile --upload -p /dev/cu.usbserial-XXXX \
  --fqbn esp32:esp32:esp32:UploadSpeed=115200 \
  --library RoombaOI RoombaOI/examples/WebControl
```

Notas de subida (macOS):
- A 921600 baudios la subida me falló; con `UploadSpeed=115200` va bien.
- El monitor serie del IDE bloquea el puerto: ciérralo antes de subir.

## Uso de la librería

```cpp
#include <RoombaOI.h>

HardwareSerial port(2);
RoombaOI roomba;

void setup() {
  roomba.begin(port, /*rx*/16, /*tx*/17, /*brc*/4);
  delay(500);
  roomba.wake();            // pulso BRC: despierta si estaba dormido
  delay(200);
  roomba.start();           // Passive
  roomba.full();            // o roomba.safe()
  const uint8_t ids[] = {7, 22, 24, 35, 43, 44};
  roomba.startStream(ids, sizeof(ids));
}

void loop() {
  roomba.update();          // procesa el stream sin bloquear
  uint16_t mv;
  if (roomba.getU16(22, mv)) { /* tensión de batería en mV */ }
  roomba.driveDirect(100, 100);   // derecha, izquierda, mm/s
}
```

Referencia de la API en [RoombaOI/README.md](RoombaOI/README.md).

## Seguridad

- **Nunca** conectes los pines 1 y 2 del mini-DIN (Vpwr) ni los 12 V a ningún pin del ESP32.
- Prueba los motores con las ruedas **en el aire** y el cuerpo sujeto; un motor bloqueado puede pedir más corriente de la que da un adaptador pequeño.
- En **Full** el robot ignora ruedas caídas y acantilados: no lo dejes en una mesa sin vigilar. El ejemplo web tiene parada a los 400 ms sin órdenes y limita la velocidad a 200 mm/s.
- No dejes cargando una batería NiMH sin vigilar y no cortocircuites sus contactos. La carga **no** está probada en este proyecto.

## Documentación de iRobot

La especificación del OI (Roomba 600 / Create 2) es de iRobot y **no se incluye** aquí. Se puede descargar de la web de iRobot buscando "Roomba 600 Open Interface Spec". Las longitudes de paquete de la librería siguen esa especificación según mi conocimiento de la misma, pero no las he cotejado línea a línea con el PDF.

## Licencia

[MIT](LICENSE). "Roomba" e "iRobot" son marcas de iRobot Corporation; este proyecto no está afiliado a ella.
