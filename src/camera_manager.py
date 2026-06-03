"""
Foto aufnehmen.

Wählt automatisch die passende Kamera-Quelle:
  • Raspberry Pi  → Pi-Kamera über rpicam-still / libcamera-still (CSI-Port)
  • Mac / PC      → eingebaute oder USB-Webcam über OpenCV (cv2.VideoCapture)

Die Log-Ausgaben benennen immer die tatsächlich verwendete Quelle, damit
auf dem Mac keine irreführenden "rpicam"-Warnungen erscheinen.
"""
from datetime import datetime
import os
import time
import subprocess
import shutil

try:
	import cv2
	import numpy as np
except Exception:
	cv2 = None
	np = None

from PIL import Image, ImageEnhance


def on_raspberry_pi() -> bool:
	"""True wenn das Raspberry-Pi-Kamera-Stack (rpicam/libcamera) vorhanden ist.

	Dient zur Unterscheidung zwischen Pi-Kamera und Mac/PC-Webcam.
	"""
	return shutil.which("rpicam-still") is not None or shutil.which("libcamera-still") is not None


def check_camera_available() -> bool:
	"""Prüft ob eine nutzbare Kamera für die Aufnahme verfügbar ist.

	Auf dem Raspberry Pi wird die Pi-Kamera über rpicam-hello/libcamera-hello
	geprüft. Auf Mac/PC wird die OpenCV-Webcam (Index 0) geprüft.

	Returns:
		True wenn eine Kamera erkannt wird, False sonst.
	"""
	# --- Raspberry Pi: Pi-Kamera prüfen ---
	if on_raspberry_pi():
		for tool in ("rpicam-hello", "libcamera-hello"):
			try:
				result = subprocess.run(
					[tool, '--timeout', '500'],
					capture_output=True,
					timeout=2,
					text=True
				)
				if result.returncode == 0:
					return True
			except FileNotFoundError:
				continue
			except Exception:
				continue
		return False

	# --- Mac/PC: OpenCV-Webcam prüfen ---
	if cv2 is None:
		return False
	try:
		cap = cv2.VideoCapture(0)
		available = cap is not None and cap.isOpened()
		if cap is not None:
			cap.release()
		return available
	except Exception:
		return False


def take_multiple_photos_during_recording(base_path: str, callback_function):
    """
    Hilfsfunktion die während einer Audio-Aufnahme mehrere Fotos macht.
    Wird als Callback an record_audio übergeben.

    Args:
        base_path: Basis-Pfad für Fotos (ohne Endung), z.B. "data/photos/20231028_120000"
        callback_function: Die Funktion die aufgerufen werden soll für jedes Foto

    Returns:
        Eine Funktion die als Callback verwendet werden kann
    """
    photo_counter = [0]  # Liste statt int für closure

    def photo_callback(elapsed_time):
        """Wird während der Audio-Aufnahme aufgerufen"""
        photo_counter[0] += 1
        photo_path = f"{base_path}_frame{photo_counter[0]:03d}.jpg"

        try:
            take_photo(photo_path)
            if callback_function:
                callback_function(photo_path, photo_counter[0])
        except Exception:
            pass

    return photo_callback


def _enhance_dark_image(img: "Image.Image") -> "Image.Image":
	"""Hellt ein Bild auf, wenn es im Schnitt zu dunkel ist (avg < 80)."""
	if np is None or cv2 is None:
		return img
	try:
		gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
		avg_brightness = np.mean(gray)
		if avg_brightness < 80:
			factor = min(1.8, 100 / (avg_brightness + 1))
			img = ImageEnhance.Brightness(img).enhance(factor)
	except Exception:
		pass
	return img


def _capture_with_picamera(save_path: str) -> str | None:
	"""Nimmt ein Foto mit der Raspberry-Pi-Kamera auf (rpicam-still, sonst libcamera-still).

	Dreht das Bild um 180° (Pi-Kamera ist verkehrt herum montiert) und hellt
	dunkle Bilder auf. Gibt den Pfad zurück oder None bei Fehlschlag.
	"""
	# 1) rpicam-still (Raspberry Pi 5 / aktuelles libcamera)
	try:
		print("📷 Nehme Foto mit Raspberry-Pi-Kamera auf (rpicam-still)...")
		result = subprocess.run(
			['rpicam-still', '-o', save_path,
			 '--width', '1920', '--height', '1080',
			 '--timeout', '2000', '--nopreview'],
			capture_output=True, timeout=10, text=True
		)
		if os.path.exists(save_path):
			try:
				img = Image.open(save_path).rotate(180, expand=False)
				img = _enhance_dark_image(img)
				img.save(save_path, quality=95)
			except Exception:
				pass  # Foto existiert auch ohne Nachbearbeitung
			print("✅ Foto aufgenommen (Raspberry-Pi-Kamera)")
			return save_path

		# Datei nicht erstellt → echte Fehlerursache ermitteln
		full_error = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
		if "no cameras available" in full_error.lower():
			print("\n" + "=" * 60)
			print("❌ Raspberry-Pi-Kamera wird nicht erkannt!")
			print("=" * 60)
			print("  1) Kamera aktivieren:  sudo raspi-config → Interface → Camera → Enable → reboot")
			print("  2) Testen:             rpicam-hello --timeout 2000")
			print("  3) Hardware prüfen:    CSI-Kabel am Port J4, Modul Pi-5-kompatibel?")
			print("=" * 60 + "\n")
		elif result.returncode != 0 and full_error:
			print(f"⚠️ rpicam-still fehlgeschlagen (Code {result.returncode}): {full_error[:200]}")
		return None

	except FileNotFoundError:
		# rpicam-still nicht installiert → ältere Pi-Tools versuchen
		pass
	except Exception as e:
		print(f"⚠️ rpicam-still Ausnahme: {e}")
		return None

	# 2) libcamera-still (ältere Pi-Versionen)
	try:
		print("📷 rpicam-still nicht gefunden – versuche libcamera-still...")
		result = subprocess.run(
			['libcamera-still', '-o', save_path,
			 '--width', '1920', '--height', '1080',
			 '-t', '2000', '--nopreview'],
			capture_output=True, timeout=10, text=True
		)
		if result.returncode == 0 and os.path.exists(save_path):
			try:
				Image.open(save_path).rotate(180, expand=False).save(save_path, quality=95)
			except Exception:
				pass
			print("✅ Foto aufgenommen (Raspberry-Pi-Kamera, libcamera-still)")
			return save_path
		if result.stderr:
			print(f"⚠️ libcamera-still fehlgeschlagen: {result.stderr[:200]}")
	except Exception as e:
		print(f"⚠️ libcamera-still nicht nutzbar: {e}")
	return None


def _capture_with_webcam(save_path: str) -> str | None:
	"""Nimmt ein Foto mit der eingebauten/USB-Webcam auf (OpenCV).

	Keine 180°-Drehung (Webcam liefert aufrecht). Hellt dunkle Bilder auf.
	Gibt den Pfad zurück oder None bei Fehlschlag.
	"""
	if cv2 is None or np is None:
		print("⚠️ OpenCV (cv2) nicht installiert – Webcam-Aufnahme nicht möglich")
		return None

	try:
		print("📷 Nehme Foto mit eingebauter/USB-Webcam auf (OpenCV)...")
		cap = cv2.VideoCapture(0)
		if cap is None or not cap.isOpened():
			print("⚠️ Keine Webcam an Index 0 gefunden")
			if cap is not None:
				cap.release()
			return None

		# Belichtung/Helligkeit anpassen (nicht überall unterstützt)
		try:
			cap.set(cv2.CAP_PROP_EXPOSURE, -4)
			cap.set(cv2.CAP_PROP_BRIGHTNESS, 0.6)
		except Exception:
			pass

		# Kamera aufwärmen lassen (Auto-Belichtung)
		for _ in range(10):
			try:
				cap.read()
				time.sleep(0.1)
			except Exception:
				break

		ret, frame = cap.read()
		cap.release()

		if not (ret and frame is not None and frame.size > 0):
			print("⚠️ Webcam lieferte kein Bild")
			return None

		# Bei Dunkelheit aufhellen
		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		avg_brightness = np.mean(gray)
		if avg_brightness < 80:
			factor = min(2.0, 100 / (avg_brightness + 1))
			frame = cv2.convertScaleAbs(frame, alpha=factor, beta=20)

		# BGR → RGB, keine Drehung (Webcam steht aufrecht)
		frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
		img = ImageEnhance.Brightness(Image.fromarray(frame)).enhance(1.2)
		img.save(save_path, quality=95)
		print("✅ Foto aufgenommen (Webcam)")
		return save_path
	except Exception as e:
		print(f"⚠️ Webcam-Aufnahme fehlgeschlagen: {e}")
		return None


def take_photo(save_path: str) -> str:
	"""Nimmt ein Foto auf und speichert es unter `save_path`.

	Quelle wird automatisch gewählt:
	  • Raspberry Pi → Pi-Kamera (rpicam-still / libcamera-still)
	  • Mac / PC     → Webcam (OpenCV)
	Bei Fehlschlag wird ein beschriftetes Platzhalter-Bild erzeugt.

	Returns:
		Pfad zum gespeicherten Bild.
	"""
	os.makedirs(os.path.dirname(save_path), exist_ok=True)

	if on_raspberry_pi():
		# Auf dem Pi nur die Pi-Kamera nutzen (cv2.VideoCapture läuft dort nicht)
		result = _capture_with_picamera(save_path)
		placeholder_reason = "Pi-Kamera nicht verfügbar"
	else:
		# Auf Mac/PC die Webcam nutzen
		result = _capture_with_webcam(save_path)
		placeholder_reason = "Keine Webcam verfügbar"

	if result is not None:
		return result

	# ===== Fallback: Platzhalter-Bild =====
	print(f"🖼️ {placeholder_reason} – erstelle Platzhalter-Bild: {save_path}")
	img = Image.new('RGB', (640, 480), color='gray')
	try:
		from PIL import ImageDraw
		draw = ImageDraw.Draw(img)
		ts = datetime.now().isoformat(timespec='seconds')
		draw.text((10, 10), "NO CAMERA FOUND", fill=(255, 0, 0))
		draw.text((10, 30), ts, fill=(255, 255, 255))
		draw.text((10, 50), placeholder_reason, fill=(255, 255, 255))
	except Exception:
		pass
	img.save(save_path)
	return save_path
