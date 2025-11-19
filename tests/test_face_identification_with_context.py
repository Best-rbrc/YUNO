"""
Test script for face identification that also displays the stored context
for each recognized person directly on the video feed.

- Green box: recognized person, shows name + similarity + context snippet
- Yellow box: best candidate suggestion (near threshold)
- Red box: unknown

Press 'q' to quit.
"""

import cv2
import sys
from textwrap import wrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

from src.face_recognizer import get_recognizer, get_all_faces_from_frame
from src.identity_matcher import match_identity, THRESHOLD, THRESHOLD_SUGGESTION
from src.database_handler import init_db, get_person_by_id


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


def draw_label(img, text, x, y, color=(0, 255, 0), scale=0.6, thickness=2):
    """Draw a single-line UTF-8 label using Pillow so ä, ü, ß render correctly."""
    pil_img = _ensure_pil(img)
    draw = ImageDraw.Draw(pil_img)
    font = _load_font(size=int(24 * scale) or 12)
    # Convert BGR -> RGB for color
    rgb = (color[2], color[1], color[0])
    # Shadow
    draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0))
    # Foreground
    draw.text((x, y), text, font=font, fill=rgb)
    img[:] = _to_cv(pil_img)


def draw_multiline_box(img, lines, x, y, max_width_px=600, pad=8, line_scale=0.5, line_thickness=1, bg_color=(0, 0, 0), fg_color=(255, 255, 255)):
    """Draw a multiline UTF-8 text box using Pillow.
    Places the box with top-left at (x, y).
    """
    pil_img = _ensure_pil(img)
    draw = ImageDraw.Draw(pil_img)
    font = _load_font(size=int(24 * line_scale) or 12)

    # Measure text
    line_sizes = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        line_sizes.append((width, height))
    box_width = min(max((w for w, h in line_sizes), default=0) + 2 * pad, max_width_px)
    # Approx line height from font
    ascent, descent = font.getmetrics()
    line_height = ascent + descent + 4
    box_height = line_height * len(lines) + 2 * pad

    # Background box
    draw.rectangle([x, y, x + box_width, y + box_height], fill=bg_color, outline=(80, 80, 80))

    # Draw lines
    ty = y + pad
    for line in lines:
        draw.text((x + pad, ty), line, font=font, fill=fg_color)
        ty += line_height

    img[:] = _to_cv(pil_img)


def _sanitize_context(context: str) -> str:
    """Remove transcript part – show only context/analysis, not raw transcript."""
    if not context:
        return ""
    txt = context
    # Cut everything starting from a 'Transkript:' marker (case-insensitive)
    lower = txt.lower()
    marker = "transkript:"
    idx = lower.find(marker)
    if idx != -1:
        txt = txt[:idx].rstrip()
    return txt.strip()


def wrap_context(context: str, max_chars=70, max_lines=3):
    context_only = _sanitize_context(context)
    if not context_only:
        return ["(kein Kontext gespeichert)"]
    # Prefer single-line summary: first N characters; then wrap nicely
    snippet = context_only.replace("\n", "  ")
    wrapped = wrap(snippet, max_chars)
    if len(wrapped) > max_lines:
        wrapped = wrapped[:max_lines-1] + [wrapped[max_lines-1] + " …"]
    return wrapped


def _format_datetime(dt_str: str) -> str:
    """Format ISO-like datetime to DD.MM.YYYY HH:MM; fallback to original on parse failure."""
    if not dt_str:
        return ""
    try:
        # Handle possible Z suffix
        ds = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ds)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        # Try common alternative formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
            try:
                dt = datetime.strptime(dt_str, fmt)
                return dt.strftime("%d.%m.%Y %H:%M")
            except Exception:
                continue
    return dt_str


def main():
    # Initialize database
    print("Initializing database...")
    try:
        init_db()
        print("✅ Database initialized")
    except Exception as e:
        print(f"⚠️ Warning: Database initialization issue: {e}")

    # Initialize face recognizer
    print("Loading face recognizer...")
    try:
        recognizer = get_recognizer()
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

    print("\nFace identification (with context) started. Press 'q' to quit.\n")
    print(f"Identification threshold: {THRESHOLD}")
    print(f"Suggestion threshold: {THRESHOLD_SUGGESTION}\n")

    frame_count = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("❌ Error: Could not read frame")
                break

            frame_count += 1

            # Get all faces from frame
            all_faces = get_all_faces_from_frame(frame)

            # Process each detected face
            identified_count = 0
            for face_img, (x, y, w, h) in all_faces:
                # Get embedding for this face
                try:
                    embedding = recognizer.get_embedding(face_img)
                except Exception:
                    # Skip this face if embedding generation fails
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    draw_label(frame, "Error", x, max(y - 10, 20), (0, 0, 255))
                    continue

                # Match identity
                match = match_identity(embedding, threshold=THRESHOLD)

                if match["match_found"]:
                    # Person identified - draw green box with name
                    identified_count += 1
                    name = match["name"]
                    similarity = match["similarity"]
                    person_id = match["person_id"]

                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 200, 0), 2)

                    # Primary label (name + similarity)
                    label = f"{name} ({similarity:.2f})"
                    draw_label(frame, label, x, max(y - 10, 20), (0, 255, 0))

                    # Fetch context and draw a small text box near the face (below if space, else above)
                    context_lines = []
                    try:
                        person_data = get_person_by_id(person_id)
                        if person_data:
                            context = person_data.get("context", "")
                            created_at = person_data.get("created_at", "")
                            # Show date/time (formatted), but do not show transcript
                            if created_at:
                                context_lines.append(f"seit: {_format_datetime(created_at)}")
                            context_lines += wrap_context(context, max_chars=60, max_lines=3)
                        else:
                            context_lines = ["(keine Daten gefunden)"]
                    except Exception as e:
                        context_lines = [f"(Fehler: {e})"]

                    # Decide placement: prefer below face; if near bottom, place above
                    box_x = x
                    below_y = y + h + 12
                    above_y = max(y - (20 * len(context_lines) + 24), 10)
                    box_y = below_y if below_y + 80 < frame.shape[0] else above_y
                    draw_multiline_box(frame, context_lines, box_x, box_y,
                                       max_width_px=600, pad=6, line_scale=0.55,
                                       line_thickness=1, bg_color=(0, 0, 0), fg_color=(255, 255, 255))

                elif match.get("best_candidates") and len(match["best_candidates"]) > 0:
                    # No match above threshold, but show best candidate if above suggestion threshold
                    best_candidate = match["best_candidates"][0]
                    if best_candidate["similarity"] >= THRESHOLD_SUGGESTION:
                        # Draw yellow box with suggestion
                        name = best_candidate["name"]
                        similarity = best_candidate["similarity"]

                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
                        label = f"?{name}? ({similarity:.2f})"
                        draw_label(frame, label, x, max(y - 10, 20), (0, 255, 255))
                    else:
                        # Unknown person - draw red box
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                        draw_label(frame, "Unknown", x, max(y - 10, 20), (0, 0, 255))
                else:
                    # No candidates in database - draw red box
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    draw_label(frame, "Unknown", x, max(y - 10, 20), (0, 0, 255))

            # HUD
            info_text = f"Faces: {len(all_faces)} | Identified: {identified_count}"
            draw_label(frame, info_text, 10, 30, (255, 255, 255), scale=0.8, thickness=2)
            draw_label(frame, f"Frame: {frame_count}", 10, 60, (200, 200, 200), scale=0.6, thickness=2)

            # Display frame
            cv2.imshow('Face Identification (with Context)', frame)

            # Print status every 60 frames
            if frame_count % 60 == 0:
                print(f"Frame {frame_count}: {len(all_faces)} face(s), {identified_count} identified")

            # Press 'q' to quit
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    finally:
        # Cleanup
        cap.release()
        cv2.destroyAllWindows()
        print("\n✅ Camera released. Exiting.")


if __name__ == "__main__":
    main()
