// Control del Roomba desde el movil por WiFi. El ESP32 crea su propia red (no usa tu router).
//   1. Conecta el movil a la red WIFI_SSID con la clave WIFI_PASS.
//   2. Abre http://192.168.4.1
//   3. Mantén pulsado un boton para moverte; al soltar o perder la conexion el robot se para.
//
// Cambia WIFI_PASS antes de usarlo fuera de la mesa de pruebas.
// Con ruedas colgando o sensores sin conectar hace falta Full; con la base montada prueba Safe.

#include <WiFi.h>
#include <WebServer.h>
#include <RoombaOI.h>

const char *WIFI_SSID = "Roomba-ESP32";
const char *WIFI_PASS = "roomba1234";

const int RX_PIN = 16;
const int TX_PIN = 17;
const int BRC_PIN = 4;

const int16_t MAX_SPEED = 200;          // mm/s, tope de seguridad
const uint32_t FAILSAFE_MS = 400;       // sin ordenes durante este tiempo -> parar
#define USE_FULL_MODE 1                 // 0 = Safe

HardwareSerial RoombaPort(2);
RoombaOI roomba;
WebServer server(80);

// 7 bumps/ruedas, 22 tension, 24 temperatura, 35 modo, 43/44 encoders
const uint8_t kIds[] = {7, 22, 24, 35, 43, 44};

uint32_t lastCmdMs = 0;
uint32_t ignoreDriveUntilMs = 0;  // tras un /stop se descartan los /drive que lleguen tarde
bool moving = false;

const char PAGE[] PROGMEM = R"rawliteral(
<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>Roomba</title>
<style>
body{font-family:sans-serif;margin:16px;text-align:center;background:#111;color:#eee;touch-action:none}
.pad{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;max-width:320px;margin:16px auto}
button{font-size:28px;padding:22px 0;border:0;border-radius:12px;background:#2a6;color:#fff;user-select:none;-webkit-user-select:none}
button.stop{background:#c33}
#st{font-size:14px;color:#9a9;margin-top:12px}
input{width:80%}
</style></head><body>
<h2>Roomba</h2>
<div>Velocidad: <span id="sp">100</span> mm/s<br><input id="speed" type="range" min="50" max="200" step="10" value="100"></div>
<div class="pad">
<span></span><button data-l="1" data-r="1">&#9650;</button><span></span>
<button data-l="-1" data-r="1">&#9664;</button><button class="stop" id="stop">&#9632;</button><button data-l="1" data-r="-1">&#9654;</button>
<span></span><button data-l="-1" data-r="-1">&#9660;</button><span></span>
</div>
<div id="st">...</div>
<script>
let timer=null,active=false;
const sp=document.getElementById('speed');
sp.oninput=()=>document.getElementById('sp').textContent=sp.value;
function send(l,r){fetch('/drive?l='+l+'&r='+r).catch(()=>{});}
function halt(){active=false;clearInterval(timer);timer=null;fetch('/stop').catch(()=>{});}
document.querySelectorAll('button[data-l]').forEach(b=>{
  const l=+b.dataset.l,r=+b.dataset.r;
  b.onpointerdown=e=>{e.preventDefault();b.setPointerCapture(e.pointerId);active=true;
    const go=()=>{if(active)send(l*sp.value,r*sp.value);};go();timer=setInterval(go,100);};
  ['pointerup','pointercancel','lostpointercapture'].forEach(ev=>b.addEventListener(ev,halt));
});
document.getElementById('stop').onclick=halt;
setInterval(()=>fetch('/state').then(r=>r.json()).then(s=>{
  document.getElementById('st').textContent=
   s.mV+' mV  '+s.temp+' C  modo '+s.mode+'  bumps 0x'+s.bumps.toString(16)+'  enc '+s.encL+' / '+s.encR+'  [rx '+s.rx+' ok '+s.ok+' mal '+s.bad+']';
}).catch(()=>{document.getElementById('st').textContent='sin conexion';}),700);
</script></body></html>
)rawliteral";

void handleDrive() {
  if ((int32_t)(millis() - ignoreDriveUntilMs) < 0) {
    server.send(200, "text/plain", "ignorado");
    return;
  }
  int16_t l = constrain(server.arg("l").toInt(), -MAX_SPEED, MAX_SPEED);
  int16_t r = constrain(server.arg("r").toInt(), -MAX_SPEED, MAX_SPEED);
  roomba.driveDirect(r, l);  // el OI recibe primero la rueda derecha
  moving = (l != 0 || r != 0);
  lastCmdMs = millis();
  server.send(200, "text/plain", "ok");
}

void handleStop() {
  roomba.stopMotors();
  roomba.stopMotors();
  moving = false;
  ignoreDriveUntilMs = millis() + 300;
  server.send(200, "text/plain", "ok");
}

void handleState() {
  uint8_t bumps = 0, mode = 0;
  uint16_t mv = 0;
  int8_t temp = 0;
  int16_t encL = 0, encR = 0;
  roomba.getU8(7, bumps);
  roomba.getU8(35, mode);
  roomba.getU16(22, mv);
  roomba.getS8(24, temp);
  roomba.getS16(43, encL);
  roomba.getS16(44, encR);
  char json[192];
  snprintf(json, sizeof(json),
           "{\"mV\":%u,\"temp\":%d,\"mode\":%u,\"bumps\":%u,\"encL\":%d,\"encR\":%d,\"rx\":%lu,\"ok\":%lu,\"bad\":%lu}",
           mv, temp, mode, bumps, encL, encR,
           (unsigned long)roomba.rxBytes(), (unsigned long)roomba.framesOk(), (unsigned long)roomba.framesBad());
  server.send(200, "application/json", json);
}

// Despierta el robot, entra en el modo elegido y arranca el stream.
// El robot se duerme tras unos minutos en Passive y entonces ignora start().
void initRoomba() {
  roomba.wake();
  delay(200);
  roomba.start();
  delay(100);
#if USE_FULL_MODE
  roomba.full();
#else
  roomba.safe();
#endif
  delay(100);
  roomba.startStream(kIds, sizeof(kIds));
}

void setup() {
  Serial.begin(115200);
  roomba.begin(RoombaPort, RX_PIN, TX_PIN, BRC_PIN);
  delay(500);
  initRoomba();

  WiFi.mode(WIFI_AP);
  WiFi.softAP(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi: ");
  Serial.print(WIFI_SSID);
  Serial.print("  http://");
  Serial.println(WiFi.softAPIP());

  server.on("/", []() { server.send_P(200, "text/html", PAGE); });
  server.on("/drive", handleDrive);
  server.on("/stop", handleStop);
  server.on("/state", handleState);
  server.begin();
}

void loop() {
  roomba.update();
  server.handleClient();

  // Si no llegan tramas, se reintenta el despertar y el stream cada 3 s.
  static uint32_t lastRetryMs = 0;
  if (roomba.lastFrameAgeMs() > 1000 && millis() - lastRetryMs > 3000) {
    lastRetryMs = millis();
    Serial.printf("Sin tramas (bytes=%lu): reintentando\n", (unsigned long)roomba.rxBytes());
    initRoomba();
  }

  // Parada de seguridad: sin ordenes recientes, las ruedas se paran.
  if (moving && millis() - lastCmdMs > FAILSAFE_MS) {
    roomba.stopMotors();
    moving = false;
  }
}
