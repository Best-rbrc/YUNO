"""
Test script for face detection using the face recognizer.
Opens a video feed and displays detected faces with bounding boxes.
Press 'q' to quit.
"""

import cv2
import sys
from src.face_recognizer import get_recognizer

def main():
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
    
    print("\nFace detection started. Press 'q' to quit.\n")
    
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("❌ Error: Could not read frame")
                break
            
            frame_count += 1
            
            # Detect faces in the frame
            faces = recognizer.detect_faces(frame)
            
            # Draw bounding boxes around detected faces
            for (x, y, w, h) in faces:
                # Validate face before drawing
                face_img = frame[y:y+h, x:x+w]
                if face_img.size == 0:
                    continue
                
                if recognizer.is_valid_face(face_img, (x, y, w, h)):
                    # Draw green rectangle for valid faces
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, "Face", (x, y - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                else:
                    # Draw red rectangle for invalid/rejected faces
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    cv2.putText(frame, "Rejected", (x, y - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            
            # Display face count in top-left corner
            valid_faces = sum(1 for (x, y, w, h) in faces 
                            if frame[y:y+h, x:x+w].size > 0 and 
                            recognizer.is_valid_face(frame[y:y+h, x:x+w], (x, y, w, h)))
            cv2.putText(frame, f"Faces detected: {valid_faces}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            # Display frame
            cv2.imshow('Face Detection Test', frame)
            
            # Print status every 30 frames
            if frame_count % 30 == 0:
                print(f"Frame {frame_count}: {valid_faces} face(s) detected")
            
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
