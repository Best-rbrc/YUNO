"""
Input Handler - Manages button input on Raspberry Pi for enroll/identify/rizz/sync actions

Single button mapping:
  1x Press:   Neue Person aufnehmen (Enroll)
  2x Press:   Person identifizieren (Identify)
  3x Press:   Rizz Mode
  Halten:     Datenbank synchronisieren (Sync)
"""

import time
import threading
import os
import sys
from src.person_manager import enroll_person, identify_person
from src.sync_manager import SyncManager
from src.camera_manager import take_photo, check_camera_available

# Demo-Modus Funktionen importieren
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from demo_rizz_mode import demo_rizz_mode_with_yannik
    from demo_identify_mode import demo_identify_mode
    DEMO_AVAILABLE = True
except ImportError:
    DEMO_AVAILABLE = False
    print("⚠️ Demo-Scripts nicht verfügbar")

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False
    print("⚠️ RPi.GPIO nicht verfügbar - Raspberry Pi Button-Funktion deaktiviert")

rizzmode_activated = False

def is_rizzmode_activated():
    """Return True if Rizz Mode is activated (placeholder, always False)."""
    return rizzmode_activated


# Photo capture during button mode
photo_capture_active = False
photo_capture_lock = threading.Lock()

def photo_capture_loop(interval_seconds: float = 10.0):
    """Periodically take photos while button listener is active."""
    global photo_capture_active
    photo_dir = os.path.join("data", "photos_button")
    os.makedirs(photo_dir, exist_ok=True)

    while True:
        with photo_capture_lock:
            if not photo_capture_active:
                break

        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            photo_path = os.path.join(photo_dir, f"button_{timestamp}.jpg")
            take_photo(photo_path)
        except Exception:
            pass

        time.sleep(interval_seconds)


# Raspberry Pi Button Handler
class ButtonHandler:
    """Handhabt Eingaben eines einzelnen Buttons vom Raspberry Pi.

    Erkennt Mehrfach-Drücken (1x/2x/3x) sowie langes Halten:
      1x Press:  Enroll
      2x Press:  Identify
      3x Press:  Rizz Mode
      Halten:    Sync
    """

    def __init__(self, button_pin=17, multi_press_timeout=0.8, hold_threshold=1.0):
        """
        Args:
            button_pin: GPIO Pin für den Button (BCM Nummerierung)
            multi_press_timeout: Zeitfenster für Multi-Press in Sekunden (default: 0.8s)
            hold_threshold: Mindest-Haltedauer in Sekunden, ab der ein Druck als
                            "Halten" (Sync) gilt (default: 1.0s)
        """
        self.button_pin = button_pin
        self.multi_press_timeout = multi_press_timeout
        self.hold_threshold = hold_threshold
        self.press_count = 0
        self.timer = None
        self.lock = threading.Lock()
        self.is_processing = False
        self._press_start_time = None
        self.sync_manager = SyncManager(auto_sync_on_start=False)

        if HAS_GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            # Beide Flanken überwachen, um zwischen kurzem Druck und Halten
            # unterscheiden zu können
            GPIO.add_event_detect(self.button_pin, GPIO.BOTH,
                                callback=self._on_edge, bouncetime=50)
            print(f"✅ Button-Handler initialisiert auf GPIO Pin {self.button_pin}")
        else:
            print("⚠️ GPIO nicht verfügbar - Button-Handler im Demo-Modus")

    def _on_edge(self, channel):
        """Callback bei jeder Flanke - unterscheidet Drücken und Loslassen."""
        if not HAS_GPIO:
            return
        # PUD_UP: LOW = gedrückt, HIGH = losgelassen
        pressed = (GPIO.input(self.button_pin) == GPIO.LOW)
        if pressed:
            self._button_down()
        else:
            self._button_up()

    def _button_down(self):
        """Button wurde heruntergedrückt - merke Startzeit."""
        with self.lock:
            if self.is_processing:
                return
            self._press_start_time = time.time()

    def _button_up(self):
        """Button wurde losgelassen - entscheidet Halten vs. Press-Zählung."""
        with self.lock:
            if self.is_processing:
                return
            if self._press_start_time is None:
                return

            duration = time.time() - self._press_start_time
            self._press_start_time = None

            # Langes Halten → Sync (laufende Press-Zählung verwerfen)
            if duration >= self.hold_threshold:
                if self.timer is not None:
                    self.timer.cancel()
                    self.timer = None
                self.press_count = 0
                print(f"\n🔘 Halten erkannt ({duration:.1f}s) - Starte Sync...")
                self.is_processing = True
                threading.Thread(target=self._run_locked, args=(self.sync_database,), daemon=True).start()
                return

            # Kurzer Druck → als Press zählen
            self.press_count += 1
            if self.timer is not None:
                self.timer.cancel()
                print(f"🔘 Press #{self.press_count} - warte auf weitere...")
            else:
                print(f"🔘 Button gedrückt - warte {self.multi_press_timeout}s auf weitere Presses...")

            self.timer = threading.Timer(self.multi_press_timeout, self.handle_press)
            self.timer.start()

    def _run_locked(self, func):
        """Führt func aus und setzt danach is_processing zurück.

        is_processing wird vom Aufrufer bereits gesetzt; hier nur Cleanup.
        """
        try:
            func()
        finally:
            with self.lock:
                self.is_processing = False
            print("\n⏳ Bereit für nächsten Input...\n")

    def handle_press(self):
        """Nach dem Timeout - entscheidet Einzel/Doppel/Dreifach-Press."""
        with self.lock:
            if self.is_processing:
                return

            press_count = self.press_count
            self.press_count = 0
            self.timer = None
            self.is_processing = True

        try:
            # Prüfe Kamera-Verfügbarkeit
            camera_available = check_camera_available()

            if press_count == 1:
                # Einzel-Press → Enroll
                print("\n🔘 Einzel-Press erkannt - Starte Enroll...")
                if camera_available:
                    enroll_person()
                else:
                    print("⚠️ Enroll übersprungen - keine Kamera erkannt")
                    print("   Enroll benötigt eine echte Kamera (kein Demo-Modus möglich).")
            elif press_count == 2:
                # Doppel-Press → Identify
                print("\n🔘🔘 Doppel-Press erkannt - Starte Identify...")
                if camera_available:
                    identify_person()
                else:
                    print("⚠️ Kamera nicht verfügbar - Wechsle zu Demo Identify Mode...")
                    if DEMO_AVAILABLE:
                        demo_identify_mode()
                    else:
                        print("❌ Demo-Modus nicht verfügbar")
            elif press_count >= 3:
                # Dreifach-Press → Rizz Mode
                print("\n🔘🔘🔘 Dreifach-Press erkannt - Starte Rizz Mode...")
                self._rizz()
        except Exception as e:
            print(f"❌ Fehler bei der Verarbeitung: {e}")
        finally:
            with self.lock:
                self.is_processing = False
            print("\n⏳ Bereit für nächsten Button-Press...\n")

    def _rizz(self):
        """Führt Rizz Mode aus (innerhalb von handle_press, is_processing bereits gesetzt)."""
        try:
            # Versuche immer zuerst normale Erkennung, Fallback auf Yannik
            if DEMO_AVAILABLE:
                # demo_rizz_mode_with_yannik() versucht zuerst normale Erkennung,
                # fällt bei Fehlschlag auf Yannik zurück
                demo_rizz_mode_with_yannik()
            else:
                # Fallback: Versuche normale Erkennung direkt
                from src.rizz_orchestrator import run_rizz_pipeline
                run_rizz_pipeline()
        except Exception as e:
            print(f"❌ Fehler bei Rizz Mode: {e}")

    def sync_database(self):
        """Synchronisiert die lokale Datenbank mit Supabase."""
        print("\n" + "="*50)
        print("🔄 DATENBANK SYNCHRONISATION")
        print("="*50)

        # Status vor Sync anzeigen
        print("\n📊 Status vor Sync:")
        self.sync_manager.print_sync_status()

        # Sync durchführen
        if not self.sync_manager.supabase.is_connected():
            print("❌ Keine Verbindung zu Supabase!")
            print("   Prüfe Internet-Verbindung und config/.env Datei")
            return

        print("\n🔄 Starte Synchronisation...")
        success = self.sync_manager.sync_from_supabase(force=True)

        if success:
            print("\n✅ Synchronisation erfolgreich abgeschlossen!")
            print("\n📊 Status nach Sync:")
            self.sync_manager.print_sync_status()
        else:
            print("\n❌ Synchronisation fehlgeschlagen!")

        print("="*50 + "\n")

    def cleanup(self):
        """Cleanup GPIO und Timer"""
        if self.timer is not None:
            self.timer.cancel()
        if HAS_GPIO:
            GPIO.cleanup()
            print("✅ GPIO cleanup abgeschlossen")


def start_button_listener():
    """Startet den Button-Listener für Raspberry Pi"""
    global photo_capture_active

    print("🎛️ Memory Assistant - Button-Modus")
    print("=" * 50)
    print("Button:")
    print("  1x Press:  Neue Person aufnehmen (Enroll)")
    print("  2x Press:  Person identifizieren (Identify)")
    print("  3x Press:  Rizz Mode")
    print("  Halten:    Datenbank synchronisieren (Sync)")
    print("=" * 50)

    # Prüfe Kamera-Status beim Start
    from src.camera_manager import on_raspberry_pi
    camera_available = check_camera_available()
    camera_source = "Raspberry-Pi-Kamera" if on_raspberry_pi() else "Webcam (OpenCV)"
    if camera_available:
        print(f"✅ Kamera erkannt: {camera_source}")
    else:
        print(f"⚠️ Keine Kamera erkannt ({camera_source} nicht gefunden)")
        if DEMO_AVAILABLE:
            print("   → Identify & Rizz Mode laufen im Demo-Modus")
        else:
            print("   → Demo-Modus nicht verfügbar; Aufnahmen erzeugen Platzhalter-Bilder")

    print("=" * 50)
    print("\n⏳ Warte auf Input... (Ctrl+C zum Beenden)\n")

    button_handler = ButtonHandler(button_pin=17)

    # Start photo capture thread (photos every 10 seconds)
    photo_capture_active = True
    photo_thread = threading.Thread(target=photo_capture_loop, args=(10.0,), daemon=True)
    photo_thread.start()

    try:
        # Endlos-Schleife - Button wird über Interrupts (Callbacks) verarbeitet
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\n👋 Programm beendet")
        with photo_capture_lock:
            photo_capture_active = False
        button_handler.cleanup()
