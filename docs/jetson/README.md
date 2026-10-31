# Etapa 2: Jetson + base Roomba

Objetivo: un robot completo en el que un **NVIDIA Jetson** haga de cerebro y la **base del Roomba** (con el ESP32 y la librería [`RoombaOI`](../../RoombaOI/)) haga de cuerpo, para que pueda **moverse solo**.

Esta carpeta documenta solo la parte del Jetson. El hardware del Roomba está en [../hardware.md](../hardware.md).

> Estado: en preparación. Aún no está instalado nada en el Jetson. Lo que se afirma sobre versiones de software viene de búsquedas en foros y documentación de NVIDIA, no de haberlo probado en esta placa; las fuentes se citan donde corresponde.

## Arquitectura propuesta

```
 Jetson  ──USB serie──►  ESP32  ──UART OI──►  Roomba (STM32 original)
 (decide)               (puente + seguridad)   (ruedas, cepillos, sensores)
```

- **El Jetson decide**: percepción, mapa y planificación. Manda órdenes de velocidad.
- **El ESP32 es el puente**: traduce esas órdenes al OI con la librería que ya funciona, devuelve sensores y encoders, y mantiene la **parada de seguridad** (sin órdenes en 400 ms, ruedas paradas) aunque Linux se cuelgue.
- **El Roomba** sigue con su firmware original.

Por qué el ESP32 en medio, y no el Jetson hablando directamente con el OI:
- Ya está probado: modos, drive, stream con checksum, despertar por BRC.
- Aísla los 3,3 V del OI y el robot no depende de que Linux responda a tiempo para pararse. Un Jetson con Linux no es de tiempo real.
- Se puede cambiar más adelante si se quiere simplificar. El puerto UART del Jetson (J41) también habla 3,3 V, pero no está probado con el Roomba.

## Fases

| Fase | Qué | Estado |
|---|---|---|
| 0 | Identificar el modelo de Jetson y reunir lo necesario | hecho: Jetson Nano Developer Kit (P3450) |
| 1 | Instalar el sistema, primer arranque, actualizar, acceso remoto por SSH | en curso, ver [01-instalacion.md](01-instalacion.md) |
| 1b | El robot conversa y razona (escuchar, Mistral, hablar) | hecho, ver [02-conversacion.md](02-conversacion.md) |
| 1c | El robot ve (cámara, visión) y tiene candados de privacidad | hecho; el filtro del nombre aún sin probar a fondo, ver [03-vision-y-seguridad.md](03-vision-y-seguridad.md) |
| 2 | Conectar el Jetson con el ESP32 (USB serie) y un protocolo de órdenes con parada de seguridad | pendiente |
| 3 | Software de movimiento autónomo, empezando sin sensores nuevos (encoders, parachoques, acantilados) | pendiente |
| 4 | Sensores nuevos (cámara o LiDAR), cuando se decidan | pendiente |
| 5 | Integración mecánica y alimentación del conjunto | pendiente |

## Modelo identificado

La etiqueta de la placa dice **Model P3450**, referencia `945-13450-0000-000` (placa portadora `180-13449-DARF-A02`). Es el **Jetson Nano Developer Kit original**. Por el conector de corriente cilíndrico y los puertos USB parece la versión de **4 GB**, y por un solo conector de cámara la revisión **A02**; son deducciones mías de las fotos y no cambian el proceso de instalación.

Consecuencia: **JetPack 4.6.x, Ubuntu 18.04**, con tarjeta microSD. Ver [01-instalacion.md](01-instalacion.md).

## Fase 0 (referencia): qué modelo tienes

El proceso de instalación depende mucho del modelo.

**Jetson Nano original (2019), 4 GB o 2 GB**
- Acaba en **JetPack 4.6.x con Ubuntu 18.04**. Según NVIDIA en sus foros, JetPack 4.6 fue la última versión mayor para el Nano, y JetPack 5.x y 6.x no lo soportan ([foro NVIDIA](https://forums.developer.nvidia.com/t/jetpack-4-6-3-l4t-32-7-3-released/235952)).
- Tiene **ranura microSD** (no lleva almacenamiento propio).
- ROS 2 Humble no se pudo compilar en él según informes de la comunidad. Foxy sí funciona dentro de un contenedor de [`jetson-containers`](https://github.com/dusty-nv/jetson-containers) ([foro NVIDIA](https://forums.developer.nvidia.com/t/ros2-humble-desktop-for-jetson-nano/236942)).

**Jetson Orin Nano Developer Kit (2023 en adelante)**
- JetPack 6.x con Ubuntu 22.04. Según la guía de NVIDIA, de fábrica trae un firmware que hay que actualizar antes de usar la imagen de JetPack 6 ([guía de inicio de NVIDIA](https://developer.nvidia.com/embedded/learn/get-started-jetson-orin-nano-devkit)).
- Es una plataforma mucho más actual, también para ROS 2.

**Cómo distinguirlos** (suposición mía a confirmar con la caja o la etiqueta):
- Mira la caja y la etiqueta de la placa: debe poner **"Jetson Nano"** o **"Jetson Orin Nano"**.
- El Nano original 4 GB suele tener un disipador de aluminio grande sin ventilador, un conector de corriente cilíndrico y cuatro puertos USB. El de 2 GB se alimenta por USB-C y tiene menos puertos.
- El Orin Nano trae el disipador con ventilador y su propia fuente de alimentación.

## Qué necesitarás para el primer arranque

- Monitor con HDMI o DisplayPort, teclado y ratón.
- **Tarjeta microSD** de buena calidad y espacio de sobra (a partir de 32 GB, mejor 64 GB) si es un Nano original. Confírmalo en la guía de NVIDIA de tu modelo.
- **Fuente de alimentación adecuada**. El Jetson consume bastante más que un ESP32. Con una fuente justa se reinicia o se limita; mira la guía de tu modelo.
- Un Mac o PC para preparar la tarjeta (balenaEtcher o similar).
- Un cable USB para el ESP32.

## Siguientes pasos

1. Identificar el modelo.
2. Seguir la guía de instalación del modelo concreto (se añadirá aquí).
