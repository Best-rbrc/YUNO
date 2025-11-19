"""
Test script for gender detection on a pre-recorded video file.
Overlays gender detection boxes and pickup lines ("Anmachsprüche").

- Blue box: Man  | shows a random pickup line for men
- Magenta box: Woman | shows a random pickup line for women
- Gray box: Unknown/Error

Usage:
    python test_gender_video.py <path_to_video_file> [-o OUTPUT.mp4]

Options:
    -o, --out   Save processed video with overlays to this MP4 file.

Controls:
    q       Quit
    SPACE   Pause/Resume
"""

import cv2
import sys
import random
import time
import argparse
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
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Gender detection on video with pickup lines overlay")
    parser.add_argument("video", help="Path to input video file")
    parser.add_argument("-o", "--out", dest="out_path", help="Save processed video to this MP4 file")
    args = parser.parse_args()

    video_path = args.video
    
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

    # Open video file
    print(f"\nOpening video file: {video_path}")
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"❌ Error: Could not open video file: {video_path}")
        sys.exit(1)
    
    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0
    
    print(f"✅ Video opened successfully!")
    print(f"   Resolution: {width}x{height}")
    print(f"   FPS: {fps:.2f}")
    print(f"   Frames: {total_frames}")
    print(f"   Duration: {duration:.2f} seconds")

    # Optional video writer
    writer = None
    if args.out_path:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        target_fps = fps if fps and fps > 0 else 25.0
        writer = cv2.VideoWriter(args.out_path, fourcc, target_fps, (width, height))
        if writer.isOpened():
            print(f"📝 Saving processed video to: {args.out_path}")
        else:
            print(f"⚠️ Could not open writer for: {args.out_path}. Continuing without saving.")
            writer = None

    print("\nGender detection with pickup lines started.")
    print("👉 Press 'q' to quit, SPACE to pause/resume.\n")
    print("👉 Anmachsprüche bleiben pro Person ~30 Sekunden stabil.\n")

    frame_count = 0
    # Time-based tracking to improve stability
    last_gender_update_time = {}  # face_key -> time of last gender inference
    gender_cache = {}            # face_key -> {'gender','confidence','last_seen_time'}
    line_cache = {}              # face_key -> {'line','assigned_at','last_seen'}
    paused = False

    # Processing settings (time-based where possible)
    FACE_KEY_TOLERANCE = 100            # pixels (more tolerant for video motion)
    GENDER_UPDATE_INTERVAL_S = 0.5      # re-run gender every 0.5s per face
    CACHE_DURATION_S = 5.0              # keep gender cache if face disappears briefly
    LINE_CHANGE_INTERVAL_S = 30.0       # keep same pickup line for ~30s per person
    LINE_PERSIST_S = 10.0               # keep assigned line up to 10s after face disappears

    try:
        start_time = time.time()
        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    print("\n✅ End of video reached.")
                    break

                frame_count += 1
                current_time = time.time()
                all_faces = get_all_faces_from_frame(frame)

                for i, (face_img, (x, y, w, h)) in enumerate(all_faces):
                    # Use stable key based on center position + size (more tolerant)
                    face_key = get_stable_face_key(x, y, w, h, tolerance=FACE_KEY_TOLERANCE)

                    # Decide if we update the gender for this region (time-based)
                    should_update = (
                        face_key not in last_gender_update_time or
                        (current_time - last_gender_update_time[face_key]) >= GENDER_UPDATE_INTERVAL_S
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
                                    'last_seen_time': current_time,
                                }
                            else:
                                if face_key not in gender_cache:
                                    gender_cache[face_key] = {
                                        'gender': 'Unknown',
                                        'confidence': 0.0,
                                        'last_seen_time': current_time,
                                    }
                            last_gender_update_time[face_key] = current_time
                        except Exception:
                            if face_key not in gender_cache:
                                gender_cache[face_key] = {
                                    'gender': 'Error',
                                    'confidence': 0.0,
                                    'last_seen_time': current_time,
                                }

                    # Mark last seen for active faces
                    if face_key in gender_cache:
                        gender_cache[face_key]['last_seen_time'] = current_time

                    # Draw box and labels
                    if face_key in gender_cache and (current_time - gender_cache[face_key]['last_seen_time']) <= CACHE_DURATION_S:
                        gender = gender_cache[face_key]['gender']
                        confidence = gender_cache[face_key]['confidence']

                        if gender == 'Man':
                            color = (255, 0, 0)
                            label = f"Man ({confidence:.1f}%)"
                            
                            # Assign or refresh compliment (only change every 30s)
                            if face_key not in line_cache:
                                line_cache[face_key] = {
                                    "line": random.choice(PICKUP_LINES_MEN),
                                    "assigned_at": current_time,
                                    "last_seen": current_time,
                                }
                            elif current_time - line_cache[face_key]["assigned_at"] > LINE_CHANGE_INTERVAL_S:
                                # Time to refresh
                                line_cache[face_key] = {
                                    "line": random.choice(PICKUP_LINES_MEN),
                                    "assigned_at": current_time,
                                    "last_seen": current_time,
                                }
                            compliment = line_cache[face_key]["line"]
                            line_cache[face_key]["last_seen"] = current_time
                            
                        elif gender == 'Woman':
                            color = (255, 0, 255)
                            label = f"Woman ({confidence:.1f}%)"
                            
                            # Assign or refresh compliment (only change every 30s)
                            if face_key not in line_cache:
                                line_cache[face_key] = {
                                    "line": random.choice(PICKUP_LINES_WOMEN),
                                    "assigned_at": current_time,
                                    "last_seen": current_time,
                                }
                            elif current_time - line_cache[face_key]["assigned_at"] > LINE_CHANGE_INTERVAL_S:
                                # Time to refresh
                                line_cache[face_key] = {
                                    "line": random.choice(PICKUP_LINES_WOMEN),
                                    "assigned_at": current_time,
                                    "last_seen": current_time,
                                }
                            compliment = line_cache[face_key]["line"]
                            line_cache[face_key]["last_seen"] = current_time
                            
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

                # Clean caches (time-based)
                expired_gender = [key for key, entry in gender_cache.items() if (current_time - entry['last_seen_time']) > CACHE_DURATION_S]
                for key in expired_gender:
                    gender_cache.pop(key, None)
                    last_gender_update_time.pop(key, None)

                # Remove pickup lines only if face hasn't been seen for a while
                expired_lines = [key for key, entry in line_cache.items() if (current_time - entry.get('last_seen', current_time)) > LINE_PERSIST_S]
                for key in expired_lines:
                    line_cache.pop(key, None)

                # HUD - Top stats
                detected_genders = defaultdict(int)
                for entry in gender_cache.values():
                    if (current_time - entry['last_seen_time']) <= CACHE_DURATION_S:
                        detected_genders[entry['gender']] += 1

                stats_text = f"Faces: {len(all_faces)}"
                if detected_genders:
                    gender_stats = ", ".join([f"{k}: {v}" for k, v in detected_genders.items()])
                    stats_text += f" | {gender_stats}"
                draw_text_pil(frame, stats_text, 10, 10, color=(255, 255, 255), size=20, 
                             bg_color=(0, 0, 0), padding=5)
                
                # HUD - Bottom video progress
                progress = (frame_count / total_frames) * 100 if total_frames > 0 else 0
                elapsed = time.time() - start_time
                video_time = frame_count / fps if fps > 0 else 0
                progress_text = f"Frame {frame_count}/{total_frames} ({progress:.1f}%) | Time: {video_time:.1f}s / {duration:.1f}s"
                draw_text_pil(frame, progress_text, 10, height - 40, 
                             color=(255, 255, 255), size=18, 
                             bg_color=(0, 0, 0), padding=5)

            # Show frame (whether paused or not)
            if paused:
                # Add "PAUSED" indicator
                draw_text_pil(frame, "PAUSED", width // 2 - 60, height // 2 - 20, 
                             color=(0, 255, 255), size=30, 
                             bg_color=(0, 0, 0), padding=10)
            
            cv2.imshow('Gender + Pickup Lines (Video)', frame)

            # Save to output if enabled
            if writer is not None and not paused:
                writer.write(frame)

            # Key handling
            key = cv2.waitKey(30 if not paused else 100) & 0xFF
            if key == ord('q'):
                print("\n⚠️ Quit requested by user")
                break
            elif key == ord(' '):  # SPACE bar
                paused = not paused
                print(f"{'⏸️  Paused' if paused else '▶️  Resumed'}")

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    finally:
        cap.release()
        if writer is not None:
            writer.release()
        cv2.destroyAllWindows()
        print("\n✅ Video released. Exiting.")


if __name__ == "__main__":
    main()
