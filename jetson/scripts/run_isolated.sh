#!/bin/sh
# Ejecuta un script de Python con el cargador y las librerías de Ubuntu 20.04 (glibc 2.31 y
# libstdc++ 10) descargadas por fetch_focal_libs.sh. Hace falta para Vosk, cuya librería está
# compilada para sistemas más nuevos que el Ubuntu 18.04 del Jetson Nano. El sistema no se modifica.
# Uso: run_isolated.sh script.py [argumentos]
F="$HOME/robot/tts/focal"
export PYTHONPATH="$HOME/robot/venv/lib/python3.6/site-packages:$HOME/robot"
exec "$F/lib/aarch64-linux-gnu/ld-2.31.so" \
  --library-path "$F/lib/aarch64-linux-gnu:$F/usr/lib/aarch64-linux-gnu:/usr/lib/aarch64-linux-gnu:/lib/aarch64-linux-gnu" \
  /usr/bin/python3 "$@"
