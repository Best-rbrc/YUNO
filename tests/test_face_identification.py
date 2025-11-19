"""
Test script for face identification using the face recognizer and identity matcher.
Opens a video feed and displays detected faces with their names.
Press 'q' to quit.
"""

import cv2
import sys
from src.face_recognizer import get_recognizer, get_all_faces_from_frame
from src.identity_matcher import match_identity, THRESHOLD, THRESHOLD_SUGGESTION
from src.database_handler import init_db


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
    
    print("\nFace identification started. Press 'q' to quit.\n")
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
                except Exception as e:
                    # Skip this face if embedding generation fails
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    cv2.putText(frame, "Error", (x, y - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    continue
                
                # Match identity
                match = match_identity(embedding, threshold=THRESHOLD)
                
                if match["match_found"]:
                    # Person identified - draw green box with name
                    identified_count += 1
                    name = match["name"]
                    similarity = match["similarity"]
                    
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    
                    # Display name and similarity
                    label = f"{name} ({similarity:.2f})"
                    cv2.putText(frame, label, (x, y - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                    
                elif match.get("best_candidates") and len(match["best_candidates"]) > 0:
                    # No match above threshold, but show best candidate if above suggestion threshold
                    best_candidate = match["best_candidates"][0]
                    if best_candidate["similarity"] >= THRESHOLD_SUGGESTION:
                        # Draw yellow box with suggestion
                        name = best_candidate["name"]
                        similarity = best_candidate["similarity"]
                        
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
                        
                        label = f"?{name}? ({similarity:.2f})"
                        cv2.putText(frame, label, (x, y - 10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    else:
                        # Unknown person - draw red box
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                        cv2.putText(frame, "Unknown", (x, y - 10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                else:
                    # No candidates in database - draw red box
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    cv2.putText(frame, "Unknown", (x, y - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            # Display face count and identified count in top-left corner
            
            info_text = f"Faces: {len(all_faces)} | Identified: {identified_count}"
            cv2.putText(frame, info_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(frame, f"Frame: {frame_count}", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Display frame
            cv2.imshow('Face Identification Test', frame)
            
            # Print status every 30 frames
            if frame_count % 30 == 0:
                print(f"Frame {frame_count}: {len(all_faces)} face(s), {identified_count} identified")
            
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
