"""
Input Handler - Manages button input on Raspberry Pi for enroll/identify/sync actions
"""

import time
import threading
import os
import sys
from typing import Tuple
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


# Heartbeat Sensor (KY-039) Handler
class HeartbeatSensor:
    """Erkennt Finger-Präsenz auf KY-039 als 'Button' über digitalen Eingang."""
    
    def __init__(self, sensor_gpio_pin=18, led_gpio_pin=None, debounce_ms=50):
        """
        Args:
            sensor_gpio_pin: GPIO Pin für KY-039 D0 (BCM numbering)
            led_gpio_pin: GPIO Pin für LED (BCM numbering, None = keine LED)
            debounce_ms: Entprellzeit in Millisekunden
        """
        self.sensor_pin = sensor_gpio_pin
        self.led_pin = led_gpio_pin
        self.debounce_ms = debounce_ms / 1000.0
        self._led_on = False
        self._last_state = GPIO.HIGH if HAS_GPIO else None
        self._last_read_time = 0
        self._pressed_start_time = None
        self._has_handled = False
        self.lock = threading.Lock()
        
        if not HAS_GPIO:
            print("⚠️ Heartbeat-Sensor nicht verfügbar (kein GPIO)")
            return
        
        try:
            # Prüfe ob GPIO bereits initialisiert (kann vom ButtonHandler kommen)
            try:
                current_mode = GPIO.getmode()
                if current_mode is None:
                    GPIO.setmode(GPIO.BCM)
                    print(f"💓 GPIO Mode auf BCM gesetzt")
                elif current_mode != GPIO.BCM:
                    print(f"⚠️ GPIO bereits im Mode {current_mode}, verwende BCM")
                    GPIO.setmode(GPIO.BCM)
                else:
                    print(f"💓 GPIO bereits im BCM Mode")
            except Exception as e:
                print(f"💓 GPIO Mode-Check fehlgeschlagen, setze BCM: {e}")
                GPIO.setmode(GPIO.BCM)
            
            print(f"💓 Richte Sensor Pin {self.sensor_pin} ein...")
            GPIO.setup(self.sensor_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            if self.led_pin is not None:
                print(f"💓 Richte LED Pin {self.led_pin} ein...")
                GPIO.setup(self.led_pin, GPIO.OUT, initial=GPIO.LOW)
            
            self._last_state = GPIO.input(self.sensor_pin)
            self._last_read_time = time.time()
            print(f"💓 Heartbeat-Sensor initialisiert auf GPIO Pin {self.sensor_pin}")
        except Exception as e:
            print(f"❌ Fehler bei Heartbeat-Sensor Initialisierung: {e}")
            import traceback
            traceback.print_exc()
    
    def read_sensor(self) -> Tuple[bool, float]:
        """
        Liest den Sensor-Zustand mit Entprellung.
        
        Returns:
            (finger_on: bool, duration: float) - Finger drauf und wie lange schon
        """
        if not HAS_GPIO:
            return False, 0.0
        
        current_time = time.time()
        current_state = GPIO.input(self.sensor_pin)
        
        # Zustandsänderung erkannt
        if current_state != self._last_state:
            if (current_time - self._last_read_time) >= self.debounce_ms:
                self._last_state = current_state
                self._last_read_time = current_time
                
                if current_state == GPIO.LOW:
                    # Finger wurde drauf gelegt
                    self._pressed_start_time = current_time
                    self._has_handled = False
                else:
                    # Finger wurde entfernt
                    if self._pressed_start_time is not None:
                        # Finale Dauer beim Loslassen (falls noch nicht behandelt)
                        duration = current_time - self._pressed_start_time
                        self._pressed_start_time = None
                        self._has_handled = False
                        return False, duration
                    self._pressed_start_time = None
                    self._has_handled = False
        else:
            # Gleicher Zustand - update Zeit
            self._last_read_time = current_time
        
        # Aktueller Zustand und Dauer berechnen
        finger_on = (self._last_state == GPIO.LOW)
        duration = 0.0
        if finger_on and self._pressed_start_time is not None:
            # Berechne Dauer seit Finger auf Sensor gelegt wurde
            duration = current_time - self._pressed_start_time
        
        return finger_on, duration
    
    def set_led(self, on: bool):
        """Schaltet LED ein oder aus"""
        if not HAS_GPIO or self.led_pin is None:
            return
        if on != self._led_on:
            GPIO.output(self.led_pin, GPIO.HIGH if on else GPIO.LOW)
            self._led_on = on
    
    def cleanup(self):
        """Räumt GPIO auf"""
        if HAS_GPIO and self.led_pin is not None:
            try:
                GPIO.output(self.led_pin, GPIO.LOW)
            except Exception:
                pass


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
    """Handhabt Button-Eingaben vom Raspberry Pi"""
    
    def __init__(self, button_pin=17, multi_press_timeout=0.8):
        """
        Args:
            button_pin: GPIO Pin für den Button (BCM Nummerierung)
            multi_press_timeout: Zeitfenster für Multi-Press in Sekunden (default: 0.8s)
        """
        self.button_pin = button_pin
        self.multi_press_timeout = multi_press_timeout
        self.press_count = 0
        self.timer = None
        self.lock = threading.Lock()
        self.is_processing = False
        self.sync_manager = SyncManager(auto_sync_on_start=False)
        
        if HAS_GPIO:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(self.button_pin, GPIO.FALLING, 
                                callback=self.button_pressed, bouncetime=300)
            print(f"✅ Button-Handler initialisiert auf GPIO Pin {self.button_pin}")
        else:
            print("⚠️ GPIO nicht verfügbar - Button-Handler im Demo-Modus")
    
    def button_pressed(self, channel):
        """Callback wenn Button gedrückt wird"""
        with self.lock:
            # Wenn gerade ein Enroll/Identify läuft, ignoriere weitere Presses
            if self.is_processing:
                print("⏳ Bitte warten, Verarbeitung läuft noch...")
                return
            
            self.press_count += 1
            
            # Wenn ein Timer läuft, canceln wir ihn (weil jetzt ein weiterer Press kam)
            if self.timer is not None:
                self.timer.cancel()
                print(f"🔘 Press #{self.press_count} - warte auf weitere...")
            else:
                print(f"🔘 Button gedrückt - warte {self.multi_press_timeout}s auf weitere Presses...")
            
            # Neuen Timer starten - wartet auf potentielle weitere Presses
            self.timer = threading.Timer(self.multi_press_timeout, self.handle_press)
            self.timer.start()
    
    def handle_press(self):
        """Wird nach dem Timeout aufgerufen - entscheidet ob Einzel, Doppel oder Dreifach-Press"""
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
                    print("⚠️ Kamera nicht verfügbar - Demo-Modus nicht verfügbar für Enroll")
                    print("   Bitte aktiviere die Kamera in raspi-config")
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
            # 3x Press wurde entfernt - Sync nur über Heartbeat-Sensor
        except Exception as e:
            print(f"❌ Fehler bei der Verarbeitung: {e}")
        finally:
            with self.lock:
                self.is_processing = False
            print("\n⏳ Bereit für nächsten Button-Press...\n")
    
    def _run_rizz(self):
        """Führt Rizz Mode in separatem Thread aus"""
        with self.lock:
            self.is_processing = True
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
        finally:
            with self.lock:
                self.is_processing = False
            print("\n⏳ Bereit für nächsten Input...\n")
    
    def sync_database(self):
        """Synchronisiert die lokale Datenbank mit Supabase"""
        with self.lock:
            self.is_processing = True
        try:
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
        finally:
            with self.lock:
                self.is_processing = False
            print("\n⏳ Bereit für nächsten Input...\n")
    
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
    print("=" * 50)
    print("Heartbeat-Sensor (KY-039):")
    print("  Finger auf Sensor legen:")
    print("    3-5s:  Rizz Mode")
    print("    6s+:   Datenbank synchronisieren (Sync)")
    print("=" * 50)
    
    # Prüfe Kamera-Status beim Start
    camera_available = check_camera_available()
    if camera_available:
        print("✅ Kamera verfügbar")
    else:
        print("⚠️ Kamera nicht verfügbar - Demo-Modus wird automatisch verwendet")
        print("   (Identify & Rizz Mode funktionieren im Demo-Modus)")
    
    print("=" * 50)
    print("\n⏳ Warte auf Input... (Ctrl+C zum Beenden)\n")
    
    button_handler = ButtonHandler(button_pin=17)
    
    # Initialisiere Heartbeat-Sensor
    print("💓 Initialisiere Heartbeat-Sensor (KY-039)...")
    try:
        heartbeat_sensor = HeartbeatSensor(sensor_gpio_pin=18, led_gpio_pin=None, debounce_ms=50)  # Keine LED im Button-Modus
    except Exception as e:
        print(f"❌ Heartbeat-Sensor konnte nicht initialisiert werden: {e}")
        import traceback
        traceback.print_exc()
        heartbeat_sensor = None
    
    # Start photo capture thread (photos every 10 seconds)
    photo_capture_active = True
    photo_thread = threading.Thread(target=photo_capture_loop, args=(10.0,), daemon=True)
    photo_thread.start()
    
    try:
        # Endlos-Schleife - überwache Button UND Heartbeat-Sensor
        while True:
            # Prüfe Heartbeat-Sensor (falls initialisiert)
            if heartbeat_sensor is not None:
                try:
                    finger_on, duration = heartbeat_sensor.read_sensor()
                    
                    # Wenn Finger drauf ist
                    if finger_on and not button_handler.is_processing:
                        # Erste Erkennung - nur Info
                        if duration >= 0.5 and not hasattr(heartbeat_sensor, '_detected'):
                            heartbeat_sensor._detected = True
                            print(f"💓 Finger auf Sensor erkannt... halte für 3s (Rizz) oder 6s (Sync)")
                        
                        # Nur Sync während des Drückens starten (bei 6s+)
                        if duration >= 6.0 and not hasattr(heartbeat_sensor, '_sync_triggered'):
                            # Sync Mode (6+ Sekunden) - startet sofort beim Erreichen
                            print(f"\n💓 Heartbeat-Sensor: Langdruck erkannt ({duration:.1f}s) - Starte Sync Mode...")
                            heartbeat_sensor._sync_triggered = True
                            heartbeat_sensor._rizz_triggered = True  # Verhindere Rizz
                            threading.Thread(target=button_handler.sync_database, daemon=True).start()
                    
                    # Finger weg - prüfe finale Dauer und starte Rizz nur wenn < 6s
                    elif not finger_on:
                        # Prüfe ob Finger gerade entfernt wurde (duration > 0 bedeutet es war ein Press)
                        if hasattr(heartbeat_sensor, '_detected'):
                            delattr(heartbeat_sensor, '_detected')
                            
                            # Hole die finale Dauer vom letzten read_sensor call
                            # (duration wird beim Loslassen zurückgegeben)
                            if duration > 0 and duration < 6.0 and not hasattr(heartbeat_sensor, '_sync_triggered'):
                                # Rizz Mode nur wenn < 6 Sekunden und Sync nicht gestartet
                                if duration >= 3.0 and not hasattr(heartbeat_sensor, '_rizz_triggered'):
                                    print(f"\n💓 Heartbeat-Sensor: Finger entfernt ({duration:.1f}s) - Starte Rizz Mode...")
                                    heartbeat_sensor._rizz_triggered = True
                                    threading.Thread(target=button_handler._run_rizz, daemon=True).start()
                            
                            # Reset Flags
                            if hasattr(heartbeat_sensor, '_rizz_triggered'):
                                delattr(heartbeat_sensor, '_rizz_triggered')
                            if hasattr(heartbeat_sensor, '_sync_triggered'):
                                delattr(heartbeat_sensor, '_sync_triggered')
                            
                            print(f"💓 Finger vom Sensor entfernt")
                except Exception as e:
                    print(f"⚠️ Heartbeat-Sensor Fehler: {e}")
                    import traceback
                    traceback.print_exc()
            
            time.sleep(0.01)  # 10ms = 100Hz Sampling
    except KeyboardInterrupt:
        print("\n\n👋 Programm beendet")
        with photo_capture_lock:
            photo_capture_active = False
        button_handler.cleanup()
        if heartbeat_sensor is not None:
            heartbeat_sensor.cleanup()
