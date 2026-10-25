// Cliente del Open Interface (OI) de iRobot Roomba serie 600 para ESP32.
//
// Uso tipico:
//   RoombaOI roomba;
//   roomba.begin(Serial2, RX_PIN, TX_PIN, BRC_PIN);
//   roomba.start();                       // Passive
//   roomba.full();                        // o roomba.safe()
//   roomba.startStream(ids, sizeof(ids)); // lecturas periodicas cada 15 ms
//   loop() { roomba.update(); ... }
//
// No mezcles startStream() con querySensors() a la vez: las respuestas se confundirian.
// Los codigos y longitudes de paquete son los de la spec OI del Create 2 / Roomba 600.
#pragma once

#include <Arduino.h>

class RoombaOI {
public:
  enum Mode : uint8_t { MODE_OFF = 0, MODE_PASSIVE = 1, MODE_SAFE = 2, MODE_FULL = 3, MODE_UNKNOWN = 255 };

  // Radios especiales de drive()
  static const int16_t RADIUS_STRAIGHT = (int16_t)0x8000;
  static const int16_t RADIUS_SPIN_CCW = 1;
  static const int16_t RADIUS_SPIN_CW = -1;

  static const uint8_t kMaxPacketId = 58;

  // Prepara el puerto serie. brcPin = -1 si no se usa BRC.
  // BRC solo se baja a nivel bajo (es una entrada de 5 V del Roomba), nunca se sube.
  bool begin(HardwareSerial &port, int8_t rxPin, int8_t txPin, int8_t brcPin = -1, uint32_t baud = 115200);

  // Pulso bajo de 100 ms en BRC para despertar al robot.
  void wake();

  // Modos. El modo guardado es el ultimo comandado, o el que informa el paquete 35 si va en el stream.
  void start();   // Off -> Passive (tambien vuelve a Passive desde Safe/Full)
  void safe();
  void full();
  void stop();    // cierra el OI
  void reset();
  Mode mode() const { return _mode; }

  // Movimiento (Safe o Full). Velocidades en mm/s, -500..500.
  void driveDirect(int16_t rightMmS, int16_t leftMmS);
  void drive(int16_t velocityMmS, int16_t radiusMm);
  void stopMotors();

  // Cepillos y aspiracion (PWM). principal y lateral -127..127, aspiracion 0..127.
  void setBrushes(int8_t mainPwm, int8_t sidePwm, uint8_t vacuumPwm = 0);

  // LEDs: bits 0-3 = debris, spot, dock, check robot.
  void setLeds(uint8_t bits, uint8_t powerColor, uint8_t powerIntensity);

  // Define la cancion 0 con una nota (MIDI 31..127, duracion en 1/64 s) y la reproduce.
  // Bloquea unos 50 ms.
  void playNote(uint8_t midiNote, uint8_t duration64ths);

  // --- Lectura puntual (bloqueante, con timeout) ---
  // Pide los paquetes ids[0..n-1] y los deja concatenados en out. Devuelve false si falla.
  bool querySensors(const uint8_t *ids, uint8_t n, uint8_t *out, size_t outLen, uint16_t timeoutMs = 100);

  // --- Stream ---
  bool startStream(const uint8_t *ids, uint8_t n);
  void pauseStream(bool pause);
  // Llamar en loop(): procesa los bytes recibidos sin bloquear.
  void update();

  // Ultimo valor recibido por el stream. Devuelven false si no hay dato de ese paquete o la longitud no coincide.
  bool getU8(uint8_t id, uint8_t &v) const;
  bool getS8(uint8_t id, int8_t &v) const;
  bool getU16(uint8_t id, uint16_t &v) const;
  bool getS16(uint8_t id, int16_t &v) const;

  // True una vez por cada trama nueva; se borra al consultarlo.
  bool takeNewFrame();
  uint32_t lastFrameAgeMs() const { return _lastFrameMs ? millis() - _lastFrameMs : 0xFFFFFFFF; }
  uint32_t framesOk() const { return _framesOk; }
  uint32_t framesBad() const { return _framesBad; }
  uint32_t rxBytes() const { return _rxBytes; }  // bytes recibidos en total, para diagnosticar cableado

  // Longitud en bytes de un paquete (0 si no esta soportado).
  static uint8_t packetLength(uint8_t id);

private:
  void send(const uint8_t *b, size_t n);
  void sendByte(uint8_t b) { send(&b, 1); }
  bool decodeFrame();

  HardwareSerial *_port = nullptr;
  int8_t _brc = -1;
  Mode _mode = MODE_OFF;

  enum RxState : uint8_t { WAIT_HEADER, WAIT_LEN, PAYLOAD, WAIT_CHECKSUM };
  RxState _rxState = WAIT_HEADER;
  uint8_t _buf[256];
  uint8_t _expected = 0;
  uint8_t _got = 0;
  uint8_t _sum = 0;

  uint8_t _data[kMaxPacketId + 1][2] = {};
  bool _valid[kMaxPacketId + 1] = {};
  bool _newFrame = false;
  uint32_t _lastFrameMs = 0;
  uint32_t _framesOk = 0;
  uint32_t _framesBad = 0;
  uint32_t _rxBytes = 0;
};
