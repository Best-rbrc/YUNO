"""
Test script for gender detection using the gender detector.
Opens a video feed and displays detected faces with their gender predictions.
Press 'q' to quit.
"""

import cv2
import sys
import time
from collections import defaultdict
from src.face_recognizer import get_recognizer, get_all_faces_from_frame
from src.gender_detector import create_gender_detector


def main():
    # Initialize gender detector
    print("Loading gender detector...")
    try:
        # Use enforce_detection=False to handle edge cases gracefully
        gender_detector = create_gender_detector(model_name="VGG-Face")
        if gender_detector is None:
            print("❌ Error: DeepFace is not available. Install with: pip install deepface")
            sys.exit(1)
        
        # Set enforce_detection to False for better real-time performance
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
    
    print("\nGender detection started. Press 'q' to quit.")
    print("Note: Gender detection may be slower than face detection.\n")
    
    frame_count = 0
    last_gender_update = {}  # Track when we last updated gender for each face region
    gender_cache = {}  # Cache gender results for a few frames
    
    # Processing settings
    GENDER_UPDATE_INTERVAL = 15  # Update gender every N frames (to improve performance)
    CACHE_DURATION = 30  # Keep cached results for N frames
    
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
            for i, (face_img, (x, y, w, h)) in enumerate(all_faces):
                # Create a unique key for this face region (based on position and size)
                face_key = f"{x}_{y}_{w}_{h}"
                
                # Check if we should update gender detection for this face
                should_update = (
                    face_key not in last_gender_update or
                    (frame_count - last_gender_update[face_key]) >= GENDER_UPDATE_INTERVAL
                )
                
                # Get cached result or detect gender
                if should_update:
                    # Detect gender from face image array
                    try:
                        gender_result = gender_detector.detect_gender_from_array(face_img)
                        
                        if gender_result and gender_result.get('success', False):
                            gender = gender_result.get('gender', 'Unknown')
                            confidence = gender_result.get('confidence', 0.0)
                            
                            # Cache the result
                            gender_cache[face_key] = {
                                'gender': gender,
                                'confidence': confidence,
                                'frame': frame_count
                            }
                            last_gender_update[face_key] = frame_count
                        else:
                            # Detection failed, use cached or set unknown
                            if face_key not in gender_cache:
                                gender_cache[face_key] = {
                                    'gender': 'Unknown',
                                    'confidence': 0.0,
                                    'frame': frame_count
                                }
                    except Exception as e:
                        # Error in detection, use cached or set unknown
                        if face_key not in gender_cache:
                            gender_cache[face_key] = {
                                'gender': 'Error',
                                'confidence': 0.0,
                                'frame': frame_count
                            }
                
                # Get gender info (from cache or current detection)
                if face_key in gender_cache:
                    cache_entry = gender_cache[face_key]
                    # Check if cache is still valid
                    if (frame_count - cache_entry['frame']) <= CACHE_DURATION:
                        gender = cache_entry['gender']
                        confidence = cache_entry['confidence']
                        
                        # Draw bounding box and label based on gender
                        if gender == 'Man':
                            color = (255, 0, 0)  # Blue for Man
                            label = f"Man ({confidence:.1f}%)"
                        elif gender == 'Woman':
                            color = (255, 0, 255)  # Magenta for Woman
                            label = f"Woman ({confidence:.1f}%)"
                        else:
                            color = (128, 128, 128)  # Gray for Unknown/Error
                            label = gender
                        
                        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                        cv2.putText(frame, label, (x, y - 10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                    else:
                        # Cache expired, show placeholder
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        cv2.putText(frame, "Processing...", (x, y - 10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                else:
                    # No cache yet, show processing
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, "Processing...", (x, y - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Clean up old cache entries
            keys_to_remove = [
                key for key, entry in gender_cache.items()
                if (frame_count - entry['frame']) > CACHE_DURATION
            ]
            for key in keys_to_remove:
                del gender_cache[key]
                if key in last_gender_update:
                    del last_gender_update[key]
            
            # Display statistics in top-left corner
            detected_genders = defaultdict(int)
            for entry in gender_cache.values():
                if (frame_count - entry['frame']) <= CACHE_DURATION:
                    detected_genders[entry['gender']] += 1
            
            stats_text = f"Faces: {len(all_faces)}"
            if detected_genders:
                gender_stats = ", ".join([f"{k}: {v}" for k, v in detected_genders.items()])
                stats_text += f" | {gender_stats}"
            
            cv2.putText(frame, stats_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame, f"Frame: {frame_count}", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Update every {GENDER_UPDATE_INTERVAL} frames", (10, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            
            # Display frame
            cv2.imshow('Gender Detection Test', frame)
            
            # Print status every 60 frames
            if frame_count % 60 == 0:
                print(f"Frame {frame_count}: {len(all_faces)} face(s) detected, "
                      f"{sum(detected_genders.values())} with gender prediction")
            
            # Press 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
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
