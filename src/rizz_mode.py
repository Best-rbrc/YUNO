"""
Rizz Mode - AI-Powered Flirting Assistant

This module combines camera capture, gender detection, and OpenAI API to provide
personalized flirting tips based on the detected gender of the person in the camera.
"""

import os
import time
import logging
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Import existing modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .camera_manager import take_photo
    from .face_recognizer import get_face_from_frame
    from .gender_detector import create_gender_detector
    from .openai_api import client
except ImportError:
    # Fallback for direct execution
    from camera_manager import take_photo
    from face_recognizer import get_face_from_frame
    from gender_detector import create_gender_detector
    from openai_api import client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RizzMode:
    """
    AI-powered flirting assistant that detects gender and provides personalized tips.
    """
    
    def __init__(self, temp_dir: str = "data/temp"):
        """
        Initialize Rizz Mode.
        
        Args:
            temp_dir: Directory for temporary image storage
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize gender detector
        self.gender_detector = create_gender_detector("VGG-Face")
        if not self.gender_detector:
            raise RuntimeError("Failed to initialize gender detector. Please install DeepFace.")
        
        # Gender-specific settings
        self.gender_settings = {
            "Man": {
                "enabled": True,
                "style": "confident and charming",
                "approach": "direct but respectful"
            },
            "Woman": {
                "enabled": True,
                "style": "smooth and sophisticated", 
                "approach": "gentle and attentive"
            }
        }
        
        logger.info("🔥 Rizz Mode initialized successfully!")
    
    def capture_and_analyze(self, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """
        Capture image from camera and analyze for gender.
        
        Args:
            timeout: Camera timeout in seconds
            
        Returns:
            Dictionary with analysis results or None if failed
        """
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_image_path = self.temp_dir / f"rizz_capture_{timestamp}.jpg"
            
            logger.info("📸 Capturing image...")
            
            # Take photo using existing camera manager
            photo_path = take_photo(str(temp_image_path))
            
            if not os.path.exists(photo_path):
                logger.error("Failed to capture image")
                return None
            
            logger.info(f"✅ Image captured: {photo_path}")
            
            # Load image for face detection
            frame = cv2.imread(photo_path)
            if frame is None:
                logger.error("Failed to load captured image")
                return None
            
            # Detect and crop face
            logger.info("🔍 Detecting face...")
            face_result = get_face_from_frame(frame)
            
            if face_result is None:
                logger.warning("No face detected in image")
                return {
                    "success": False,
                    "error": "No face detected",
                    "image_path": photo_path
                }
            
            face_img, bbox = face_result
            logger.info(f"✅ Face detected at {bbox}")
            
            # Save cropped face for gender detection
            face_path = self.temp_dir / f"rizz_face_{timestamp}.jpg"
            cv2.imwrite(str(face_path), face_img)
            
            # Detect gender
            logger.info("🧠 Analyzing gender...")
            gender_result = self.gender_detector.detect_gender(str(face_path))
            
            if not gender_result or not gender_result.get('success', False):
                logger.warning("Gender detection failed")
                return {
                    "success": False,
                    "error": "Gender detection failed",
                    "image_path": photo_path,
                    "face_path": str(face_path)
                }
            
            gender = gender_result['gender']
            confidence = gender_result['confidence']
            
            logger.info(f"✅ Gender detected: {gender} (confidence: {confidence:.1f}%)")
            
            # Generate flirting tips
            tips = self._generate_flirting_tips(gender, confidence)
            
            result = {
                "success": True,
                "gender": gender,
                "confidence": confidence,
                "image_path": photo_path,
                "face_path": str(face_path),
                "tips": tips,
                "timestamp": timestamp
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in capture_and_analyze: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_flirting_tips(self, gender: str, confidence: float) -> Dict[str, Any]:
        """
        Generate personalized flirting tips based on detected gender.
        
        Args:
            gender: Detected gender ("Man" or "Woman")
            confidence: Detection confidence (0-100)
            
        Returns:
            Dictionary with flirting tips and advice
        """
        try:
            # Check if gender is enabled
            if gender not in self.gender_settings or not self.gender_settings[gender]["enabled"]:
                return {
                    "enabled": False,
                    "message": f"Rizz mode is disabled for {gender}"
                }
            
            # Create gender-specific prompt
            style = self.gender_settings[gender]["style"]
            approach = self.gender_settings[gender]["approach"]
            
            # DEUTSCH: Extrem strikte Formatvorgabe für OpenAI, damit IMMER nur echtes JSON kommt!
            prompt = (
                "Gib deine Antwort AUSSCHLIESSLICH als gültiges JSON-Objekt aus – OHNE jede Einleitung, Erklärung, Nachsatz, Kommentar, keine Markdown-Blöcke. Nur das JSON!\n"
                'Format:\n'
                '{\n'
                '  "opener": "Dein Anmachspruch oder Gesprächsöffner (konkret, situativ)",\n'
                '  "body_language": "Körpersprache-Tipp (präzise Handlung, keine Allgemeinplätze)",\n'
                '  "conversation": "Gesprächsverlauf-Tipp (2-3 konkrete Fragen/Leitfäden)",\n'
                '  "confidence_boosters": "Selbstbewusstseins-Booster (praktische, sofort anwendbare Micro-Aktionen)",\n'
                '  "red_flags": "Was du vermeiden solltest (konkret, fallbezogen)"\n'
                '}\n'
                f'Die Person wurde als {gender} erkannt (Sicherheit {confidence:.1f}%). '
                'Liefere mindestens 3 präzise, respektvolle, SITUATIVE Flirttipps im angegebenen Format. '
                'Vermeide generische Floskeln wie "sei du selbst" oder "sei freundlich". '
                'Nutze abwechslungsreiche Formulierungen und vermeide Wiederholungen früherer Antworten. '
                'Nutze detailreiche, bildhafte Sprache (aber kurz und präzise), z. B. konkrete Beobachtungen (Lächeln, Outfit, Energie), '
                'offene Fragen mit Tiefe und kleine spielerische Herausforderungen. '
                'Alle Inhalte bitte auf Deutsch.'
            )

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Du bist ein professioneller Wingman. Du gibst präzise, situative, respektvolle und abwechslungsreiche Flirttipps auf Deutsch."},
                    {"role": "user", "content": prompt}
                ],
                temperature=1.0,
                top_p=0.9,
                presence_penalty=0.6,
                frequency_penalty=0.4,
                max_tokens=800
            )
            
            tips_text = response.choices[0].message.content.strip()
            
            # Try to parse as JSON, fallback to text
            try:
                import json
                tips = json.loads(tips_text)
            except json.JSONDecodeError:
                # Keine Fallback-Tipps mehr! Stattdessen Fehler-Meldung für Sprachmodul
                return {
                    "enabled": False,
                    "error": "OpenAI lieferte keine gültige Tipps-Struktur! KI-Antwort konnte nicht verarbeitet werden.",
                    "raw_response": tips_text
                }
            
            return {
                "enabled": True,
                "gender": gender,
                "confidence": confidence,
                "tips": tips,
                "style": style,
                "approach": approach
            }
            
        except Exception as e:
            logger.error(f"Error generating flirting tips: {str(e)}")
            return {
                "enabled": False,
                "error": str(e),
                "message": "Failed to generate flirting tips"
            }
    
    def set_gender_setting(self, gender: str, enabled: bool = None, style: str = None, approach: str = None):
        """
        Update settings for a specific gender.
        
        Args:
            gender: "Man" or "Woman"
            enabled: Whether to enable rizz mode for this gender
            style: Style description
            approach: Approach description
        """
        if gender not in self.gender_settings:
            self.gender_settings[gender] = {}
        
        if enabled is not None:
            self.gender_settings[gender]["enabled"] = enabled
        if style is not None:
            self.gender_settings[gender]["style"] = style
        if approach is not None:
            self.gender_settings[gender]["approach"] = approach
        
        logger.info(f"Updated settings for {gender}: {self.gender_settings[gender]}")
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current gender settings."""
        return self.gender_settings.copy()
    
    def cleanup_temp_files(self, max_age_hours: int = 24):
        """
        Clean up old temporary files.
        
        Args:
            max_age_hours: Maximum age of files to keep (in hours)
        """
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for file_path in self.temp_dir.glob("rizz_*"):
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
                        logger.info(f"Cleaned up old file: {file_path.name}")
            
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {str(e)}")


def create_rizz_mode(temp_dir: str = "data/temp") -> Optional[RizzMode]:
    """
    Factory function to create a RizzMode instance.
    
    Args:
        temp_dir: Directory for temporary image storage
        
    Returns:
        RizzMode instance or None if initialization fails
    """
    try:
        return RizzMode(temp_dir)
    except Exception as e:
        logger.error(f"Failed to create RizzMode: {str(e)}")
        return None


# Example usage and testing
if __name__ == "__main__":
    print("🔥 Initializing Rizz Mode...")
    
    # Create RizzMode instance
    rizz = create_rizz_mode()
    
    if rizz:
        print("✅ Rizz Mode ready!")
        print(f"Settings: {rizz.get_settings()}")
        
        # Test capture and analysis
        print("\n📸 Testing camera capture and analysis...")
        result = rizz.capture_and_analyze()
        
        if result and result.get('success'):
            print(f"✅ Analysis successful!")
            print(f"Gender: {result['gender']} (confidence: {result['confidence']:.1f}%)")
            print(f"Tips: {result['tips']}")
        else:
            print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
        
        # Cleanup
        rizz.cleanup_temp_files()
    else:
        print("❌ Failed to initialize Rizz Mode")
