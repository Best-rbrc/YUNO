import yaml
import wave
import os
import threading
import time

# Konfiguration laden
with open("config/settings.yaml", "r") as f:
    config = yaml.safe_load(f)

def record_audio(filename="data/audio/audio.wav", progress_callback=None, callback_interval=0.5):
    """
    Nimmt Audio für 'record_duration' Sekunden auf.
    Nutzt unter macOS das sounddevice-Modul (reine Python),
    auf dem Raspberry Pi das pyaudio-Modul.
    
    Args:
        filename: Pfad für die Audio-Datei
        progress_callback: Optional - Funktion die während der Aufnahme aufgerufen wird (mit elapsed time)
        callback_interval: Zeitabstand zwischen Callback-Aufrufen in Sekunden
    """
    duration = config.get("record_duration", 20)
    # Höhere Samplerate für bessere Qualität (44.1 kHz = CD-Qualität)
    # Whisper von OpenAI kann gut mit verschiedenen Samplerates umgehen
    samplerate = config.get("audio_samplerate", 44100)
    channels = 1
    
    # Optional: Spezifisches Audio-Gerät aus Config (Name oder ID)
    device_name = config.get("audio_device_name", None)
    device_id = config.get("audio_device_id", None)
    
    # Wenn Gerätename angegeben, suche die ID
    if device_name and device_id is None:
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                if device_name.lower() in device['name'].lower() and device['max_input_channels'] > 0:
                    device_id = i
                    print(f"📍 Gefunden: {device['name']} (ID: {i})")
                    break
        except Exception:
            pass
    
    # Thread für Callbacks während der Aufnahme
    stop_callbacks = threading.Event()
    
    def run_callbacks():
        """Ruft den Callback regelmäßig auf"""
        start_time = time.time()
        while not stop_callbacks.is_set() and (time.time() - start_time) < duration:
            if progress_callback:
                elapsed = time.time() - start_time
                progress_callback(elapsed)
            time.sleep(callback_interval)
    
    # Starte Callback-Thread wenn Callback angegeben
    callback_thread = None
    if progress_callback:
        callback_thread = threading.Thread(target=run_callbacks, daemon=True)
        callback_thread.start()

    # Versuche zunächst sounddevice zu importieren (Mac)
    try:
        import sounddevice as sd
        
        # Zeige verwendetes Gerät
        if device_id is not None:
            device_info = sd.query_devices(device_id)
            print(f"🎙️ Aufnahme mit: {device_info['name']}")
        else:
            print(f"🎙️ Aufnahme mit Standard-Mikrofon")
        
        print(f"   Dauer: {duration}s | Samplerate: {samplerate} Hz")
        
        audio = sd.rec(
            int(samplerate * duration), 
            samplerate=samplerate,
            channels=channels, 
            dtype='int16',
            device=device_id
        )
        sd.wait()
        stop_callbacks.set()
        
        # Audio-Pegel-Check
        import numpy as np
        audio_float = audio.astype(float) / 32768.0
        max_amplitude = np.max(np.abs(audio_float))
        
        print(f"✅ Aufnahme beendet. (Max Pegel: {max_amplitude * 100:.1f}%)")
        if max_amplitude < 0.05:
            print("⚠️  Warnung: Aufnahme sehr leise! Prüfe Mikrofon-Lautstärke.")
        # WAV speichern
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)  # 16 bit = 2 Bytes
            wf.setframerate(samplerate)
            wf.writeframes(audio.tobytes())
        return filename

    except ImportError:
        # Fallback: pyaudio verwenden (z. B. auf dem Raspberry Pi)
        import pyaudio
        p = pyaudio.PyAudio()
        
        # Finde das richtige Gerät wenn Name angegeben
        input_device_index = None
        if device_name:
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if device_name.lower() in dev['name'].lower() and dev['maxInputChannels'] > 0:
                    input_device_index = i
                    print(f"📍 Gefunden: {dev['name']} (Index: {i})")
                    break
        elif device_id is not None:
            input_device_index = device_id
        
        if input_device_index is not None:
            dev_info = p.get_device_info_by_index(input_device_index)
            print(f"🎙️ Aufnahme mit: {dev_info['name']}")
        else:
            print("🎙️ Aufnahme mit Standard-Mikrofon (pyaudio)")
        
        print(f"   Dauer: {duration}s | Samplerate: {samplerate} Hz")
        
        # Versuche Stream zu öffnen, mit Fallback auf andere Samplerates
        stream = None
        for attempt_rate in [samplerate, 48000, 44100, 16000, 8000]:
            try:
                stream = p.open(
                    format=pyaudio.paInt16, 
                    channels=channels,
                    rate=attempt_rate, 
                    input=True, 
                    frames_per_buffer=1024,
                    input_device_index=input_device_index
                )
                if attempt_rate != samplerate:
                    print(f"   ℹ️  Fallback auf {attempt_rate} Hz (Original {samplerate} Hz nicht unterstützt)")
                    samplerate = attempt_rate
                break
            except Exception as e:
                if attempt_rate == 8000:  # Letzte Option
                    raise Exception(f"Keine unterstützte Samplerate gefunden: {e}")
                continue
        
        if stream is None:
            p.terminate()
            raise Exception("Konnte Audio-Stream nicht öffnen")
        
        frames = []
        for _ in range(int(samplerate / 1024 * duration)):
            frames.append(stream.read(1024))
        stream.stop_stream()
        stream.close()
        p.terminate()
        stop_callbacks.set()
        
        print("✅ Aufnahme beendet.")
        
        # Warte auf Callback-Thread
        if callback_thread:
            callback_thread.join(timeout=1)
        
        # WAV speichern
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(samplerate)
            wf.writeframes(b''.join(frames))
        return filename
