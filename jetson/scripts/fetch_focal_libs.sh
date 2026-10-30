#!/bin/sh
# Descarga libc6, libstdc++6 y libgcc-s1 de Ubuntu 20.04 (focal) a ~/robot/tts/focal, SIN instalar nada
# en el sistema. Sirven para ejecutar programas compilados para sistemas más nuevos (Piper, Vosk) en el
# Jetson Nano, que trae Ubuntu 18.04 (glibc 2.27, libstdc++ hasta GLIBCXX_3.4.25).
set -e

BASE=http://ports.ubuntu.com/ubuntu-ports
DEST="$HOME/robot/tts"

mkdir -p "$DEST/focal" "$DEST/dl"
cd "$DEST/dl"

wget -q -O Packages.gz "$BASE/dists/focal-updates/main/binary-arm64/Packages.gz"

for pkg in libc6 libstdc++6 libgcc-s1; do
  file=$(zcat Packages.gz | awk -v want="$pkg" '$1=="Package:" {cur=$2} $1=="Filename:" && cur==want {print $2; exit}')
  if [ -z "$file" ]; then
    echo "No encontré $pkg en el índice" >&2
    exit 1
  fi
  echo "$pkg -> $file"
  wget -q "$BASE/$file"
  dpkg -x "$(basename "$file")" "$DEST/focal"
done

echo "--- cargador y librerías extraídas:"
ls "$DEST/focal/lib/aarch64-linux-gnu" | grep -E "^(ld-|libc\.|libm\.|libgcc)" | head
ls "$DEST/focal/usr/lib/aarch64-linux-gnu" | grep "libstdc++" | head -3
