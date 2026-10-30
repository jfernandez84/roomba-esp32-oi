#!/bin/sh
# Dice un texto con Piper (voz neuronal local) y lo reproduce por HDMI.
# Uso: say.sh "Hola, soy tu robot" [modelo.onnx]
#      say.sh archivo.txt [modelo.onnx]     (si el primer argumento es un archivo, se lee su contenido)
#
# Piper está compilado para sistemas más nuevos que el Ubuntu 18.04 del Jetson Nano, así que se
# ejecuta con el cargador y las librerías de Ubuntu 20.04 descargadas por fetch_focal_libs.sh.
# El sistema no se modifica.
#
# Se añade un silencio inicial al audio porque el canal HDMI tarda un instante en despertar y
# se comía el principio de la frase.
set -e

TTS="$HOME/robot/tts"
FOCAL="$TTS/focal"
MODEL="${2:-$TTS/voices/es_MX-claude-high.onnx}"
OUT="/tmp/say.wav"
PADDED="/tmp/say_padded.wav"

if [ -f "$1" ]; then
  TEXT=$(cat "$1")
else
  TEXT="$1"
fi

echo "$TEXT" | "$FOCAL/lib/aarch64-linux-gnu/ld-2.31.so" \
  --library-path "$FOCAL/lib/aarch64-linux-gnu:$FOCAL/usr/lib/aarch64-linux-gnu:$TTS/piper" \
  "$TTS/piper/piper" --model "$MODEL" --espeak_data "$TTS/piper/espeak-ng-data" --output_file "$OUT" \
  2>&1 | grep -v "pthread_setaffinity_np" >&2 || true

sox "$OUT" "$PADDED" pad 0.6 0
aplay -D plughw:0,3 -q "$PADDED"
