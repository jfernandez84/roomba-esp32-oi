// Prueba serie del Roomba (Open Interface) con ESP32. No mueve ruedas ni cepillos.
//
// Conexiones (TXD del Roomba medido en reposo: 3,3 V, igual que el ESP32):
//   Roomba pin 4 (TXD)  -> 1k en serie -> GPIO16 (RX2)   [sin divisor: la salida ya es de 3,3 V]
//   Roomba pin 3 (RXD)  <- GPIO17 (TX2)
//   Roomba pin 6 o 7 (GND) -> GND del ESP32
//   Roomba pin 5 (BRC)  <- GPIO4 (opcional, solo se usa para despertar)
//   NO conectes los pines 1 y 2 (Vpwr, ~14 V) a ningun pin del ESP32.
//
// Abre el monitor serie a 115200 y envia una letra:
//   s = Start (128)       -> el robot debe pitar una vez
//   r = Reset (7)         -> imprime el mensaje de arranque con la version de firmware
//   v = tension de bateria (paquete 22, en mV)
//   p = lee varios sensores a la vez (Query List 149: paquetes 7, 9-13, 18, 21, 22, 24)
//   l = alterna los LEDs (139): todos encendidos / apagados (necesita Safe o Full)
//   1 / 2 / 3 = pulso de 1 s a 100 mm/s: rueda izquierda / derecha / ambas (necesita Full)
//   4 / 5 = pulso de 1 s al ~31 % de PWM: cepillo principal / lateral (necesita Full)
//   e = pulso de 1 s con ambas ruedas y cuentas de encoder antes/despues (paquetes 43 y 44)
//   i = vigila 15 s los sensores IR (paquetes 17, 52, 53) e imprime los cambios
//   c = senal analogica de los 4 acantilados (paquetes 28-31, 0-4095), 20 s a 4 lecturas/s
//   z = parada de ruedas (Drive Direct 0,0)
//   a = Safe (131)        f = Full (132)
//   b = define y reproduce una nota corta (necesita Safe o Full)
//   w = pulso bajo en BRC para despertar
//   x = Stop (173)

#include <HardwareSerial.h>

HardwareSerial Roomba(2);

const int RX_PIN  = 16;  // desde TXD del Roomba (via 1k en serie)
const int TX_PIN  = 17;  // hacia RXD del Roomba
const int BRC_PIN = 4;   // hacia BRC (pin 5)

void dump(unsigned long ms) {
  unsigned long t0 = millis();
  while (millis() - t0 < ms) {
    while (Roomba.available()) {
      char c = Roomba.read();
      Serial.write(c);
    }
  }
  Serial.println();
}

void sendByte(uint8_t b) {
  Roomba.write(b);
}

void wakePulse() {
  // BRC es una entrada de 5 V del Roomba: solo la bajamos, nunca la subimos.
  pinMode(BRC_PIN, OUTPUT);
  digitalWrite(BRC_PIN, LOW);
  delay(100);
  pinMode(BRC_PIN, INPUT);
  Serial.println("Pulso BRC enviado");
}

void readVoltage() {
  while (Roomba.available()) Roomba.read();  // vaciar buffer
  sendByte(142);  // Sensors
  sendByte(22);   // paquete 22: tension en mV
  unsigned long t0 = millis();
  while (Roomba.available() < 2 && millis() - t0 < 500) {}
  if (Roomba.available() >= 2) {
    uint8_t hi = Roomba.read();
    uint8_t lo = Roomba.read();
    uint16_t mv = (hi << 8) | lo;
    Serial.printf("Tension: %u mV\n", mv);
  } else {
    Serial.println("Sin respuesta (envia 's' primero, o 'f' si el robot ha vuelto a dormir; revisa el cableado)");
  }
}

// Query List (149) con los paquetes 7, 9, 10, 11, 12, 13, 18, 21, 22, 24.
// Respuesta: 1+1+1+1+1+1+1+1+2+1 = 11 bytes, en el mismo orden que la peticion.
void readSensors() {
  const uint8_t pkts[] = {7, 9, 10, 11, 12, 13, 18, 21, 22, 24};
  const size_t RESP_LEN = 11;

  while (Roomba.available()) Roomba.read();
  sendByte(149);
  sendByte(sizeof(pkts));
  Roomba.write(pkts, sizeof(pkts));

  uint8_t r[RESP_LEN];
  size_t n = 0;
  unsigned long t0 = millis();
  while (n < RESP_LEN && millis() - t0 < 500) {
    if (Roomba.available()) r[n++] = Roomba.read();
  }
  if (n < RESP_LEN) {
    Serial.printf("Respuesta incompleta (%u de %u bytes). Envia 's' o 'f' primero.\n",
                  (unsigned)n, (unsigned)RESP_LEN);
    return;
  }

  // Si todos los bytes son ASCII imprimible no son sensores sino texto del robot
  // (p. ej. "Soft reset!"). El paquete 7 real nunca pasa de 0x0F, asi que no hay falsos positivos.
  bool text = true;
  for (size_t i = 0; i < RESP_LEN; i++) {
    if (r[i] < 32 || r[i] > 126) { text = false; break; }
  }
  if (text) {
    Serial.print("El robot ha respondido con texto, no con sensores: \"");
    Serial.write(r, RESP_LEN);
    Serial.println("\"\nEnvia 's' y 'f' y vuelve a probar.");
    return;
  }

  // Paquete 7: bit0 bump der, bit1 bump izq, bit2 rueda der caida, bit3 rueda izq caida
  Serial.printf("[7]  bumps/ruedas: 0x%02X  (bump D=%d I=%d, rueda caida D=%d I=%d)\n",
                r[0], r[0] & 1, (r[0] >> 1) & 1, (r[0] >> 2) & 1, (r[0] >> 3) & 1);
  Serial.printf("[9]  acantilado izq:      %u\n", r[1]);
  Serial.printf("[10] acantilado frontal izq: %u\n", r[2]);
  Serial.printf("[11] acantilado frontal der: %u\n", r[3]);
  Serial.printf("[12] acantilado der:      %u\n", r[4]);
  Serial.printf("[13] virtual wall:        %u\n", r[5]);
  // Paquete 18: bit0 Clean, bit1 Spot, bit2 Dock (este modelo solo tiene estos tres botones;
  // los bits 3-7 son Minute, Hour, Day, Schedule y Clock, de otros modelos)
  Serial.printf("[18] botones:             0x%02X  (Clean=%d Spot=%d Dock=%d)\n",
                r[6], r[6] & 1, (r[6] >> 1) & 1, (r[6] >> 2) & 1);
  Serial.printf("[21] estado de carga:     %u  (0 no carga,1 reacond.,2 plena,3 lenta,4 mantenim.,5 fallo)\n", r[7]);
  Serial.printf("[22] tension:             %u mV\n", (r[8] << 8) | r[9]);
  Serial.printf("[24] temp. bateria:       %d C\n", (int8_t)r[10]);
}

// Drive Direct (145): velocidad de cada rueda en mm/s (int16, big endian). Orden: derecha, izquierda.
void driveDirect(int16_t right, int16_t left) {
  uint8_t cmd[] = {145, (uint8_t)(right >> 8), (uint8_t)right, (uint8_t)(left >> 8), (uint8_t)left};
  Roomba.write(cmd, sizeof(cmd));
}

// Pulso corto y parada. Necesita Full (en Safe, con ruedas caidas/acantilados activos, el robot se para).
void drivePulse(int16_t right, int16_t left, unsigned long ms) {
  Serial.printf("Pulso: derecha=%d izquierda=%d mm/s durante %lu ms\n", right, left, ms);
  driveDirect(right, left);
  delay(ms);
  driveDirect(0, 0);
  Serial.println("Parado");
}

// Encoders (paquetes 43 izquierda y 44 derecha): int16 con signo que se desborda; las diferencias
// restadas como int16 salen bien aunque haya vuelta.
bool readEncoders(int16_t &left, int16_t &right) {
  while (Roomba.available()) Roomba.read();
  uint8_t cmd[] = {149, 2, 43, 44};
  Roomba.write(cmd, sizeof(cmd));
  uint8_t r[4];
  size_t n = 0;
  unsigned long t0 = millis();
  while (n < 4 && millis() - t0 < 500) {
    if (Roomba.available()) r[n++] = Roomba.read();
  }
  if (n < 4) return false;
  left  = (int16_t)((r[0] << 8) | r[1]);
  right = (int16_t)((r[2] << 8) | r[3]);
  return true;
}

// Pulso con ambas ruedas y cuentas de encoder antes/despues.
// A 100 mm/s durante 1 s se esperan unas 225 cuentas (508,8 cuentas/vuelta, rueda de 72 mm).
void encoderTest() {
  int16_t l0, r0, l1, r1;
  if (!readEncoders(l0, r0)) { Serial.println("Sin respuesta de encoders (envia 's' y 'f' primero)"); return; }
  drivePulse(100, 100, 1000);
  delay(100);  // dejar que las ruedas terminen de frenar
  if (!readEncoders(l1, r1)) { Serial.println("Sin respuesta de encoders tras el pulso"); return; }
  Serial.printf("Encoders: izquierda %d -> %d (delta %d), derecha %d -> %d (delta %d)\n",
                l0, l1, (int16_t)(l1 - l0), r0, r1, (int16_t)(r1 - r0));
}

// PWM Motors (144): cepillo principal (-127..127), lateral (-127..127), aspiracion (0..127).
// Pulso corto y parada. 40/127 son unos 31 % de la tension de alimentacion.
void brushPulse(int8_t mainPwm, int8_t sidePwm, unsigned long ms) {
  Serial.printf("Cepillos: principal=%d lateral=%d durante %lu ms\n", mainPwm, sidePwm, ms);
  uint8_t cmd[] = {144, (uint8_t)mainPwm, (uint8_t)sidePwm, 0};
  Roomba.write(cmd, sizeof(cmd));
  delay(ms);
  uint8_t stop[] = {144, 0, 0, 0};
  Roomba.write(stop, sizeof(stop));
  Serial.println("Parado");
}

// Senal analogica de los acantilados (paquetes 28-31, uint16 0-4095): izq, frontal izq, frontal der, der.
// Un sensor que ve suelo y uno que ve vacio dan valores muy distintos; uno desconectado suele dar 0 o 4095.
// Se repite 4 veces por segundo durante 20 s para poder mover los sensores a mano sin teclear.
void readCliffSignals() {
  // Senal (28-31, 2 bytes cada uno) y digital (9-12, 1 byte cada uno): 8 + 4 = 12 bytes.
  const uint8_t cmd[] = {149, 8, 28, 29, 30, 31, 9, 10, 11, 12};
  Serial.println("Acantilados 20 s (4 lecturas/s): senal y [digital 1=vacio]");
  unsigned long t0 = millis();
  while (millis() - t0 < 20000) {
    while (Roomba.available()) Roomba.read();
    Roomba.write(cmd, sizeof(cmd));
    uint8_t r[12];
    size_t n = 0;
    unsigned long t1 = millis();
    while (n < 12 && millis() - t1 < 200) {
      if (Roomba.available()) r[n++] = Roomba.read();
    }
    if (n < 12) { Serial.println("Sin respuesta (envia 's' primero)"); return; }
    Serial.printf("izq=%4u[%u]  front izq=%4u[%u]  front der=%4u[%u]  der=%4u[%u]\n",
                  (r[0] << 8) | r[1], r[8], (r[2] << 8) | r[3], r[9],
                  (r[4] << 8) | r[5], r[10], (r[6] << 8) | r[7], r[11]);
    delay(250);
  }
  Serial.println("Fin");
}

// Nombre de un codigo IR del mando (129-143) o 255 = sin codigo. El resto se imprime solo en numerico.
const char *irName(uint8_t c) {
  static const char *remote[] = {"Left", "Forward", "Right", "Spot", "Max", "Small", "Medium",
                                 "Clean", "Pause", "Power", "Arc-Left", "Arc-Right", "Stop",
                                 "Download", "Seek Dock"};
  if (c == 255) return "ninguno";
  if (c >= 129 && c <= 143) return remote[c - 129];
  return "otro";
}

// Vigila el IR omni (paquete 17) y los IR izquierdo/derecho (52, 53) durante 15 s.
// Imprime solo cuando cambian. Muestra el codigo ya decodificado, no la senal en bruto.
void watchIR() {
  const uint8_t cmd[] = {149, 3, 17, 52, 53};
  uint8_t last[3] = {0, 0, 0};
  bool first = true;
  Serial.println("Vigilando IR 15 s (omni / izq / der)...");
  unsigned long t0 = millis();
  while (millis() - t0 < 15000) {
    while (Roomba.available()) Roomba.read();
    Roomba.write(cmd, sizeof(cmd));
    uint8_t r[3];
    size_t n = 0;
    unsigned long t1 = millis();
    while (n < 3 && millis() - t1 < 200) {
      if (Roomba.available()) r[n++] = Roomba.read();
    }
    if (n < 3) { Serial.println("Sin respuesta (envia 's' primero)"); return; }
    if (first || memcmp(r, last, 3) != 0) {
      Serial.printf("IR omni=%u (%s)  izq=%u (%s)  der=%u (%s)\n",
                    r[0], irName(r[0]), r[1], irName(r[1]), r[2], irName(r[2]));
      memcpy(last, r, 3);
      first = false;
    }
    delay(50);
  }
  Serial.println("Fin");
}

// LEDs (139): bits 0-3 = debris, spot, dock, check robot; luego color e intensidad del LED de potencia.
void toggleLeds() {
  static bool on = false;
  on = !on;
  uint8_t cmd[] = {139, (uint8_t)(on ? 0x0F : 0x00), (uint8_t)(on ? 255 : 0), (uint8_t)(on ? 255 : 0)};
  Roomba.write(cmd, sizeof(cmd));
  Serial.println(on ? "LEDs encendidos" : "LEDs apagados");
}

void setup() {
  Serial.begin(115200);
  pinMode(BRC_PIN, INPUT);
  Roomba.begin(115200, SERIAL_8N1, RX_PIN, TX_PIN);
  Serial.println("Listo. Letras: s r v p l 1 2 3 4 5 e i c z a f b w x");
}

void loop() {
  if (!Serial.available()) return;
  char cmd = Serial.read();
  switch (cmd) {
    case 's': sendByte(128); Serial.println("Start enviado"); break;
    case 'r': sendByte(7);   Serial.println("Reset enviado, leyendo..."); dump(4000); break;
    case 'v': readVoltage(); break;
    case 'p': readSensors(); break;
    case 'l': toggleLeds(); break;
    case '1': drivePulse(0, 100, 1000); break;    // solo rueda izquierda
    case '2': drivePulse(100, 0, 1000); break;    // solo rueda derecha
    case '3': drivePulse(100, 100, 1000); break;  // ambas hacia delante
    case '4': brushPulse(40, 0, 1000); break;   // cepillo principal
    case '5': brushPulse(0, 40, 1000); break;   // cepillo lateral
    case 'e': encoderTest(); break;
    case 'i': watchIR(); break;
    case 'c': readCliffSignals(); break;
    case 'z': driveDirect(0, 0); Serial.println("Parado"); break;
    case 'a': sendByte(131); Serial.println("Safe enviado"); break;
    case 'f': sendByte(132); Serial.println("Full enviado"); break;
    case 'b': {
      // Song 0: una nota (MIDI 72, 16/64 s) y se reproduce
      uint8_t song[] = {140, 0, 1, 72, 16};
      Roomba.write(song, sizeof(song));
      delay(50);
      sendByte(141);
      sendByte(0);
      Serial.println("Nota enviada");
      break;
    }
    case 'w': wakePulse(); break;
    case 'x': sendByte(173); Serial.println("Stop enviado"); break;
    default: break;
  }
}
