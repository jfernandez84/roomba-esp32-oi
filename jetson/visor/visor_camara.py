#!/usr/bin/env python3
"""Visor en tiempo real de la cámara del Jetson, en el navegador del Mac. Solo biblioteca estándar.

    python3 visor_camara.py --host IP_DEL_JETSON [--user jorge] [--key ~/.ssh/mi_clave]

Cómo funciona y por qué es seguro:
  * Lanza ffmpeg en el Jetson POR SSH y recibe los fotogramas por la salida del propio túnel SSH.
    No se abre ningún puerto en el Jetson, así que nadie más de la red puede ver la cámara.
  * Sirve el vídeo en http://127.0.0.1:PUERTO, solo accesible desde este Mac, y abre el navegador.
  * La cámara solo está abierta mientras el visor corre (el LED de la cámara se enciende). Con Ctrl+C
    se cierra todo.

Aviso: la cámara solo admite un programa a la vez. Mientras el visor está abierto, la herramienta
"mirar" del robot no puede usarla.
"""
import argparse
import os
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html><html lang="es"><meta charset="utf-8"><title>Cámara del robot</title>
<style>body{margin:0;background:#111;color:#ccc;font-family:sans-serif;text-align:center}
img{max-width:100%;height:auto;margin-top:12px;border-radius:6px}p{font-size:14px}</style>
<body><p>Cámara del robot en directo</p><img src="/stream" alt="Cámara"></body></html>""".encode("utf-8")

SOI, EOI = b"\xff\xd8", b"\xff\xd9"   # inicio y fin de un JPEG


class Frames:
    """Último fotograma recibido, con aviso a los clientes cuando llega uno nuevo."""

    def __init__(self):
        self.condition = threading.Condition()
        self.frame = None
        self.number = 0
        self.alive = True

    def publish(self, frame):
        with self.condition:
            self.frame, self.number = frame, self.number + 1
            self.condition.notify_all()

    def stop(self):
        with self.condition:
            self.alive = False
            self.condition.notify_all()

    def wait_next(self, last_number):
        with self.condition:
            while self.alive and self.number == last_number:
                self.condition.wait(timeout=2)
            return self.frame, self.number


def read_stream(process, frames):
    """Separa el flujo de ffmpeg en JPEG sueltos y los publica."""
    buffer = b""
    while True:
        chunk = process.stdout.read1(65536)
        if not chunk:
            break
        buffer += chunk
        while True:
            start = buffer.find(SOI)
            if start < 0:
                buffer = b""
                break
            end = buffer.find(EOI, start + 2)
            if end < 0:
                buffer = buffer[start:]
                break
            frames.publish(buffer[start:end + 2])
            buffer = buffer[end + 2:]
    frames.stop()


def make_handler(frames):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):   # sin ruido en la terminal
            pass

        def do_GET(self):
            if self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(PAGE)))
                self.end_headers()
                self.wfile.write(PAGE)
            elif self.path == "/stream":
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                number = 0
                try:
                    while True:
                        frame, number = frames.wait_next(number)
                        if frame is None or not frames.alive:
                            break
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n"
                                         % len(frame) + frame + b"\r\n")
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self.send_error(404)
    return Handler


def main():
    parser = argparse.ArgumentParser(description="Visor de la cámara del Jetson")
    parser.add_argument("--host", default=os.environ.get("ROBOT_HOST"), help="IP o nombre del Jetson")
    parser.add_argument("--user", default=os.environ.get("ROBOT_USER"), help="usuario del Jetson")
    parser.add_argument("--key", default=os.environ.get("ROBOT_KEY"), help="clave SSH (si no es la de siempre)")
    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument("--size", default="640x480")
    parser.add_argument("--fps", default="10")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="no abrir el navegador")
    args = parser.parse_args()
    if not args.host or not args.user:
        parser.error("Faltan --host y --user (o las variables ROBOT_HOST y ROBOT_USER) del Jetson")

    remote = ("ffmpeg -hide_banner -loglevel error -f v4l2 -input_format yuyv422 -framerate 15 "
              "-video_size %s -i %s -vf fps=%s -q:v 6 -f image2pipe -c:v mjpeg -" % (args.size, args.device, args.fps))
    command = ["ssh", "-o", "BatchMode=yes"]
    if args.key:
        command += ["-o", "IdentitiesOnly=yes", "-i", os.path.expanduser(args.key)]
    command += ["%s@%s" % (args.user, args.host), remote]

    print("Conectando con el Jetson y abriendo la cámara...", flush=True)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    frames = Frames()
    threading.Thread(target=read_stream, args=(process, frames), daemon=True).start()

    deadline = time.time() + 15   # se espera el primer fotograma
    while frames.number == 0 and frames.alive and time.time() < deadline:
        time.sleep(0.1)
    if frames.number == 0:
        process.terminate()
        error = process.stderr.read().decode("utf-8", "replace").strip()
        sys.exit("No llegó ningún fotograma.\n%s" % (error or "(sin mensaje de error)"))

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(frames))
    url = "http://127.0.0.1:%d" % args.port
    print("En directo: %s   (Ctrl+C para terminar y apagar la cámara)" % url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando...")
    finally:
        frames.stop()
        process.terminate()
        server.server_close()


if __name__ == "__main__":
    main()
