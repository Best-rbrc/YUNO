"""
Test script for gender detection that also overlays a randomly chosen
friendly compliment ("Anmachspruch") per detected face.

- Blue box: Man  | shows a random compliment for men
- Magenta box: Woman | shows a random compliment for women
- Gray box: Unknown/Error

Press 'q' to quit.
"""

import cv2
import sys
import random
import time
import numpy as np
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont

from src.face_recognizer import get_recognizer, get_all_faces_from_frame
from src.gender_detector import create_gender_detector


# Funnier, but still friendly and safe-for-work pickup lines
PICKUP_LINES_MEN = [
    "Bist du ein Magnet? Weil ich fühl mich angezogen!",
    "Glaubst du an Liebe auf den ersten Blick? Soll ich nochmal reinkommen?",
    "Dein Lächeln ist besser als mein Kaffeekick!",
    "Bist du Google? Weil du alles hast, was ich suche.",
    "Wenn du eine Kartoffel wärst, wärst du eine Süßkartoffel!",
    "Ist hier ein Flughafen? Mein Herz hebt gerade ab.",
    "Du siehst aus wie 100 Euro, die ich mal verloren hab!",
]

PICKUP_LINES_WOMEN = [
    "Roses are red get into my bed",
    "Glaubst du an Liebe auf den ersten Blick? Soll ich nochmal reinkommen?",
    "Dein Lächeln ist besser als mein Kaffeekick!",
    "Bist du Google? Weil du alles hast, was ich suche.",
    "Wenn du eine Kartoffel wärst, wärst du eine Süßkartoffel!",
    "Kann ich dir beim Tragen helfen? Du trägst die ganze Zeit meine Gedanken mit dir rum.",
    "Ich heiße zwar mit Vornamen nicht farid aber würde dich trotzdem bangen",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a Unicode-capable TrueType font. Falls back gracefully."""
    candidates = [
        # Common on Linux (incl. Raspberry Pi)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        # macOS candidates
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/DejaVuSans.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        # Pillow bundled font
        "DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _ensure_pil(img_bgr):
    """Convert OpenCV BGR ndarray to PIL Image (RGB)."""
    return Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))


def _to_cv(img_pil):
    """Convert PIL Image (RGB) back to OpenCV BGR ndarray."""
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def draw_text_pil(img, text, x, y, color=(255, 255, 255), size=20, bg_color=None, padding=5):
    """Draw UTF-8 text using Pillow for proper umlaut rendering."""
    pil_img = _ensure_pil(img)
    draw = ImageDraw.Draw(pil_img)
    font = _load_font(size=size)
    
    # Convert BGR -> RGB for color
    rgb = (color[2], color[1], color[0])
    
    # Get text bounding box
    bbox = draw.textbbox((x, y), text, font=font)
    
    # Draw background if specified
    if bg_color is not None:
        bg_rgb = (bg_color[2], bg_color[1], bg_color[0])
        draw.rectangle([bbox[0] - padding, bbox[1] - padding, 
                       bbox[2] + padding, bbox[3] + padding], 
                      fill=bg_rgb)
    
    # Draw text
    draw.text((x, y), text, font=font, fill=rgb)
    
    # Convert back to OpenCV
    img[:] = _to_cv(pil_img)


def get_stable_face_key(x, y, w, h, tolerance=50):
    """
    Create a stable tracking key for a face based on center position + size.
    This allows small movements without triggering a new person.
    """
    center_x = x + w // 2
    center_y = y + h // 2
    avg_size = (w + h) // 2
    
    # Round to nearest tolerance pixels to group nearby faces
    stable_x = (center_x // tolerance) * tolerance
    stable_y = (center_y // tolerance) * tolerance
    stable_size = (avg_size // tolerance) * tolerance
    
    return f"{stable_x}_{stable_y}_{stable_size}"


def main():
    # Initialize gender detector
    print("Loading gender detector...")
    try:
        gender_detector = create_gender_detector(model_name="VGG-Face")
        if gender_detector is None:
            print("❌ Error: DeepFace is not available. Install with: pip install deepface")
            sys.exit(1)
        gender_detector.enforce_detection = False
        print("✅ Gender detector loaded successfully!")
        print(f"   Model: {gender_detector.model_name}")
    except Exception as e:
        print(f"❌ Error loading gender detector: {e}")
        sys.exit(1)

    # Initialize face recognizer for face detection
    print("Loading face recognizer...")
    try:
        face_recognizer = get_recognizer()
        print("✅ Face recognizer loaded successfully!")
    except Exception as e:
        print(f"❌ Error loading face recognizer: {e}")
        sys.exit(1)

    # Open camera (try index 0, then 1)
    print("\nOpening camera...")
    cap = None
    for camera_index in [0, 1]:
        cap = cv2.VideoCapture(camera_index)
        if cap.isOpened():
            print(f"✅ Camera opened (index {camera_index})")
            break

    if cap is None or not cap.isOpened():
        print("❌ Error: Could not open camera")
        sys.exit(1)

    # Set camera properties for better quality
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    print("\nGender detection with compliments started. Press 'q' to quit.\n")
    print("👉 Anmachsprüche wechseln alle 30 Sekunden pro Person.\n")

    frame_count = 0
    last_gender_update = {}
    gender_cache = {}
    line_cache = {}  # face_key -> {"line": str, "timestamp": float}

    # Processing settings
    GENDER_UPDATE_INTERVAL = 15
    CACHE_DURATION = 30
    LINE_CHANGE_INTERVAL = 30.0  # seconds

    try:
        current_time = time.time()
        while True:
            ret, frame = cap.read()
            if not ret:
                print("❌ Error: Could not read frame")
                break

            frame_count += 1
            current_time = time.time()
            all_faces = get_all_faces_from_frame(frame)

            for i, (face_img, (x, y, w, h)) in enumerate(all_faces):
                # Use stable key based on center position + size (tolerance 50px)
                face_key = get_stable_face_key(x, y, w, h, tolerance=50)

                # Decide if we update the gender for this region
                should_update = (
                    face_key not in last_gender_update or
                    (frame_count - last_gender_update[face_key]) >= GENDER_UPDATE_INTERVAL
                )

                # Detect gender or use cache
                if should_update:
                    try:
                        gender_result = gender_detector.detect_gender_from_array(face_img)
                        if gender_result and gender_result.get('success', False):
                            gender = gender_result.get('gender', 'Unknown')
                            confidence = gender_result.get('confidence', 0.0)
                            gender_cache[face_key] = {
                                'gender': gender,
                                'confidence': confidence,
                                'frame': frame_count
                            }
                        else:
                            if face_key not in gender_cache:
                                gender_cache[face_key] = {
                                    'gender': 'Unknown',
                                    'confidence': 0.0,
                                    'frame': frame_count
                                }
                        last_gender_update[face_key] = frame_count
                    except Exception:
                        if face_key not in gender_cache:
                            gender_cache[face_key] = {
                                'gender': 'Error',
                                'confidence': 0.0,
                                'frame': frame_count
                            }

                # Draw box and labels
                if face_key in gender_cache and (frame_count - gender_cache[face_key]['frame']) <= CACHE_DURATION:
                    gender = gender_cache[face_key]['gender']
                    confidence = gender_cache[face_key]['confidence']

                    if gender == 'Man':
                        color = (255, 0, 0)
                        label = f"Man ({confidence:.1f}%)"
                        
                        # Assign or refresh compliment (only change every 30s)
                        if face_key not in line_cache:
                            line_cache[face_key] = {
                                "line": random.choice(PICKUP_LINES_MEN),
                                "timestamp": current_time
                            }
                        elif current_time - line_cache[face_key]["timestamp"] > LINE_CHANGE_INTERVAL:
                            # Time to refresh
                            line_cache[face_key] = {
                                "line": random.choice(PICKUP_LINES_MEN),
                                "timestamp": current_time
                            }
                        compliment = line_cache[face_key]["line"]
                        
                    elif gender == 'Woman':
                        color = (255, 0, 255)
                        label = f"Woman ({confidence:.1f}%)"
                        
                        # Assign or refresh compliment (only change every 30s)
                        if face_key not in line_cache:
                            line_cache[face_key] = {
                                "line": random.choice(PICKUP_LINES_WOMEN),
                                "timestamp": current_time
                            }
                        elif current_time - line_cache[face_key]["timestamp"] > LINE_CHANGE_INTERVAL:
                            # Time to refresh
                            line_cache[face_key] = {
                                "line": random.choice(PICKUP_LINES_WOMEN),
                                "timestamp": current_time
                            }
                        compliment = line_cache[face_key]["line"]
                        
                    else:
                        color = (128, 128, 128)
                        label = gender
                        compliment = None

                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                    draw_text_pil(frame, label, x, max(y - 30, 10), color=color, size=20)

                    # Draw compliment below the face box if available
                    if compliment:
                        # Calculate position below face
                        text_y = y + h + 10
                        # Draw with black background for readability
                        draw_text_pil(frame, compliment, x + 5, text_y, 
                                    color=(255, 255, 255), size=16, 
                                    bg_color=(0, 0, 0), padding=5)
                else:
                    # Processing placeholder
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    draw_text_pil(frame, "Processing...", x, max(y - 30, 10), 
                                color=(0, 255, 0), size=18)

            # Clean caches
            expired = [key for key, entry in gender_cache.items() if (frame_count - entry['frame']) > CACHE_DURATION]
            for key in expired:
                gender_cache.pop(key, None)
                last_gender_update.pop(key, None)
                line_cache.pop(key, None)

            # HUD
            detected_genders = defaultdict(int)
            for entry in gender_cache.values():
                if (frame_count - entry['frame']) <= CACHE_DURATION:
                    detected_genders[entry['gender']] += 1

            stats_text = f"Faces: {len(all_faces)}"
            if detected_genders:
                gender_stats = ", ".join([f"{k}: {v}" for k, v in detected_genders.items()])
                stats_text += f" | {gender_stats}"
            draw_text_pil(frame, stats_text, 10, 10, color=(255, 255, 255), size=20, 
                         bg_color=(0, 0, 0), padding=5)

            # Show
            cv2.imshow('Gender + Compliments', frame)

            # Quit on 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("\n✅ Camera released. Exiting.")


if __name__ == "__main__":
    main()
