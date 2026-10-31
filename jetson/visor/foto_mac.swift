// Toma UNA foto con la cámara del Mac y la guarda como JPEG. Solo usa AVFoundation (viene con macOS).
//
// Compilar:  swiftc -swift-version 5 -O foto_mac.swift -o foto_mac
// Usar:      ./foto_mac RUTA.jpg [segundos_de_calentamiento]
//
// La cámara se enciende solo durante la captura (unos 2 s). La primera vez, macOS pide permiso de cámara
// para la aplicación desde la que se ejecuta (Terminal u otra).
import AVFoundation
import Foundation

let arguments = CommandLine.arguments
if arguments.count < 2 {
    FileHandle.standardError.write("Uso: foto_mac RUTA.jpg [calentamiento_en_segundos]\n".data(using: .utf8)!)
    exit(2)
}
let outputPath = arguments[1]
let warmup = arguments.count >= 3 ? (Double(arguments[2]) ?? 1.5) : 1.5

func fail(_ message: String, _ code: Int32 = 1) -> Never {
    FileHandle.standardError.write((message + "\n").data(using: .utf8)!)
    exit(code)
}

func spin(until deadline: Date, while condition: () -> Bool) {
    while condition() && Date() < deadline {
        RunLoop.current.run(until: Date(timeIntervalSinceNow: 0.05))
    }
}

// 1. Permiso de cámara
switch AVCaptureDevice.authorizationStatus(for: .video) {
case .authorized:
    break
case .notDetermined:
    var answered = false
    var granted = false
    AVCaptureDevice.requestAccess(for: .video) { ok in
        granted = ok
        answered = true
    }
    spin(until: Date(timeIntervalSinceNow: 60)) { !answered }   // da tiempo a pulsar "Permitir"
    if !granted {
        fail("Permiso de cámara denegado o sin respuesta. Actívalo en Ajustes del Sistema > Privacidad y seguridad > Cámara.", 3)
    }
default:
    fail("Sin permiso de cámara. Actívalo en Ajustes del Sistema > Privacidad y seguridad > Cámara.", 3)
}

// 2. Sesión de captura
guard let device = AVCaptureDevice.default(for: .video) else { fail("Este Mac no tiene cámara.") }
guard let input = try? AVCaptureDeviceInput(device: device) else {
    fail("No pude abrir la cámara (¿la está usando otra aplicación?).")
}
let session = AVCaptureSession()
session.beginConfiguration()
if session.canSetSessionPreset(.hd1280x720) { session.sessionPreset = .hd1280x720 }
guard session.canAddInput(input) else { fail("No pude conectar la cámara a la sesión.") }
session.addInput(input)
let photoOutput = AVCapturePhotoOutput()
guard session.canAddOutput(photoOutput) else { fail("No pude preparar la salida de fotos.") }
session.addOutput(photoOutput)
session.commitConfiguration()
session.startRunning()

// 3. Calentamiento (la exposición tarda en ajustarse) y foto
let warmEnd = Date(timeIntervalSinceNow: warmup)
spin(until: warmEnd) { true }

final class Receiver: NSObject, AVCapturePhotoCaptureDelegate {
    var finished = false
    func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        if let error = error { fail("Error al capturar: \(error.localizedDescription)") }
        guard let data = photo.fileDataRepresentation() else { fail("La cámara no devolvió datos.") }
        do {
            try data.write(to: URL(fileURLWithPath: outputPath))
        } catch {
            fail("No pude escribir \(outputPath): \(error.localizedDescription)")
        }
        finished = true
    }
}

let receiver = Receiver()
let settings = photoOutput.availablePhotoCodecTypes.contains(.jpeg)
    ? AVCapturePhotoSettings(format: [AVVideoCodecKey: AVVideoCodecType.jpeg])
    : AVCapturePhotoSettings()
photoOutput.capturePhoto(with: settings, delegate: receiver)
spin(until: Date(timeIntervalSinceNow: 10)) { !receiver.finished }
session.stopRunning()
if !receiver.finished { fail("Se agotó el tiempo esperando la foto.") }
