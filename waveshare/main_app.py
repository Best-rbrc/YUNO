"""
Combined Landing Screen + Slideshow for Yuno
Displays landing screen on startup, switches to slideshow on button press via MQTT.

Controls:
- Any button press on landing screen → Start slideshow
- LEFT joystick in slideshow → Previous image
- RIGHT joystick in slideshow → Next image
- DOWN joystick in slideshow → Toggle name on Arduino LCD
- UP joystick in slideshow → Text-to-Speech reads context
"""
import time
import threading
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import adafruit_blinka_raspberry_pi5_piomatter as pm
import paho.mqtt.client as mqtt
import pyttsx3
import os
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI as _OpenAIClient
import tempfile
import subprocess
import shutil
import signal
try:
    # Optional: reuse existing OpenAI client config
    from src.openai_api import client as openai_client
    from src.openai_api import generate_speech_audio as openai_tts_generate
except Exception:
    openai_client = None
    openai_tts_generate = None

# Fallback: try to initialize OpenAI client here if import failed
if openai_client is None:
    try:
        # Load .env from common locations
        env_path = find_dotenv(filename=".env") or find_dotenv(filename="config/.env")
        if env_path:
            load_dotenv(env_path)
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            openai_client = _OpenAIClient(api_key=api_key)
            print("✅ OpenAI client initialized via local fallback.")
        else:
            print("ℹ️ OPENAI_API_KEY not found in environment.")
    except Exception as e:
        print(f"⚠️ Failed to initialize OpenAI client: {e}")

# Local imports
from data_loader import DataLoader
from pixel_art_generator import PixelArtGenerator


# ── Display Configuration ─────────────────────────────────────────────────────
W, H       = 64, 64
ADDR       = 5
LANES      = 2
PINOUT     = pm.Pinout.Active3BGR
BRIGHTNESS = 180
FPS        = 30
FRAME_DT   = 1.0 / FPS

# ── MQTT Configuration ────────────────────────────────────────────────────────
BROKER = "localhost"
TOPIC = "arduino/to/pi"


# ── Global State ──────────────────────────────────────────────────────────────
class AppState:
    def __init__(self):
        self.mode = "landing"  # "landing" or "slideshow"
        self.running = True
        self.slideshow_idx = 0
        self.slideshow_change_requested = False
        self.name_showing = False  # Track if name is currently displayed on Arduino
        self.lock = threading.Lock()
        # Pending swipe transition requested by input handler
        self._pending_transition = None  # (direction: 'left'|'right', next_idx: int)
    
    def switch_to_slideshow(self):
        with self.lock:
            if self.mode != "slideshow":
                self.mode = "slideshow"
                print("🎬 Switching to slideshow mode...")
                return True
            return False
    
    def get_mode(self):
        with self.lock:
            return self.mode
    
    def next_image(self, total_images):
        with self.lock:
            if total_images > 0:
                self.slideshow_idx = (self.slideshow_idx + 1) % total_images
                self.slideshow_change_requested = True
                print(f"➡️  Next image: {self.slideshow_idx + 1}/{total_images}")
    
    def prev_image(self, total_images):
        with self.lock:
            if total_images > 0:
                self.slideshow_idx = (self.slideshow_idx - 1) % total_images
                self.slideshow_change_requested = True
                print(f"⬅️  Previous image: {self.slideshow_idx + 1}/{total_images}")
    
    def get_slideshow_idx(self):
        with self.lock:
            return self.slideshow_idx
    
    def check_and_reset_change_flag(self):
        with self.lock:
            flag = self.slideshow_change_requested
            self.slideshow_change_requested = False
            return flag
    
    def set_name_showing(self, showing: bool):
        with self.lock:
            self.name_showing = showing
    
    def is_name_showing(self) -> bool:
        with self.lock:
            return self.name_showing
    
    def stop(self):
        with self.lock:
            self.running = False

    def request_transition(self, direction: str, next_idx: int):
        with self.lock:
            self._pending_transition = (direction, next_idx)

    def pop_transition(self):
        with self.lock:
            t = self._pending_transition
            self._pending_transition = None
            return t


state = AppState()


# ── Hardware Mapping ──────────────────────────────────────────────────────────
def map_interleave_columns_no_transform(w, h, lanes):
    lane_w = w // lanes
    lane_pixels = (w * h) // lanes
    out = np.empty(w * h, dtype=np.uint32)
    for y in range(h):
        for x in range(w):
            lane = x % lanes
            x_l = x // lanes
            phys = lane * lane_pixels + y * lane_w + x_l
            out[y * w + x] = phys
    return out.tolist()


def flush_black(fb, device, frames=3, delay=0.015):
    fb.fill(0)
    for _ in range(frames):
        device.show()
        time.sleep(delay)


def apply_brightness_inplace(dst_fb: np.ndarray, src_img: Image.Image, brightness: int):
    if isinstance(src_img, Image.Image):
        arr = np.asarray(src_img, dtype=np.uint16)
    else:
        arr = src_img.astype(np.uint16)
    
    if brightness < 255:
        arr = (arr * brightness) // 255
    np.copyto(dst_fb, arr.astype(np.uint8), casting="no")


def swipe_transition(device, fb, current_arr: np.ndarray, next_arr: np.ndarray, direction: str, steps: int = 10, fps: int = 45):
    """Perform a horizontal swipe between two 64x64 RGB arrays."""
    frame_dt = 1.0 / max(1, fps)
    for i in range(steps + 1):
        t = i / steps
        shift = int(t * W)
        frame = np.zeros_like(current_arr)
        if direction == 'left':
            if shift < W:
                frame[:, :W-shift] = current_arr[:, shift:]
            if shift > 0:
                frame[:, W-shift:] = next_arr[:, :shift]
        else:
            if shift < W:
                frame[:, shift:] = current_arr[:, :W-shift]
            if shift > 0:
                frame[:, :shift] = next_arr[:, W-shift:]
        apply_brightness_inplace(fb, frame, BRIGHTNESS)
        device.show()
        time.sleep(frame_dt)


def tint_image(arr: np.ndarray, tint_rgb: tuple, alpha: float) -> np.ndarray:
    """Blend image with a solid tint color: out = (1-alpha)*img + alpha*tint."""
    img16 = arr.astype(np.uint16)
    tint = np.zeros_like(arr, dtype=np.uint16)
    tint[..., 0] = tint_rgb[0]
    tint[..., 1] = tint_rgb[1]
    tint[..., 2] = tint_rgb[2]
    a_num = int(alpha * 255)
    out = ((img16 * (255 - a_num)) + (tint * a_num)) // 255
    return out.astype(np.uint8)


# ── Landing Screen Functions ──────────────────────────────────────────────────
title_text = "Yuno"
tagline = "Smart Person Recognition & Database"
prompt = "Press any button to start Practicing names"

try:
    title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
    subtitle_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 12)
    prompt_font = ImageFont.truetype("DejaVuSans.ttf", 7)
except Exception:
    title_font = ImageFont.load_default()
    subtitle_font = ImageFont.load_default()
    prompt_font = ImageFont.load_default()

big_colors = [
    (255, 128, 255), # Pink
    (102, 200, 255), # Blue
    (255, 244, 100), # Yellow
    (120, 255, 120), # Green
    (255, 120, 180), # Magenta
    (255, 80, 80),   # Red
    (240, 240, 240), # White
]


def center(draw, text, font, y):
    try:
        w, h = draw.textbbox((0,0), text, font=font)[2:]
    except Exception:
        w, h = draw.textsize(text, font=font)
    return (W-w)//2, y


def render_landing_frame(t, phase, subtitle_scroll_x, prompt_scroll_x):
    img = Image.new("RGB", (W,H), (0,0,0))
    d = ImageDraw.Draw(img)

    # Animated title
    color_idx = int((t*2 + phase) % len(big_colors))
    title_color = big_colors[color_idx]
    fade = int(200 + 55*(0.5+0.5*np.sin(2*np.pi*t/2)))
    col = tuple(int(c*fade/255) for c in title_color)
    x_title, y_title = center(d, title_text, title_font, 4)
    d.text((x_title, y_title), title_text, fill=col, font=title_font)

    # Scrolling subtitle
    subtitle_w, subtitle_h = d.textbbox((0,0), tagline, font=subtitle_font)[2:]
    subtitle_canvas = Image.new("RGB", (subtitle_w + W, subtitle_h), (0,0,0))
    d_sub = ImageDraw.Draw(subtitle_canvas)
    d_sub.text((W//2,0), tagline, fill=(180,230,255), font=subtitle_font)
    scroll_area = subtitle_w + W
    sx = int(subtitle_scroll_x) % scroll_area
    box = (sx, 0, sx+W, subtitle_h)
    subtitle_strip = subtitle_canvas.crop(box)
    y_subtitle = 34
    img.paste(subtitle_strip, (0, y_subtitle))

    # Scrolling prompt
    prompt_w, prompt_h = d.textbbox((0,0), prompt, font=prompt_font)[2:]
    full_prompt_canvas = Image.new("RGB", (prompt_w*2, prompt_h), (0,0,0))
    d_prompt = ImageDraw.Draw(full_prompt_canvas)
    pulse = int(140+60*(0.5+0.5*np.sin(2*np.pi*t/1.4)))
    d_prompt.text((0, 0), prompt, fill=(pulse,pulse,pulse), font=prompt_font)
    d_prompt.text((prompt_w, 0), prompt, fill=(pulse,pulse,pulse), font=prompt_font)
    p_scroll_area = prompt_w
    psx = int(prompt_scroll_x) % p_scroll_area
    pbox = (psx, 0, psx+W, prompt_h)
    prompt_strip = full_prompt_canvas.crop(pbox)
    y_prompt = H - prompt_h - 1
    img.paste(prompt_strip, (0, y_prompt))

    # Animated border
    border_col = tuple(
        int(48 + 8*np.sin(np.pi*t + k)) for k in (0,2,4)
    )
    d.rectangle((0,0,W-1,H-1), outline=border_col, width=1)
    return img


# ── Slideshow Functions ───────────────────────────────────────────────────────
def load_pixel_art_images() -> Tuple[List[np.ndarray], List[dict]]:
    """Fetch persons with photos and convert each to 64x64 pixel-art arrays.
    Returns tuple of (images, person_data)."""
    loader = DataLoader()
    if not loader.is_connected():
        print("❌ Supabase not connected. Check configuration.")
        return [], []

    persons = loader.load_persons_with_photos()
    if not persons:
        print("⚠️  No persons with photos available.")
        return [], []

    generator = PixelArtGenerator(target_size=(W, H))
    images: List[np.ndarray] = []
    person_data: List[dict] = []

    for person in persons:
        name = person.get("name", "Unknown")
        local_photo = person.get("local_photo_path")
        if not local_photo:
            print(f"   ⚠️  Skipping {name}: no local photo path")
            continue

        pixel_art = generator.generate_pixel_art(local_photo, enhance=True)
        if pixel_art is None:
            print(f"   ⚠️  Failed to generate pixel art for {name}")
            continue

        images.append(pixel_art)
        person_data.append(person)
        print(f"   ✅ Prepared {name}")

    return images, person_data


# ── Text-to-Speech Setup ─────────────────────────────────────────────────────
tts_engine = None
tts_lock = threading.Lock()

def init_tts():
    """Initialize TTS engine"""
    global tts_engine
    try:
        tts_engine = pyttsx3.init()
        # Set properties (adjust for better voice)
        tts_engine.setProperty('rate', 150)    # Speed (words per minute)
        tts_engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
        
        # Try to set a female voice if available
        voices = tts_engine.getProperty('voices')
        for voice in voices:
            if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                tts_engine.setProperty('voice', voice.id)
                break
        
        print("🔊 TTS Engine initialized")
    except Exception as e:
        print(f"⚠️  TTS initialization failed: {e}")

def _sanitize_context(name: str, context: str) -> str:
    """Remove the person's name from the context (case-insensitive) and tidy spaces."""
    try:
        import re
        cleaned = context
        # Remove full name occurrences
        if name:
            name_pattern = re.escape(name)
            cleaned = re.sub(name_pattern, "", cleaned, flags=re.IGNORECASE)
            # Also remove first/last name individually
            parts = [p for p in name.split() if p]
            for p in parts:
                cleaned = re.sub(rf"\b{re.escape(p)}\b", "", cleaned, flags=re.IGNORECASE)
        # Collapse multiple spaces and tidy punctuation
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
        return cleaned
    except Exception:
        return context


def speak_context(name: str, context: str):
    """Speak person's context using TTS in a separate thread.
    Prefers high-quality cloud TTS (OpenAI) if available, otherwise falls back to pyttsx3.
    Adds a short intro and removes the person's name from the content.
    """
    def _speak():
        with tts_lock:
            try:
                # Lower background music volume during TTS
                lower_music_volume()
                try:
                    # 1) Cleanup text (LLM if available, else local sanitize)
                    safe_context = context
                    if openai_client is not None:
                        try:
                            prompt = (
                                "You will receive a person's name and a short context about them. "
                                "Rewrite the context into clean, grammatically correct English suitable for being read aloud in one to two sentences. "
                                "Do NOT include the person's name or any direct identifiers. "
                                "Keep it concise, natural, and easy to listen to.\n\n"
                                f"Name: {name}\n"
                                f"Context: {context}"
                            )
                            resp = openai_client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[
                                    {"role": "system", "content": "You are a helpful assistant that rewrites short snippets for natural text-to-speech. Only output the rewritten text."},
                                    {"role": "user", "content": prompt},
                                ],
                                temperature=0.2,
                                max_tokens=120,
                            )
                            candidate = resp.choices[0].message.content.strip()
                            if candidate:
                                safe_context = candidate
                                print("✅ LLM cleanup used for TTS text.")
                            else:
                                safe_context = _sanitize_context(name, context)
                                print("⚠️ LLM returned empty text. Falling back to local sanitizer.")
                        except Exception:
                            safe_context = _sanitize_context(name, context)
                            print("⚠️ LLM cleanup failed. Using local sanitizer.")
                    else:
                        safe_context = _sanitize_context(name, context)
                        print("ℹ️ LLM not configured. Using local sanitizer.")

                    intro = "Here is some quick context."
                    text = f"{intro} {safe_context}"
                    print("🗣️ TTS will say:\n" + text)

                    # 2) Try multiple TTS options in order of quality
                    
                    # Option A: OpenAI TTS (nova voice - very natural, female-like)
                    if openai_client is not None and openai_tts_generate is not None:
                        try:
                            audio_bytes = openai_tts_generate(text, voice="nova")  # Very natural female voice
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                                tmp.write(audio_bytes)
                                tmp_path = tmp.name
                            # Try multiple audio players
                            for player in ["mpg123", "mpv", "aplay", "ffplay"]:
                                try:
                                    if player == "aplay":
                                        # Convert to wav first for aplay
                                        subprocess.check_call(["ffmpeg", "-i", tmp_path, "-f", "wav", "-acodec", "pcm_s16le", tmp_path.replace(".mp3", ".wav")], 
                                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                        rc = subprocess.call([player, "-q", tmp_path.replace(".mp3", ".wav")])
                                    else:
                                        rc = subprocess.call([player, "-q", tmp_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                    if rc == 0:
                                        print("✅ Played with OpenAI TTS (nova voice)")
                                        os.unlink(tmp_path)
                                        return
                                except (subprocess.CalledProcessError, FileNotFoundError):
                                    continue
                            os.unlink(tmp_path)
                            print("⚠️ No audio player found. Trying alternatives...")
                        except Exception as e:
                            print(f"⚠️ OpenAI TTS failed: {e}. Trying alternatives...")
                    
                    # Option B: gTTS (Google Text-to-Speech - free, decent quality)
                    try:
                        from gtts import gTTS
                        tts_gtts = gTTS(text=text, lang='en', slow=False)
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                            tts_gtts.save(tmp.name)
                            tmp_path = tmp.name
                        for player in ["mpg123", "mpv", "ffplay"]:
                            try:
                                rc = subprocess.call([player, "-q", tmp_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                if rc == 0:
                                    print("✅ Played with gTTS")
                                    os.unlink(tmp_path)
                                    return
                            except (subprocess.CalledProcessError, FileNotFoundError):
                                continue
                        os.unlink(tmp_path)
                    except Exception as e:
                        print(f"⚠️ gTTS failed: {e}")

                    # 3) Fallback: local pyttsx3
                    if tts_engine:
                        tts_engine.say(text)
                        tts_engine.runAndWait()
                    else:
                        print("⚠️ No TTS engine available.")
                finally:
                    # Always restore music volume after TTS
                    restore_music_volume()
            except Exception as e:
                print(f"⚠️  TTS error: {e}")
                # Restore volume even on error
                restore_music_volume()

    # Run in separate thread to avoid blocking
    threading.Thread(target=_speak, daemon=True).start()


# ── MQTT Handler / Quiz Mode State ────────────────────────────────────────────
# Store total images count and person data globally so MQTT handler can access it
total_slideshow_images = 0
slideshow_person_data = []
mqtt_client = None

# Quiz queue: list of indices into slideshow_person_data
quiz_queue = []

# Background music process
bgm_proc = None

def sounds_path(filename: str) -> str:
    return os.path.join(os.path.dirname(__file__), "sounds", filename)

def start_background_music(trigger: str):
    """Start background music depending on trigger (LEFT/RIGHT/UP/DOWN/PRESS)."""
    global bgm_proc
    # Stop any existing music first
    stop_background_music()
    # Simple mapping
    if "LEFT" in trigger:
        song = sounds_path("Subway.wav")
    elif "RIGHT" in trigger:
        song = sounds_path("Espresso.wav")
    elif "DOWN" in trigger:
        song = sounds_path("Fortnite Festival.wav")
    elif "UP" in trigger or "PRESS" in trigger:
        song = sounds_path("Fortnite OG.wav")
    else:
        song = sounds_path("Juno.wav")
    try:
        # Prefer robust players that handle compressed WAV (ffplay/mpv), then mpg123 (mp3), fallback aplay
        cmd = None
        if shutil.which("ffplay"):
            cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", song]
        elif shutil.which("mpv"):
            cmd = ["mpv", "--no-video", "--really-quiet", song]
        elif song.lower().endswith(".mp3") and shutil.which("mpg123"):
            cmd = ["mpg123", "-q", song]
        elif shutil.which("aplay"):
            cmd = ["aplay", "-q", song]

        if cmd is None:
            print("⚠️  No audio player found (ffplay/mpv/mpg123/aplay). Cannot play background music.")
            return

        bgm_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"🎵 Background music started: {os.path.basename(song)} (via {cmd[0]})")
    except Exception as e:
        print(f"⚠️  Could not start background music: {e}")

def stop_background_music():
    global bgm_proc
    if bgm_proc is not None and bgm_proc.poll() is None:
        try:
            bgm_proc.terminate()
            print("⏹️  Background music stopped")
        except Exception:
            pass
    bgm_proc = None

def lower_music_volume():
    """Lower background music during TTS by pausing the player (reliable on Pi)."""
    global bgm_proc
    if bgm_proc is None or bgm_proc.poll() is not None:
        return
    try:
        os.kill(bgm_proc.pid, signal.SIGSTOP)
        print("🔇 Background music paused for TTS")
    except Exception:
        pass

def restore_music_volume():
    """Resume background music after TTS."""
    global bgm_proc
    if bgm_proc is None or bgm_proc.poll() is not None:
        return
    try:
        os.kill(bgm_proc.pid, signal.SIGCONT)
        print("🔊 Background music resumed")
    except Exception:
        pass

def init_quiz_queue():
    global quiz_queue
    quiz_queue = list(range(total_slideshow_images))
    if quiz_queue:
        state.slideshow_idx = quiz_queue[0]
    print(f"🧩 Quiz queue initialized with {len(quiz_queue)} items")

def send_name_to_arduino(name: str):
    """Send person's name to Arduino LCD via MQTT"""
    if mqtt_client:
        # Send header to top line
        mqtt_client.publish("pi/to/arduino", "NAME:Person's Name")
        time.sleep(0.05)  # Small delay between messages
        # Send actual name to bottom line
        mqtt_client.publish("pi/to/arduino", f"DESC:{name}")
        print(f"📤 Sent to Arduino: {name}")

def reset_arduino_display():
    """Reset Arduino LCD to default YUNO screen"""
    if mqtt_client:
        mqtt_client.publish("pi/to/arduino", "NAME:YUNO")
        time.sleep(0.05)
        mqtt_client.publish("pi/to/arduino", "DESC:Smart Learning")
        print(f"🔄 Reset Arduino to YUNO screen")

def on_message(client, userdata, msg):
    message = msg.payload.decode().strip().upper()
    print(f"🎮 MQTT event: {message}")
    
    current_mode = state.get_mode()
    
    if current_mode == "landing":
        # Any button press → switch to slideshow (quiz mode)
        if state.switch_to_slideshow():
            init_quiz_queue()
            start_background_music(message)
    elif current_mode == "slideshow":
        # LEFT/RIGHT joystick → quiz progression
        if "LEFT" in message:
            # Didn't know the name → send current to back of queue, request swipe left
            if quiz_queue:
                cur = quiz_queue.pop(0)
                quiz_queue.append(cur)
                nxt = quiz_queue[0]
                state.request_transition('left', nxt)
                print(f"↩️ Not known → moved index {cur} to back. Remaining: {len(quiz_queue)}")
            reset_arduino_display()
            state.set_name_showing(False)
        elif "RIGHT" in message:
            # Knew it → remove from queue; if empty, return to landing; else swipe right to next
            if quiz_queue:
                done = quiz_queue.pop(0)
                print(f"✅ Known → removed index {done}. Remaining: {len(quiz_queue)}")
                if not quiz_queue:
                    print("🎉 Quiz complete. Returning to landing screen.")
                    reset_arduino_display()
                    state.set_name_showing(False)
                    state.mode = "landing"
                    stop_background_music()
                else:
                    nxt = quiz_queue[0]
                    state.request_transition('right', nxt)
                    reset_arduino_display()
                    state.set_name_showing(False)
        elif "DOWN" in message or "UP" in message:
            # Speak person's context using TTS (both DOWN and UP)
            current_idx = state.get_slideshow_idx()
            if 0 <= current_idx < len(slideshow_person_data):
                person = slideshow_person_data[current_idx]
                name = person.get("name", "Unknown")
                context = person.get("context", "No context available")
                speak_context(name, context)
        elif "PRESS" in message:
            # Show person's name on Arduino LCD (no toggle)
            current_idx = state.get_slideshow_idx()
            if 0 <= current_idx < len(slideshow_person_data):
                person = slideshow_person_data[current_idx]
                name = person.get("name", "Unknown")
                send_name_to_arduino(name)
                state.set_name_showing(True)


def mqtt_thread():
    """Run MQTT client in separate thread"""
    global mqtt_client
    print(f"🔗 Connecting to MQTT broker at {BROKER}...")
    mqtt_client = mqtt.Client()
    mqtt_client.on_message = on_message
    
    try:
        mqtt_client.connect(BROKER, 1883, 60)
        mqtt_client.subscribe(TOPIC)
        print(f"✅ Subscribed to {TOPIC}")
        mqtt_client.loop_forever()
    except Exception as e:
        print(f"❌ MQTT connection failed: {e}")


# ── Main Application Loop ─────────────────────────────────────────────────────
def main():
    print("\n" + "="*60)
    print("🎨 Yuno Combined Landing + Slideshow")
    print("="*60)
    print(f"Config: LANES={LANES}, PINOUT={PINOUT.name}, BRIGHTNESS={BRIGHTNESS}")
    print(f"MQTT: {BROKER} → {TOPIC}")
    print("="*60 + "\n")
    
    # Initialize display hardware
    mapping = map_interleave_columns_no_transform(W, H, LANES)
    geom = pm.Geometry(W, H, ADDR, mapping, 10, 0, LANES)
    fb = np.zeros((H, W, 3), dtype=np.uint8)
    
    m = pm.PioMatter(
        colorspace=pm.Colorspace.RGB888Packed,
        pinout=PINOUT,
        framebuffer=fb,
        geometry=geom,
    )
    
    # Start MQTT listener in separate thread
    mqtt_thread_handle = threading.Thread(target=mqtt_thread, daemon=True)
    mqtt_thread_handle.start()
    time.sleep(1)  # Give MQTT time to connect
    
    # Initialize Text-to-Speech
    print("\n🔊 Initializing Text-to-Speech...")
    init_tts()
    
    # Load slideshow images
    print("\n📸 Loading slideshow images...")
    slideshow_images, person_data = load_pixel_art_images()
    global total_slideshow_images, slideshow_person_data
    total_slideshow_images = len(slideshow_images)
    slideshow_person_data = person_data
    if not slideshow_images:
        print("⚠️  No slideshow images available. Slideshow will be empty.")
    else:
        print(f"✅ Loaded {len(slideshow_images)} images\n")
    
    # Landing screen state
    t0_landing = time.monotonic()
    phase = np.random.randint(100)
    subtitle_scroll_rate = 10
    prompt_scroll_rate = 24
    
    # Track if we need to redraw slideshow
    last_displayed_idx = -1
    
    try:
        flush_black(fb, m, frames=3, delay=0.015)
        print("🚀 Application started. Press Ctrl+C to exit.\n")
        
        while state.running:
            current_mode = state.get_mode()
            
            if current_mode == "landing":
                # Render landing screen animation
                t = time.monotonic() - t0_landing
                subtitle_scroll_x = t * subtitle_scroll_rate
                prompt_scroll_x = t * prompt_scroll_rate
                img = render_landing_frame(t, phase, subtitle_scroll_x, prompt_scroll_x)
                apply_brightness_inplace(fb, img, BRIGHTNESS)
                m.show()
                time.sleep(FRAME_DT)
                
            elif current_mode == "slideshow":
                # Handle pending swipe transitions first
                transition = state.pop_transition()
                if transition and slideshow_images:
                    direction, next_idx = transition
                    cur_idx = last_displayed_idx if last_displayed_idx >= 0 else state.get_slideshow_idx()
                    cur_img = slideshow_images[cur_idx]
                    next_img = slideshow_images[next_idx]
                    # Slightly slower swipe
                    swipe_transition(m, fb, cur_img, next_img, direction=direction, steps=8, fps=50)
                    # After swipe, brief feedback tint (left=red, right=green)
                    if direction == 'left':
                        tinted = tint_image(next_img, (255, 40, 40), 0.35)
                    else:
                        tinted = tint_image(next_img, (40, 255, 40), 0.35)
                    apply_brightness_inplace(fb, tinted, BRIGHTNESS)
                    m.show()
                    time.sleep(0.15)
                    # Then show clean next image and update index
                    apply_brightness_inplace(fb, next_img, BRIGHTNESS)
                    m.show()
                    state.slideshow_idx = next_idx
                    last_displayed_idx = next_idx
                else:
                    # Get current slideshow index
                    current_idx = state.get_slideshow_idx()
                    
                    # Only redraw if index changed or first display
                    if current_idx != last_displayed_idx:
                        if slideshow_images:
                            img = slideshow_images[current_idx]
                            apply_brightness_inplace(fb, img, BRIGHTNESS)
                            m.show()
                            last_displayed_idx = current_idx
                        else:
                            # No images, show black screen
                            fb.fill(0)
                            m.show()
                
                time.sleep(0.05)  # Small delay to avoid busy loop
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Shutting down...")
    finally:
        state.stop()
        flush_black(fb, m, frames=3, delay=0.015)
        try:
            m.set_output_enabled(False)
        except Exception:
            pass
        print("✅ Display cleared. Goodbye!\n")


if __name__ == "__main__":
    main()

