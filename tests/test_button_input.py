#!/usr/bin/env python3
"""
Button-Input Test / Logger
==========================

Loggt jede Button-Geste, OHNE eine Aktion (Enroll/Identify/Rizz/Sync) auszulösen.
So lässt sich prüfen, ob 1x/2x/3x-Druck und Halten korrekt erkannt werden.

Die Erkennungs-Parameter sind identisch zu src/input_handler.ButtonHandler:
    multi_press_timeout = 0.8 s   (Zeitfenster für Mehrfach-Druck)
    hold_threshold      = 1.0 s   (ab hier gilt ein Druck als "Halten")

Geste → erwartete echte Aktion:
    1x Press  → Enroll
    2x Press  → Identify
    3x Press  → Rizz Mode
    Halten    → Sync

Verwendung:
    # Auf dem Raspberry Pi (echter Button an GPIO 17):
    python tests/test_button_input.py

    # Auf Mac/PC ohne GPIO (ENTER-Simulator):
    python tests/test_button_input.py --sim

    # Anderer Pin:
    python tests/test_button_input.py --pin 27
"""

import argparse
import sys
import threading
import time

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    GPIO = None
    HAS_GPIO = False


def _ts() -> str:
    """Zeitstempel mit Millisekunden für die Logs."""
    return time.strftime("%H:%M:%S") + f".{int((time.time() % 1) * 1000):03d}"


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


# Geste-Name → echte Aktion (nur zur Info im Log)
ACTION_FOR = {
    1: "Enroll",
    2: "Identify",
    3: "Rizz Mode",
}


class ButtonGestureLogger:
    """Erkennt Druck-Gesten und loggt sie (gleiche Logik wie ButtonHandler)."""

    def __init__(self, multi_press_timeout: float = 0.8, hold_threshold: float = 1.0):
        self.multi_press_timeout = multi_press_timeout
        self.hold_threshold = hold_threshold
        self.press_count = 0
        self.timer = None
        self._press_start_time = None
        self.lock = threading.Lock()

    # ----- Roh-Events vom Button (oder Simulator) -----
    def button_down(self) -> None:
        """Button heruntergedrückt - Startzeit merken."""
        with self.lock:
            self._press_start_time = time.time()
        _log("⬇️  Button DOWN")

    def button_up(self) -> None:
        """Button losgelassen - Halten vs. Press-Zählung entscheiden."""
        with self.lock:
            if self._press_start_time is None:
                return
            duration = time.time() - self._press_start_time
            self._press_start_time = None

            _log(f"⬆️  Button UP  (Dauer: {duration:.2f}s)")

            # Langes Halten → Sync (laufende Zählung verwerfen)
            if duration >= self.hold_threshold:
                if self.timer is not None:
                    self.timer.cancel()
                    self.timer = None
                self.press_count = 0
                _log(f"🟣 GESTE: HALTEN ({duration:.2f}s)  →  Aktion: Sync")
                _log("-" * 50)
                return

            # Kurzer Druck → zählen, Timer (neu) starten
            self.press_count += 1
            if self.timer is not None:
                self.timer.cancel()
            _log(f"   kurzer Druck gezählt → press_count = {self.press_count} "
                 f"(warte {self.multi_press_timeout}s auf weitere)")
            self.timer = threading.Timer(self.multi_press_timeout, self._finalize)
            self.timer.start()

    def _finalize(self) -> None:
        """Nach Ablauf des Zeitfensters - endgültige Geste loggen."""
        with self.lock:
            count = self.press_count
            self.press_count = 0
            self.timer = None

        if count <= 0:
            return

        names = {1: "EINZEL-PRESS", 2: "DOPPEL-PRESS", 3: "DREIFACH-PRESS"}
        gesture = names.get(count, f"{count}x-PRESS")
        action = ACTION_FOR.get(count if count <= 3 else 3, "Rizz Mode")
        symbol = {1: "🟢", 2: "🟡", 3: "🔵"}.get(count, "⚪")
        _log(f"{symbol} GESTE: {gesture} ({count}x)  →  Aktion: {action}")
        _log("-" * 50)


def run_gpio(pin: int) -> None:
    """Echter Button über GPIO (Raspberry Pi).

    Phantom-Edge Schutz:
      Auf Pi 5 (lgpio-Backend) feuert add_event_detect manchmal direkt nach
      Init einen "Phantom"-Edge, der den ersten echten Press verschluckt.
      Wir lösen das mit:
        1. 300ms Grace-Period nach Setup, bevor wir Events akzeptieren.
        2. Falls trotzdem ein einsamer UP-Edge ohne vorheriges DOWN
           kommt, behandeln wir ihn als kurzen Press (start_time = now).
    """
    logger = ButtonGestureLogger()

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    # Grace-Period: Phantom-Edges direkt nach Setup ignorieren
    ready_at = time.time() + 0.3

    def on_edge(channel):
        if time.time() < ready_at:
            _log("⏭️  (Phantom-Edge bei Init ignoriert)")
            return
        # PUD_UP: LOW = gedrückt, HIGH = losgelassen
        if GPIO.input(pin) == GPIO.LOW:
            logger.button_down()
        else:
            # Falls UP ohne DOWN kommt (Bounce hat DOWN verschluckt) →
            # als Press werten: start_time auf jetzt setzen, ergibt 0s Dauer
            with logger.lock:
                if logger._press_start_time is None:
                    _log("⚠️  UP ohne DOWN — synthetisiere Press")
                    logger._press_start_time = time.time()
            logger.button_up()

    GPIO.add_event_detect(pin, GPIO.BOTH, callback=on_edge, bouncetime=50)

    _log(f"✅ GPIO-Modus aktiv – Button an GPIO {pin} (BCM)")
    _log(f"   (Phantom-Edge Schutz: 300ms Grace-Period + UP-without-DOWN handling)")
    _log("Drücke den Button: 1x / 2x / 3x / Halten. Strg+C zum Beenden.")
    _log("-" * 50)
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        _log("\n👋 Beendet")
    finally:
        GPIO.cleanup()


def run_sim() -> None:
    """Tasten-Simulator (Mac/PC ohne GPIO).

    Ein echter Taster geht nach dem Drücken automatisch wieder hoch, daher
    ist EIN Tastendruck = EIN kompletter, kurzer Press (down+up automatisch).
    Die reale Zeit ZWISCHEN den Tastendrücken steuert die Mehrfach-Erkennung
    (innerhalb von 0.8s = Doppel/Dreifach). Halten kann ein Terminal nicht
    aus der Tastendauer messen – dafür gibt es den Befehl 'h'.
    """
    logger = ButtonGestureLogger()

    def quick_tap() -> None:
        """Ein kompletter, kurzer Press – der Taster geht automatisch hoch."""
        logger.button_down()
        logger.button_up()  # sofort wieder hoch (≈ 0s Druckdauer)

    def simulated_hold(seconds: float = 1.5) -> None:
        """Simuliert einen langen Druck (Taster wird `seconds` gehalten)."""
        logger.button_down()
        # Druck-Startzeit künstlich zurücksetzen, um die Haltedauer abzubilden
        with logger.lock:
            logger._press_start_time = time.time() - seconds
        logger.button_up()

    _log("🖥️  Simulations-Modus (kein GPIO)")
    print("\nAnleitung (ein Taster geht automatisch wieder hoch):")
    print("  • ENTER            = 1 kurzer Press")
    print("  • schnell 2–3x ENTER (jeweils <0.8s) = Doppel-/Dreifach-Press")
    print("  • 'h' + ENTER      = Halten (Sync)")
    print("  • Strg+C           = Beenden\n")

    try:
        while True:
            cmd = input("   [ENTER = Press, 'h' = Halten] ").strip().lower()
            if cmd == "h":
                simulated_hold()
            else:
                quick_tap()
    except (KeyboardInterrupt, EOFError):
        _log("\n👋 Beendet")


def main() -> None:
    parser = argparse.ArgumentParser(description="Button-Gesten loggen (ohne Aktionen auszulösen)")
    parser.add_argument("--pin", type=int, default=17, help="GPIO Pin (BCM), Standard: 17")
    parser.add_argument("--sim", action="store_true", help="ENTER-Simulator erzwingen (kein GPIO)")
    args = parser.parse_args()

    print("=" * 50)
    print("🔘 Button-Input Test / Logger")
    print("=" * 50)

    if args.sim or not HAS_GPIO:
        if not HAS_GPIO and not args.sim:
            _log("⚠️ RPi.GPIO nicht verfügbar → wechsle in Simulations-Modus")
        run_sim()
    else:
        run_gpio(args.pin)


if __name__ == "__main__":
    main()
