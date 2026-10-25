#include "RoombaOI.h"

namespace {

// Longitud en bytes de cada paquete de sensor (indice = id). 0 = no soportado (grupos 0-6).
const uint8_t kLen[RoombaOI::kMaxPacketId + 1] = {
    0, 0, 0, 0, 0, 0, 0,  // 0-6: grupos
    1, 1, 1, 1, 1, 1,     // 7-12
    1, 1, 1, 1, 1, 1,     // 13-18
    2, 2, 1, 2, 2, 1,     // 19-24
    2, 2, 2,              // 25-27
    2, 2, 2, 2,           // 28-31
    1, 2, 1, 1, 1, 1, 1,  // 32-38
    2, 2, 2, 2, 2, 2,     // 39-44
    1,                    // 45
    2, 2, 2, 2, 2, 2,     // 46-51
    1, 1,                 // 52-53
    2, 2, 2, 2,           // 54-57
    1,                    // 58
};

}  // namespace

uint8_t RoombaOI::packetLength(uint8_t id) {
  return id <= kMaxPacketId ? kLen[id] : 0;
}

bool RoombaOI::begin(HardwareSerial &port, int8_t rxPin, int8_t txPin, int8_t brcPin, uint32_t baud) {
  _port = &port;
  _brc = brcPin;
  if (_brc >= 0) pinMode(_brc, INPUT);
  _port->setRxBufferSize(1024);  // antes de begin(); el stream manda hasta ~170 bytes cada 15 ms
  _port->begin(baud, SERIAL_8N1, rxPin, txPin);
  return true;
}

void RoombaOI::send(const uint8_t *b, size_t n) {
  if (_port) _port->write(b, n);
}

void RoombaOI::wake() {
  if (_brc < 0) return;
  pinMode(_brc, OUTPUT);
  digitalWrite(_brc, LOW);
  delay(100);
  pinMode(_brc, INPUT);
}

// --- Modos ---

void RoombaOI::start() { sendByte(128); _mode = MODE_PASSIVE; }
void RoombaOI::safe()  { sendByte(131); _mode = MODE_SAFE; }
void RoombaOI::full()  { sendByte(132); _mode = MODE_FULL; }
void RoombaOI::stop()  { sendByte(173); _mode = MODE_OFF; }
void RoombaOI::reset() { sendByte(7);   _mode = MODE_OFF; }

// --- Actuadores ---

void RoombaOI::driveDirect(int16_t rightMmS, int16_t leftMmS) {
  const uint8_t cmd[] = {145, (uint8_t)(rightMmS >> 8), (uint8_t)rightMmS,
                         (uint8_t)(leftMmS >> 8), (uint8_t)leftMmS};
  send(cmd, sizeof(cmd));
}

void RoombaOI::drive(int16_t velocityMmS, int16_t radiusMm) {
  const uint8_t cmd[] = {137, (uint8_t)(velocityMmS >> 8), (uint8_t)velocityMmS,
                         (uint8_t)(radiusMm >> 8), (uint8_t)radiusMm};
  send(cmd, sizeof(cmd));
}

void RoombaOI::stopMotors() { driveDirect(0, 0); }

void RoombaOI::setBrushes(int8_t mainPwm, int8_t sidePwm, uint8_t vacuumPwm) {
  const uint8_t cmd[] = {144, (uint8_t)mainPwm, (uint8_t)sidePwm, vacuumPwm};
  send(cmd, sizeof(cmd));
}

void RoombaOI::setLeds(uint8_t bits, uint8_t powerColor, uint8_t powerIntensity) {
  const uint8_t cmd[] = {139, bits, powerColor, powerIntensity};
  send(cmd, sizeof(cmd));
}

void RoombaOI::playNote(uint8_t midiNote, uint8_t duration64ths) {
  const uint8_t song[] = {140, 0, 1, midiNote, duration64ths};
  send(song, sizeof(song));
  delay(50);
  const uint8_t play[] = {141, 0};
  send(play, sizeof(play));
}

// --- Lectura puntual ---

bool RoombaOI::querySensors(const uint8_t *ids, uint8_t n, uint8_t *out, size_t outLen, uint16_t timeoutMs) {
  if (!_port || n == 0) return false;
  size_t total = 0;
  for (uint8_t i = 0; i < n; i++) {
    uint8_t len = packetLength(ids[i]);
    if (len == 0) return false;
    total += len;
  }
  if (total > outLen) return false;

  while (_port->available()) _port->read();
  sendByte(149);
  sendByte(n);
  send(ids, n);

  size_t got = 0;
  uint32_t t0 = millis();
  while (got < total && millis() - t0 < timeoutMs) {
    if (_port->available()) out[got++] = _port->read();
  }
  return got == total;
}

// --- Stream ---

bool RoombaOI::startStream(const uint8_t *ids, uint8_t n) {
  if (!_port || n == 0) return false;
  for (uint8_t i = 0; i < n; i++) {
    if (packetLength(ids[i]) == 0) return false;
  }
  while (_port->available()) _port->read();
  _rxState = WAIT_HEADER;
  for (uint8_t i = 0; i <= kMaxPacketId; i++) _valid[i] = false;
  sendByte(148);
  sendByte(n);
  send(ids, n);
  return true;
}

void RoombaOI::pauseStream(bool pause) {
  const uint8_t cmd[] = {150, (uint8_t)(pause ? 0 : 1)};
  send(cmd, sizeof(cmd));
}

// Trama: 19, n, [id, datos...] x paquetes, checksum. La suma de todos los bytes (incluido el checksum) es 0 mod 256.
void RoombaOI::update() {
  if (!_port) return;
  while (_port->available()) {
    uint8_t b = _port->read();
    _rxBytes++;
    switch (_rxState) {
      case WAIT_HEADER:
        if (b == 19) { _sum = 19; _rxState = WAIT_LEN; }
        break;
      case WAIT_LEN:
        _expected = b;
        _got = 0;
        _sum += b;
        _rxState = (b == 0) ? WAIT_CHECKSUM : PAYLOAD;
        break;
      case PAYLOAD:
        _buf[_got++] = b;
        _sum += b;
        if (_got == _expected) _rxState = WAIT_CHECKSUM;
        break;
      case WAIT_CHECKSUM:
        _sum += b;
        if (_sum == 0 && decodeFrame()) {
          _framesOk++;
        } else {
          _framesBad++;
        }
        _rxState = WAIT_HEADER;
        break;
    }
  }
}

bool RoombaOI::decodeFrame() {
  // Primero se valida toda la trama y luego se copia, para no dejar datos a medias.
  size_t i = 0;
  while (i < _expected) {
    uint8_t id = _buf[i++];
    uint8_t len = packetLength(id);
    if (len == 0 || i + len > _expected) return false;
    i += len;
  }
  i = 0;
  while (i < _expected) {
    uint8_t id = _buf[i++];
    uint8_t len = packetLength(id);
    for (uint8_t k = 0; k < len; k++) _data[id][k] = _buf[i + k];
    _valid[id] = true;
    if (id == 35 && _data[35][0] <= MODE_FULL) _mode = (Mode)_data[35][0];
    i += len;
  }
  _lastFrameMs = millis();
  _newFrame = true;
  return true;
}

bool RoombaOI::takeNewFrame() {
  bool f = _newFrame;
  _newFrame = false;
  return f;
}

bool RoombaOI::getU8(uint8_t id, uint8_t &v) const {
  if (id > kMaxPacketId || !_valid[id] || kLen[id] != 1) return false;
  v = _data[id][0];
  return true;
}

bool RoombaOI::getS8(uint8_t id, int8_t &v) const {
  uint8_t u;
  if (!getU8(id, u)) return false;
  v = (int8_t)u;
  return true;
}

bool RoombaOI::getU16(uint8_t id, uint16_t &v) const {
  if (id > kMaxPacketId || !_valid[id] || kLen[id] != 2) return false;
  v = ((uint16_t)_data[id][0] << 8) | _data[id][1];
  return true;
}

bool RoombaOI::getS16(uint8_t id, int16_t &v) const {
  uint16_t u;
  if (!getU16(id, u)) return false;
  v = (int16_t)u;
  return true;
}
