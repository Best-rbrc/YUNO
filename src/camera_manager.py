"""
Foto aufnehmen mit Raspberry Pi Camera oder Fallback zu USB-Kamera
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


def check_camera_available() -> bool:
	"""Prüft ob die Raspberry Pi Kamera verfügbar ist.
	
	Returns:
		True wenn Kamera erkannt wird, False sonst
	"""
	try:
		# Teste mit rpicam-hello (schneller als rpicam-still)
		result = subprocess.run(
			['rpicam-hello', '--timeout', '500'],
			capture_output=True,
			timeout=2,
			text=True
		)
		return result.returncode == 0
	except FileNotFoundError:
		# rpicam-hello nicht verfügbar, versuche libcamera-hello
		try:
			result = subprocess.run(
				['libcamera-hello', '--timeout', '500'],
				capture_output=True,
				timeout=2,
				text=True
			)
			return result.returncode == 0
		except FileNotFoundError:
			return False
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


def take_photo(save_path: str) -> str:
	"""Take a photo from the camera and save to `save_path`.

	Priority:
	1. Raspberry Pi Camera (rpicam-still) - für CSI Camera am J4 Port
	2. OpenCV (cv2) - für USB Kameras
	3. Fallback: Placeholder image (nur wenn keine Kamera verfügbar)
	
	Returns the path to the saved image.
	"""
	os.makedirs(os.path.dirname(save_path), exist_ok=True)

	# ========== 1. VERSUCH: Raspberry Pi Camera (CSI Port J4) mit rpicam-still ==========
	# Für Raspberry Pi 5: Nur rpicam-still verwenden (libcamera-Pipeline)
	
	# Optional: Schnelle Verfügbarkeitsprüfung (kann auskommentiert werden wenn zu langsam)
	# if not check_camera_available():
	#     print("⚠️ Kamera nicht verfügbar - überspringe Foto")
	#     # Fallback zu Platzhalter-Bild
	#     pass
	
	try:
		# Versuche rpicam-still (Raspberry Pi 5 mit libcamera)
		result = subprocess.run(
			[
				'rpicam-still',
				'-o', save_path,
				'--width', '1920',
				'--height', '1080',
				'--timeout', '2000',
				'--nopreview',
			],
			capture_output=True,
			timeout=10,
			text=True
		)
		
		# Prüfe zuerst ob Datei existiert (wichtigste Prüfung)
		# Manche Tools geben Warnungen aus, aber erstellen trotzdem erfolgreich das Foto
		if os.path.exists(save_path):
			# Erfolgreich! Optional: Helligkeitsanpassung und 180° Rotation
			try:
				img = Image.open(save_path)
				
				# Rotiere um 180 Grad
				img = img.rotate(180, expand=False)
				
				# Helligkeits-Check
				if np is not None and cv2 is not None:
					img_array = np.array(img)
					gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
					avg_brightness = np.mean(gray)
					
					# Bei Dunkelheit aufhellen
					if avg_brightness < 80:
						enhancer = ImageEnhance.Brightness(img)
						brightness_factor = min(1.8, 100 / (avg_brightness + 1))
						img = enhancer.enhance(brightness_factor)
					
					img.save(save_path, quality=95)
				
			except Exception:
				# Foto existiert, auch wenn Enhancement fehlschlägt
				pass
			
			return save_path
		else:
			# Datei existiert nicht - zeige Fehlermeldung nur wenn wirklich fehlgeschlagen
			error_msg = ""
			stdout_msg = ""
			
			if result.stderr:
				error_msg = result.stderr
			if result.stdout:
				stdout_msg = result.stdout
			
			# Kombiniere stderr und stdout für vollständige Fehlersuche
			full_error = (error_msg + "\n" + stdout_msg).strip()
			
			# Spezielle Behandlung für "no cameras available"
			if "no cameras available" in full_error.lower():
				print("\n" + "="*60)
				print("❌ KAMERA WIRD NICHT VOM SYSTEM ERKANNT!")
				print("="*60)
				print("\n📋 SO BEHEBST DU DAS PROBLEM:")
				print("\n1️⃣  Kamera Interface aktivieren:")
				print("   sudo raspi-config")
				print("   → Interface Options")
				print("   → Camera")
				print("   → Enable")
				print("   → Finish → Yes (reboot)")
				print("\n2️⃣  Nach Neustart testen:")
				print("   rpicam-hello --timeout 2000")
				print("\n3️⃣  Falls immer noch Fehler:")
				print("   - Kamera-Kabel prüfen (CSI-Port J4)")
				print("   - Kameramodul prüfen (kompatibel mit Pi 5?)")
				print("   - Hardware-Defekt möglich")
				print("\n" + "="*60)
				print("⚠️  Programm läuft weiter ohne Kamera (Fallback-Bild wird erstellt)\n")
			else:
				# Andere Fehler - nur ausgeben wenn returncode != 0 UND Datei nicht existiert
				if result.returncode != 0:
					if error_msg:
						print(f"⚠️ rpicam-still Fehler (returncode {result.returncode})")
						print(f"   {error_msg[:300]}")
					if stdout_msg:
						print(f"📝 Output: {stdout_msg[:200]}")
			
	except FileNotFoundError:
		# rpicam-still nicht gefunden, versuche libcamera-still (ältere Pi-Versionen)
		try:
			result = subprocess.run(
				[
					'libcamera-still',
					'-o', save_path,
					'--width', '1920',
					'--height', '1080',
					'-t', '2000',
					'--nopreview',
				],
				capture_output=True,
				timeout=10,
				text=True
			)
			
			if result.returncode == 0 and os.path.exists(save_path):
				# Rotiere um 180 Grad
				try:
					img = Image.open(save_path)
					img = img.rotate(180, expand=False)
					img.save(save_path, quality=95)
				except Exception:
					pass
				return save_path
			else:
				if result.stderr:
					error_msg = result.stderr[:500]
					print(f"⚠️ libcamera-still Fehler: {error_msg}")
		except Exception as e:
			print(f"⚠️ libcamera-still nicht verfügbar: {e}")
			
	except Exception as e:
		print(f"⚠️ rpicam-still Exception: {e}")
		import traceback
		traceback.print_exc()
	
	# ========== 2. VERSUCH: OpenCV (USB Kamera) ==========
	# Hinweis: Auf Raspberry Pi 5 funktioniert cv2.VideoCapture() nicht (libcamera statt V4L2)
	# Deshalb wird dieser Fallback nur auf Nicht-Pi-Systemen verwendet
	# Prüfe ob wir auf einem Pi sind (rpicam-still sollte funktionieren)
	is_raspberry_pi = shutil.which("rpicam-still") is not None or shutil.which("libcamera-still") is not None
	
	if not is_raspberry_pi and cv2 is not None and np is not None:
		try:
			# Versuche nur wenn wir nicht auf einem Pi sind (rpicam-still nicht verfügbar)
			# oder als letzter Fallback für USB-Kameras auf anderen Systemen
			cap = cv2.VideoCapture(0)
			if cap is not None and cap.isOpened():
				# Try to increase exposure (may not work on all systems)
				try:
					cap.set(cv2.CAP_PROP_EXPOSURE, -4)
					cap.set(cv2.CAP_PROP_BRIGHTNESS, 0.6)
				except Exception:
					pass  # Ignoriere wenn nicht unterstützt
				
				# Let camera warm up and auto-adjust (capture and discard a few frames)
				for _ in range(10):
					try:
						cap.read()
						time.sleep(0.1)
					except Exception:
						break  # Bei Fehler abbrechen
				
				# Now capture the actual frame
				ret, frame = cap.read()
				cap.release()
				
				if ret and frame is not None and frame.size > 0:
					# Check if image is too dark and auto-brighten
					gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
					avg_brightness = np.mean(gray)
					
					# If average brightness is below 80 (on 0-255 scale), brighten it
					if avg_brightness < 80:
						brightness_factor = min(2.0, 100 / (avg_brightness + 1))
						frame = cv2.convertScaleAbs(frame, alpha=brightness_factor, beta=20)
					
					# OpenCV uses BGR; convert to RGB before saving with PIL
					frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
					img = Image.fromarray(frame)

					# Hinweis: KEINE 180°-Rotation hier. Dieser Pfad wird für
					# USB-/Mac-Webcams verwendet, die bereits aufrecht liefern.
					# Die 180°-Drehung gilt nur für die physisch verkehrt herum
					# montierte Raspberry-Pi-Kamera (rpicam-/libcamera-Pfad oben).

					# Additional PIL brightness enhancement if still needed
					enhancer = ImageEnhance.Brightness(img)
					img = enhancer.enhance(1.2)
					
					img.save(save_path, quality=95)
					return save_path
		except Exception:
			# Ignoriere Fehler stillschweigend (z.B. auf Pi 5 mit libcamera)
			pass

	# ========== 3. FALLBACK: Platzhalter ==========
	img = Image.new('RGB', (640, 480), color='gray')
	# Slightly annotate with timestamp so files are identifiable
	try:
		from PIL import ImageDraw, ImageFont
		draw = ImageDraw.Draw(img)
		ts = datetime.now().isoformat(timespec='seconds')
		draw.text((10, 10), "NO CAMERA FOUND", fill=(255, 0, 0))
		draw.text((10, 30), ts, fill=(255, 255, 255))
		draw.text((10, 50), "rpicam-still not working", fill=(255, 255, 255))
	except Exception:
		pass
	img.save(save_path)
	return save_path
