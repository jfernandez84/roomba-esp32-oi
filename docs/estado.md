# Estado del proyecto

Última actualización: 2026-10-25.

## Hecho y comprobado en la placa

- [x] Comunicación OI: Start, Reset, Safe, Full, Stop, lectura de tensión y sensores.
- [x] Termistor: lectura de temperatura razonable con una resistencia de 10 kΩ.
- [x] Botones: Clean, Spot y Dock.
- [x] Ruedas caídas, parachoques y los 4 sensores de acantilado.
- [x] Motores de las dos ruedas (Drive Direct) y sus encoders.
- [x] Motores de los dos cepillos (PWM Motors).
- [x] Librería `RoombaOI` con stream y checksum (0 tramas erróneas en las pruebas).
- [x] Despertar por BRC con GPIO4 cableado.
- [x] Control web por WiFi (AP propio), con parada de seguridad.

## Pendiente o sin probar

- [ ] Confirmar que el movimiento residual tras soltar el botón del control web desaparece con el último arreglo.
- [ ] Sensor IR omnidireccional (J7): sin mando ni base para probarlo.
- [ ] Carga de la batería: sin probar. Solo se probaría con vigilancia.
- [ ] Altavoz externo y aspiración.
- [ ] Mapa de los conectores internos J3-J22.
- [ ] Probar Safe con la base montada y sensores en su sitio.
- [ ] Calibrar encoders (cuentas por vuelta reales).
- [ ] Bluetooth como alternativa al WiFi.

## Descartado

- Reprogramar el STM32F103ZET6. Ver [hardware.md](hardware.md#stm32-no-se-reprograma).

## Ideas

- Odometría con los encoders y control de velocidad desde el ESP32.
- Parada automática por bump o acantilado en el control web.
- Mando por serie o por Bluetooth además del web.
