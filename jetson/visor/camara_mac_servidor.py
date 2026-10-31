#!/usr/bin/env python3
"""Presta la cámara de este Mac al robot (Jetson) para pruebas, hasta tener una cámara mejor.

    python3 camara_mac_servidor.py --host IP_DEL_JETSON [--user jorge] [--key ~/.ssh/mi_clave]

Cómo funciona, y por qué es seguro:
  * Un servidor en 127.0.0.1 (solo este Mac) que, cuando recibe GET /foto, saca UNA foto con la cámara
    del Mac (foto_mac, ver foto_mac.swift) y la devuelve. La cámara solo se enciende esos ~2 segundos.
  * Un túnel SSH que abre ESTE Mac hacia el Jetson (con tu clave) y que hace que, en el Jetson,
    http://127.0.0.1:PUERTO/foto llegue hasta este servidor. No se abre ningún puerto de este Mac en
    la red, y el Jetson no puede entrar en el Mac: solo puede pedir una foto.
  * Cualquier programa del Jetson puede pedir fotos mientras este programa esté abierto.
    Con Ctrl+C se cierra todo.

En el Jetson, para que el robot use esta cámara:  echo http://127.0.0.1:8766/foto > ~/robot/camara.txt
Para volver a la cámara del Jetson:               echo local > ~/robot/camara.txt
(Si este programa no está abierto, el robot usa la cámara del Jetson automáticamente.)
"""
import argparse
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
SWIFT_SOURCE = os.path.join(HERE, "foto_mac.swift")
BINARY = os.path.join(HERE, "foto_mac")

capture_lock = threading.Lock()   # la cámara solo admite una captura a la vez


def ensure_binary():
    if os.path.exists(BINARY) and os.path.getmtime(BINARY) >= os.path.getmtime(SWIFT_SOURCE):
        return
    print("Compilando foto_mac (solo la primera vez)...", flush=True)
    subprocess.check_call(["swiftc", "-swift-version", "5", "-O", SWIFT_SOURCE, "-o", BINARY])


def take_photo(warmup):
    """Saca una foto y devuelve los bytes del JPEG. La foto temporal se borra al momento."""
    fd, path = tempfile.mkstemp(suffix=".jpg", prefix="foto_mac_")
    os.close(fd)
    try:
        with capture_lock:
            result = subprocess.run([BINARY, path, str(warmup)], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=75)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode("utf-8", "replace").strip().splitlines()[-1]
                               if result.stderr.strip() else "falló foto_mac")
        with open(path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(path):
            os.remove(path)


def make_handler(warmup):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _reply(self, code, content_type, body):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.split("?")[0] == "/foto":
                started = time.time()
                try:
                    photo = take_photo(warmup)
                except Exception as error:
                    print("  foto fallida: %s" % error, flush=True)
                    self._reply(500, "text/plain; charset=utf-8", str(error).encode("utf-8"))
                    return
                print("  foto enviada (%d KB, %.1f s)" % (len(photo) // 1024, time.time() - started), flush=True)
                self._reply(200, "image/jpeg", photo)
            elif self.path == "/estado":
                self._reply(200, "text/plain; charset=utf-8", b"ok")
            else:
                self._reply(404, "text/plain; charset=utf-8", b"no existe")
    return Handler


def main():
    parser = argparse.ArgumentParser(description="Presta la cámara del Mac al robot")
    parser.add_argument("--host", default=os.environ.get("ROBOT_HOST"), help="IP o nombre del Jetson")
    parser.add_argument("--user", default=os.environ.get("ROBOT_USER"), help="usuario del Jetson")
    parser.add_argument("--key", default=os.environ.get("ROBOT_KEY"), help="clave SSH (si no es la de siempre)")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--warmup", type=float, default=1.5, help="segundos de calentamiento de la cámara")
    args = parser.parse_args()
    if not args.host or not args.user:
        parser.error("Faltan --host y --user (o las variables ROBOT_HOST y ROBOT_USER) del Jetson")

    ensure_binary()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.warmup))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    # Túnel inverso: en el Jetson, 127.0.0.1:PUERTO llega a este servidor.
    tunnel = ["ssh", "-N", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
              "-o", "ServerAliveInterval=15", "-R", "127.0.0.1:%d:127.0.0.1:%d" % (args.port, args.port)]
    if args.key:
        tunnel += ["-o", "IdentitiesOnly=yes", "-i", os.path.expanduser(args.key)]
    tunnel.append("%s@%s" % (args.user, args.host))
    process = subprocess.Popen(tunnel, stderr=subprocess.PIPE)
    time.sleep(2.5)
    if process.poll() is not None:
        server.shutdown()
        sys.exit("No se pudo abrir el túnel con el Jetson:\n%s" % process.stderr.read().decode("utf-8", "replace"))

    print("Cámara del Mac lista. En el Jetson: http://127.0.0.1:%d/foto" % args.port)
    print("Para que el robot la use:  echo http://127.0.0.1:%d/foto > ~/robot/camara.txt" % args.port)
    print("Ctrl+C para cerrar.\n", flush=True)
    try:
        while True:
            while process.poll() is None:
                time.sleep(1)
            reason = process.stderr.read().decode("utf-8", "replace").strip()
            # Una vez el túnel se cayó y el robot usó la cámara del Jetson sin que nadie lo notara.
            print("El túnel con el Jetson se cerró (%s). Reconectando..." % (reason or "sin mensaje"), flush=True)
            while True:
                time.sleep(3)
                process = subprocess.Popen(tunnel, stderr=subprocess.PIPE)
                time.sleep(2.5)
                if process.poll() is None:
                    print("Túnel reconectado.", flush=True)
                    break
    except KeyboardInterrupt:
        print("\nCerrando...")
    finally:
        process.terminate()
        server.shutdown()


if __name__ == "__main__":
    main()
