# Hardware y hallazgos

Todo lo de esta página viene de pruebas sobre **una** placa. Cuando algo es una deducción y no una medida, se dice.

## Placa

- Serie **R800** (© 2015 iRobot), MCU **STM32F103ZET6** (Cortex-M3, 72 MHz, LQFP144).
- Firmware leído por serie: `release-stm32-3.7.1`, compilado el 2015-12-18; ensamblado 3.2, revisión 8, battery-current-zero 251.
- Alimentación en las pruebas: adaptador de **12 V / 1,25 A** por los contactos grandes del óvalo donde apoya la batería. Los pads VBAT/GND de la placa **no** tienen continuidad con la entrada de batería.
- Tensión medida con 12 V: unos 12,2 V por el paquete 22 y 11,82 V en los pines 1-2 del mini-DIN.

## Conector OI (mini-DIN de 7 pines)

| Pin | Señal | Notas |
|---|---|---|
| 1, 2 | Vpwr | Tensión de batería/alimentación. **No conectar al ESP32.** |
| 3 | RXD (entrada al Roomba) | Desde TX del ESP32. |
| 4 | TXD (salida del Roomba) | 3,3 V en reposo. Al RX del ESP32 con 1 kΩ en serie. |
| 5 | BRC | Entrada de 5 V del Roomba. Solo se baja a 0 desde el ESP32. |
| 6, 7 | GND | |

115200 baudios, 8N1.

### BRC y el sueño del robot

En Passive, el Roomba se duerme tras unos minutos. Dormido **ignora `Start`** y no manda nada. Despertarlo requiere un pulso bajo de unos 100 ms por BRC (pin 5) o pulsar un botón. Al principio mi cableado no tenía GPIO4 conectado a BRC, y por eso el stream no arrancaba si el robot estaba dormido: con BRC cableado, `wake()` lo despierta (comprobado). En Safe/Full no se duerme.

## Batería y termistor

- Batería original NiMH 14,4 V / 2200 mAh (12 celdas), estaba a 0,5 V; no se usa.
- Los dos contactos pequeños junto a los grandes son el **termistor de la batería**. El de mi batería medía **9,15 kΩ** a temperatura ambiente, compatible con un NTC de 10 kΩ (suposición: no he comprobado el tipo).
- Sin nada en esos contactos, el paquete 24 da **−19 °C** (entrada abierta). Con una **resistencia de 10 kΩ** puesta en su lugar da **24-25 °C**.
- No he comprobado si la placa necesita ver el termistor para cargar.

## Botones (paquete 18)

Este modelo solo tiene **tres** botones. Bits del paquete 18:

| Bit | Botón |
|---|---|
| 0 | Clean |
| 1 | Spot |
| 2 | Dock |

Los bits 3-7 (Minute, Hour, Day, Schedule, Clock) son de otros modelos y aquí no se usan. Los tres botones táctiles de la placa están serigrafiados S3/SW3, SW1 y S2/SW2; no he anotado cuál es cuál.

## Módulos de rueda

- Cada módulo de rueda se **enchufa directamente a la placa** por una pestaña con contactos de borde, sin cables. Los zócalos son **J17 y J20** (cara inferior). Es una deducción de las fotos, aunque funciona.
- Con los dos módulos enchufados:
  - Los interruptores de **rueda caída** responden: bit 2 (derecha) y bit 3 (izquierda) del paquete 7 bajan a 0 al empujar la rueda hacia dentro.
  - **Drive Direct (145)** mueve cada rueda: velocidad positiva = hacia delante, y el orden de argumentos es *derecha, izquierda*.
  - Los **encoders** (paquetes 43 izquierda y 44 derecha) cuentan y salen positivos hacia delante. A 100 mm/s durante ~1,1 s con las ruedas libres dieron +256 y +290 cuentas. Teóricamente (508,8 cuentas/vuelta, rueda de 72 mm) serían ~225 por segundo; la diferencia no la he analizado.
- Con el adaptador de 1,25 A no se reinició la placa con las dos ruedas libres. Con ruedas bloqueadas no lo he probado.

## Cepillos

Los motores de los dos cepillos giran con **PWM Motors (144)**. Se probó a 40/127 (~31 %) en vacío. No he documentado a qué zócalo va cada uno.

## Parachoques y acantilados

- **Parachoques:** derecho = bit 0 del paquete 7, izquierdo = bit 1. Ambos responden.
- **Acantilados:** los cuatro sensores responden (paquetes 9-12 digitales, 28-31 analógicos de 0 a 4095).
  - Señal analógica **alta** (~2500) con superficie cerca, **baja** (decenas a cientos) con el sensor lejos o tapado.
  - El digital pasa a **1 (vacío)** cuando la señal baja de un umbral. Los umbrales parecen distintos por sensor (muestras: ~80 en el izquierdo, ~165 en el derecho). Son valores orientativos.
  - Al apretar el parachoques derecho, el acantilado frontal derecho también cambió: probablemente va montado en el parachoques.

## Sensor IR omnidireccional

Cable de 3 hilos (rojo, negro, blanco) enchufado a **J7**. **Sin probar**: no tengo mando ni base de carga, y el robot solo decodifica códigos propios de iRobot (paquetes 17, 52 y 53). Un mando de TV no sirve.

## STM32: no se reprograma

Se valoró sustituir el firmware del STM32F103ZET6 para un robot propio, y se descartó.

- **J18** es una huella de **2×4 pines sin soldar** con tres matrices de diodos de protección debajo. No sé si es SWD. Con el ST-Link V2 y el OpenOCD que trae el core esp32 de Arduino se podría leer el estado de la protección, pero no se llegó a conectar.
- Medí continuidad entre el pin que identifiqué como 105 del chip (PA13/SWDIO, confirmado en el datasheet de ST) y J18: **no había**. No confirmé la posición del pin 109 (SWCLK) ni la del pin 1 del chip; identifiqué el pin 1 por la posición de los cristales, no por una marca oficial.
- Si el chip tuviera protección de lectura, quitarla borraría el firmware original y no habría forma de recuperarlo.

Con el ESP32 y el OI ya se consiguen ruedas, cepillos y sensores con WiFi/Bluetooth, así que la vía de reflashear no se necesita.

## Cosas sin documentar

- Pinout de los conectores internos J3-J22 (salvo los zócalos J17/J20 de las ruedas).
- Si el cargador original da ~20 V (no verificado). Con 12 V la batería no se puede cargar a tope.
