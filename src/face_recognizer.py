"""
Face Recognition using ArcFace ONNX Model
Provides face detection, cropping, and embedding generation
Based on arcface_test.py logic
"""

import cv2
import numpy as np
import onnxruntime as ort
import os
import urllib.request
from pathlib import Path


# Configuration
MODEL_PATH = "models/w600k_r50.onnx"
ALTERNATIVE_MODELS = [
    "../models/w600k_r50.onnx",
    "models/arcface_v2.onnx",
    "models/arcfaceresnet100-8.onnx",
    "models/arcface_model.onnx",
    "newFaceDetection/models/w600k_r50.onnx",
    "newFaceDetection/models/arcface_v2.onnx"
]
INPUT_SIZE = (112, 112)  # ArcFace standard input size

# YuNet face detector (CNN-based) — far more robust across ethnicities and
# poses than the legacy Haar Cascade, which has a documented bias against
# non-frontal and East/South-East Asian faces. Tiny (~230 KB) and fast enough
# for a Raspberry Pi. Auto-downloaded on first use; Haar Cascade is the fallback.
YUNET_MODEL_PATH = "models/face_detection_yunet_2023mar.onnx"
YUNET_MODEL_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
YUNET_SCORE_THRESHOLD = 0.6   # detection confidence cutoff
YUNET_NMS_THRESHOLD = 0.3
YUNET_TOP_K = 5000


def _ensure_yunet_model(path: str = YUNET_MODEL_PATH):
    """Return path to the YuNet model, downloading it if missing. None on failure."""
    if os.path.exists(path):
        return path
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print("⬇️  Downloading YuNet face detection model (~230 KB)...")
        urllib.request.urlretrieve(YUNET_MODEL_URL, path)
        print("✅ YuNet model downloaded")
        return path
    except Exception as e:
        print(f"⚠️ Could not download YuNet model: {e}")
        return None


class ArcFaceRecognizer:
    """ArcFace Face Recognition with ONNX Runtime - matching arcface_test.py"""
    
    def __init__(self, model_path):
        """Initialize ArcFace model"""
        print(f"Loading ArcFace model: {model_path}")
        
        # Check if model exists
        if not os.path.exists(model_path):
            # Try alternatives
            for alt_path in ALTERNATIVE_MODELS:
                if os.path.exists(alt_path):
                    print(f"Using alternative model: {alt_path}")
                    model_path = alt_path
                    break
            else:
                raise FileNotFoundError(
                    f"Model not found: {model_path}\n"
                    f"Run: cd newFaceDetection && python download_model.py"
                )
        
        # Load ONNX model
        self.session = ort.InferenceSession(model_path)
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        
        print("✅ ArcFace model loaded")
        print(f"   Input: {self.input_name}")
        print(f"   Output: {self.output_name}")

        # Face detector setup: prefer YuNet (robust across ethnicities/poses),
        # fall back to Haar Cascade if YuNet is unavailable.
        self.detector_backend = None
        self.yunet = None

        if hasattr(cv2, "FaceDetectorYN"):
            yunet_path = _ensure_yunet_model()
            if yunet_path:
                try:
                    self.yunet = cv2.FaceDetectorYN.create(
                        yunet_path, "", (320, 320),
                        YUNET_SCORE_THRESHOLD, YUNET_NMS_THRESHOLD, YUNET_TOP_K
                    )
                    # Self-test: some OpenCV builds can create the detector but
                    # fail to actually run inference (e.g. broken DNN backend).
                    # Run one real detect() so we fall back to Haar instead of
                    # crashing on the first camera frame.
                    self._yunet_self_test()
                    self.detector_backend = "yunet"
                    print("✅ Using YuNet face detector (robust across ethnicities)")
                except Exception as e:
                    self.yunet = None
                    print(f"⚠️ YuNet unavailable ({e}); falling back to Haar Cascade")

        # Haar Cascade always loaded as a fallback
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        if self.detector_backend is None:
            self.detector_backend = "haar"
            print("⚠️ Using Haar Cascade face detector "
                  "(less accurate on diverse/non-frontal faces)")
    
    def preprocess_face(self, face_img):
        """Preprocess face for ArcFace (112x112, normalized)"""
        # Resize to 112x112
        face = cv2.resize(face_img, INPUT_SIZE)
        
        # Convert BGR to RGB
        face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
        
        # Normalize to [-1, 1]
        face = (face - 127.5) / 127.5
        
        # Transpose to CHW format (channels first)
        face = face.transpose(2, 0, 1)
        
        # Add batch dimension
        face = np.expand_dims(face, axis=0).astype(np.float32)
        
        return face
    
    def get_embedding(self, face_img):
        """Get 512-dimensional embedding from face image"""
        preprocessed = self.preprocess_face(face_img)
        embedding = self.session.run([self.output_name], {self.input_name: preprocessed})[0]
        
        # Normalize embedding (L2 normalization)
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding[0]
    
    def _yunet_self_test(self):
        """Run one inference to confirm this OpenCV build can actually execute
        YuNet. Raises if inference fails so the caller can fall back to Haar."""
        dummy = np.full((320, 320, 3), 127, dtype=np.uint8)
        self.yunet.setInputSize((320, 320))
        self.yunet.detect(dummy)

    def detect_faces(self, frame):
        """Detect faces in frame. Returns a list of (x, y, w, h) tuples.
        Uses YuNet when available, otherwise Haar Cascade."""
        if self.detector_backend == "yunet" and self.yunet is not None:
            return self._detect_faces_yunet(frame)
        return self._detect_faces_haar(frame)

    def _detect_faces_yunet(self, frame):
        """Detect faces with the YuNet CNN detector."""
        h, w = frame.shape[:2]
        # YuNet needs the input size set to the actual frame size each call
        self.yunet.setInputSize((w, h))
        _, faces = self.yunet.detect(frame)
        results = []
        if faces is not None:
            for f in faces:
                # f = [x, y, w, h, 5x landmarks..., score]
                x, y, fw, fh = int(f[0]), int(f[1]), int(f[2]), int(f[3])
                x = max(0, x)
                y = max(0, y)
                results.append((x, y, fw, fh))
        return results

    def _detect_faces_haar(self, frame):
        """Detect faces with the legacy Haar Cascade (fallback)."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Stricter parameters to reduce false positives:
        # - minNeighbors=7 (higher = fewer false positives, may miss real faces)
        # - minSize=(100, 100) (larger = fewer small false positives)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=7,
            minSize=(100, 100),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        return [tuple(int(v) for v in f) for f in faces]
    
    def is_valid_face(self, face_img, bbox):
        """
        Validate if a detected region is actually a face.
        Checks aspect ratio, size, and basic image quality.
        
        Args:
            face_img: Cropped face image (numpy array)
            bbox: Bounding box (x, y, w, h)
        
        Returns:
            bool: True if likely a real face, False otherwise
        """
        x, y, w, h = bbox

        # Basic shape sanity (applies to all backends)
        if len(face_img.shape) != 3 or face_img.shape[2] != 3:
            return False

        # YuNet already filters detections by confidence score and NMS, so its
        # boxes are trustworthy. Skipping the Haar-era heuristics below avoids
        # wrongly rejecting valid faces (e.g. smaller or non-frontal faces in a
        # crowd), while still keeping a minimal size guard.
        if self.detector_backend == "yunet":
            return face_img.shape[0] >= 32 and face_img.shape[1] >= 32

        # --- Haar Cascade fallback: stricter validation to kill false positives ---

        # Check 1: Aspect ratio - faces are roughly square to slightly rectangular
        aspect_ratio = w / h
        if aspect_ratio < 0.6 or aspect_ratio > 1.5:
            # Too narrow or too wide - probably not a face
            return False

        # Check 2: Size - faces should be reasonably sized
        face_area = w * h
        if face_area < 10000:  # Less than 100x100 pixels - probably too small
            return False

        # Check 4: Minimum dimensions
        if face_img.shape[0] < 50 or face_img.shape[1] < 50:
            return False

        # Check 5: Basic image quality - check for very dark or very bright images
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)

        # Too dark or too bright - might be a false positive
        if mean_brightness < 20 or mean_brightness > 240:
            return False

        # Check 6: Variance - real faces have texture, false positives might be uniform
        variance = np.var(gray)
        if variance < 100:  # Very uniform image - probably not a face
            return False

        return True
    


# Global recognizer instance
_recognizer = None


def get_recognizer():
    """Get or create global recognizer instance"""
    global _recognizer
    if _recognizer is None:
        _recognizer = ArcFaceRecognizer(MODEL_PATH)
    return _recognizer


def detect_and_crop_face(image_path: str) -> str:
    """
    Detect a face in the image and crop it.
    Returns path to the cropped image, or None if no face detected.
    Uses get_face_from_frame internally for consistency.
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"Cannot read image: {image_path}")
        return None
    
    face_result = get_face_from_frame(img)
    if face_result is None:
        print("No face detected")
        return None
    
    face_img, (x, y, w, h) = face_result
    
    # Save cropped face
    base_path = Path(image_path)
    cropped_path = str(base_path.parent / f"{base_path.stem}_cropped{base_path.suffix}")
    cv2.imwrite(cropped_path, face_img)
    
    return cropped_path


def get_face_from_frame(frame):
    """
    Extract face from a frame (numpy array) - matching arcface_test.py approach.
    Prioritizes the face closest to the center of the frame.
    Filters out false positives using quality validation.
    Returns face_img (numpy array) or None if no face detected.
    """
    recognizer = get_recognizer()
    
    faces = recognizer.detect_faces(frame)
    
    if len(faces) == 0:
        return None
    
    # Filter valid faces first
    valid_faces = []
    frame_height, frame_width = frame.shape[:2]
    
    for x, y, w, h in faces:
        # Ensure coordinates are within frame bounds
        x = max(0, x)
        y = max(0, y)
        w = min(w, frame_width - x)
        h = min(h, frame_height - y)
        
        if w <= 0 or h <= 0:
            continue
        
        face_img = frame[y:y+h, x:x+w]
        
        if face_img.size == 0:
            continue
        
        # Validate face quality
        if recognizer.is_valid_face(face_img, (x, y, w, h)):
            valid_faces.append((x, y, w, h))
    
    if len(valid_faces) == 0:
        return None
    
    # Calculate center of frame
    frame_center_x = frame_width / 2
    frame_center_y = frame_height / 2
    
    # Sort faces by distance to center (prioritize center), then by size
    def face_priority(face):
        x, y, w, h = face
        face_center_x = x + w / 2
        face_center_y = y + h / 2
        
        # Distance to center
        distance_to_center = np.sqrt(
            (face_center_x - frame_center_x) ** 2 + 
            (face_center_y - frame_center_y) ** 2
        )
        
        # Priority: closer to center is better, but also consider size
        # Normalize distance by frame size, then combine with area
        normalized_distance = distance_to_center / max(frame_width, frame_height)
        area = w * h
        
        # Lower distance = higher priority, so we subtract it
        # Higher area = higher priority, so we add it normalized
        priority = area - normalized_distance * 10000
        
        return priority
    
    # Sort by priority (higher priority first)
    faces_sorted = sorted(valid_faces, key=face_priority, reverse=True)
    x, y, w, h = faces_sorted[0]
    face_img = frame[y:y+h, x:x+w]
    
    return face_img, (x, y, w, h)


def get_all_faces_from_frame(frame):
    """
    Extract all faces from a frame (numpy array).
    Returns list of tuples: (face_img, bbox) where bbox = (x, y, w, h)
    Filters out false positives using quality validation.
    """
    recognizer = get_recognizer()
    
    faces = recognizer.detect_faces(frame)
    
    if len(faces) == 0:
        return []
    
    result = []
    for x, y, w, h in faces:
        # Ensure coordinates are within frame bounds
        frame_height, frame_width = frame.shape[:2]
        x = max(0, x)
        y = max(0, y)
        w = min(w, frame_width - x)
        h = min(h, frame_height - y)
        
        if w <= 0 or h <= 0:
            continue
        
        face_img = frame[y:y+h, x:x+w]
        
        if face_img.size == 0:
            continue
        
        # Validate face quality
        if recognizer.is_valid_face(face_img, (x, y, w, h)):
            result.append((face_img, (x, y, w, h)))
        else:
            # Debug: print why face was rejected
            aspect_ratio = w / h
            print(f"   ⚠️ Face at ({x},{y}) rejected: aspect={aspect_ratio:.2f}, size={w}x{h}")
    
    return result



if __name__ == "__main__":
    # Test code
    print("Testing ArcFace Face Recognizer...")
    recognizer = get_recognizer()
    print("Model loaded successfully!")
