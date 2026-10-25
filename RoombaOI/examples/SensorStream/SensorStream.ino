// Lee sensores del Roomba por stream (cada 15 ms) y los imprime 2 veces por segundo.
// No mueve nada. Cableado como en roomba_test: pin 4 (TXD) -> 1k -> GPIO16, GPIO17 -> pin 3, GND comun.

#include <RoombaOI.h>

HardwareSerial RoombaPort(2);
RoombaOI roomba;

const int RX_PIN = 16;
const int TX_PIN = 17;
const int BRC_PIN = 4;

// 7 bumps/ruedas, 9-12 acantilados, 18 botones, 22 tension, 24 temperatura, 35 modo, 43/44 encoders
const uint8_t kIds[] = {7, 9, 10, 11, 12, 18, 22, 24, 35, 43, 44};

void setup() {
  Serial.begin(115200);
  roomba.begin(RoombaPort, RX_PIN, TX_PIN, BRC_PIN);
  delay(500);
  roomba.wake();  // el robot se duerme tras unos minutos en Passive y entonces ignora start()
  delay(200);
  roomba.start();
  delay(100);
  roomba.startStream(kIds, sizeof(kIds));
  Serial.println("Stream iniciado");
}

void loop() {
  roomba.update();

  static uint32_t lastPrint = 0;
  if (millis() - lastPrint < 500) return;
  lastPrint = millis();

  if (roomba.lastFrameAgeMs() > 1000) {
    Serial.printf("Sin tramas: bytes recibidos=%lu, tramas mal=%lu. Reintento con pulso BRC...\n",
                  (unsigned long)roomba.rxBytes(), (unsigned long)roomba.framesBad());
    roomba.wake();
    delay(200);
    roomba.start();
    delay(100);
    roomba.startStream(kIds, sizeof(kIds));
    return;
  }

  uint8_t bumps = 0, buttons = 0, mode = 0;
  uint16_t mv = 0;
  int8_t temp = 0;
  int16_t encL = 0, encR = 0;
  roomba.getU8(7, bumps);
  roomba.getU8(18, buttons);
  roomba.getU8(35, mode);
  roomba.getU16(22, mv);
  roomba.getS8(24, temp);
  roomba.getS16(43, encL);
  roomba.getS16(44, encR);

  Serial.printf("modo=%u bumps/ruedas=0x%02X botones=0x%02X %u mV %d C encI=%d encD=%d  (ok=%lu mal=%lu)\n",
                mode, bumps, buttons, mv, temp, encL, encR,
                (unsigned long)roomba.framesOk(), (unsigned long)roomba.framesBad());
}
