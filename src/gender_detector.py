"""
Gender Detection Module using DeepFace

This module provides functionality to detect gender from images using the DeepFace library.
It supports multiple models and can run both locally and with online demos.
"""

import os
import logging
import tempfile
from typing import Optional, Dict, Any, List
from pathlib import Path
import cv2
import numpy as np

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False
    logging.warning("DeepFace not available. Install with: pip install deepface")

class GenderDetector:
    """
    Gender detection using DeepFace library.
    
    Supports multiple models: VGG-Face, ArcFace, Facenet, Dlib, OpenFace
    Can detect gender, age, emotion, and race from facial images.
    """
    
    def __init__(self, model_name: str = "VGG-Face", enforce_detection: bool = True):
        """
        Initialize the gender detector.
        
        Args:
            model_name: DeepFace model to use ('VGG-Face', 'ArcFace', 'Facenet', 'Dlib', 'OpenFace')
            enforce_detection: Whether to enforce face detection (fail if no face found)
        """
        self.model_name = model_name
        self.enforce_detection = enforce_detection
        self.logger = logging.getLogger(__name__)
        
        if not DEEPFACE_AVAILABLE:
            raise ImportError("DeepFace is not installed. Install with: pip install deepface")
    
    def detect_gender(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        Detect gender from a single image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary containing gender prediction and confidence, or None if detection fails
        """
        try:
            if not os.path.exists(image_path):
                self.logger.error(f"Image file not found: {image_path}")
                return None
            
            # Analyze the image for gender
            result = DeepFace.analyze(
                img_path=image_path,
                actions=['gender'],
                enforce_detection=self.enforce_detection
            )
            
            # DeepFace returns a list, get the first result
            if isinstance(result, list) and len(result) > 0:
                result = result[0]
            
            gender_info = {
                'gender': result.get('dominant_gender', 'Unknown'),
                'confidence': result.get('gender', {}).get(result.get('dominant_gender', ''), 0.0),
                'model_used': self.model_name,
                'success': True
            }
            
            self.logger.info(f"Gender detection successful: {gender_info['gender']} (confidence: {gender_info['confidence']:.2f})")
            return gender_info
            
        except Exception as e:
            self.logger.error(f"Error detecting gender from {image_path}: {str(e)}")
            return {
                'gender': 'Unknown',
                'confidence': 0.0,
                'model_used': self.model_name,
                'success': False,
                'error': str(e)
            }
    
    def detect_gender_from_array(self, image_array: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Detect gender from a numpy array (OpenCV image).
        
        Args:
            image_array: Image as numpy array (BGR format from OpenCV)
            
        Returns:
            Dictionary containing gender prediction and confidence, or None if detection fails
        """
        # Save numpy array to temporary file since DeepFace.analyze() requires img_path parameter
        temp_file = None
        try:
            # Create a temporary file
            temp_fd, temp_file = tempfile.mkstemp(suffix='.jpg')
            os.close(temp_fd)
            
            # Save the image array to the temp file
            cv2.imwrite(temp_file, image_array)
            
            if not os.path.exists(temp_file):
                self.logger.error("Failed to create temporary image file")
                return {
                    'gender': 'Unknown',
                    'confidence': 0.0,
                    'model_used': self.model_name,
                    'success': False,
                    'error': 'Failed to create temporary file'
                }
            
            # Analyze the image using img_path (same as detect_gender method)
            result = DeepFace.analyze(
                img_path=temp_file,
                actions=['gender'],
                enforce_detection=self.enforce_detection
            )
            
            # DeepFace returns a list, get the first result
            if isinstance(result, list) and len(result) > 0:
                result = result[0]
            
            gender_info = {
                'gender': result.get('dominant_gender', 'Unknown'),
                'confidence': result.get('gender', {}).get(result.get('dominant_gender', ''), 0.0),
                'model_used': self.model_name,
                'success': True
            }
            
            self.logger.info(f"Gender detection successful: {gender_info['gender']} (confidence: {gender_info['confidence']:.2f})")
            return gender_info
            
        except Exception as e:
            self.logger.error(f"Error detecting gender from image array: {str(e)}")
            return {
                'gender': 'Unknown',
                'confidence': 0.0,
                'model_used': self.model_name,
                'success': False,
                'error': str(e)
            }
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception as e:
                    self.logger.warning(f"Failed to remove temporary file {temp_file}: {e}")
    
    def detect_multiple_attributes(self, image_path: str, attributes: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        Detect multiple attributes from an image (gender, age, emotion, race).
        
        Args:
            image_path: Path to the image file
            attributes: List of attributes to detect ['gender', 'age', 'emotion', 'race']
            
        Returns:
            Dictionary containing all detected attributes and their confidence scores
        """
        if attributes is None:
            attributes = ['gender', 'age', 'emotion', 'race']
        
        try:
            if not os.path.exists(image_path):
                self.logger.error(f"Image file not found: {image_path}")
                return None
            
            # Analyze the image for multiple attributes
            result = DeepFace.analyze(
                img_path=image_path,
                actions=attributes,
                enforce_detection=self.enforce_detection
            )
            
            # DeepFace returns a list, get the first result
            if isinstance(result, list) and len(result) > 0:
                result = result[0]
            
            # Format the results
            formatted_result = {
                'success': True,
                'model_used': self.model_name
            }
            
            for attr in attributes:
                if attr in result:
                    if attr == 'gender':
                        formatted_result['gender'] = result[attr].get('Woman', 0.0)
                        formatted_result['dominant_gender'] = result.get('dominant_gender', 'Unknown')
                    elif attr == 'age':
                        formatted_result['age'] = result[attr]
                    elif attr == 'emotion':
                        formatted_result['emotions'] = result[attr]
                        formatted_result['dominant_emotion'] = result.get('dominant_emotion', 'Unknown')
                    elif attr == 'race':
                        formatted_result['races'] = result[attr]
                        formatted_result['dominant_race'] = result.get('dominant_race', 'Unknown')
            
            self.logger.info(f"Multi-attribute detection successful for {image_path}")
            return formatted_result
            
        except Exception as e:
            self.logger.error(f"Error detecting attributes from {image_path}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'model_used': self.model_name
            }
    
    def batch_detect_gender(self, image_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Detect gender from multiple images.
        
        Args:
            image_paths: List of image file paths
            
        Returns:
            List of dictionaries containing gender predictions for each image
        """
        results = []
        
        for image_path in image_paths:
            result = self.detect_gender(image_path)
            if result:
                result['image_path'] = image_path
            results.append(result)
        
        return results
    
    def get_available_models(self) -> List[str]:
        """
        Get list of available DeepFace models.
        
        Returns:
            List of available model names
        """
        return ['VGG-Face', 'ArcFace', 'Facenet', 'Dlib', 'OpenFace']
    
    def set_model(self, model_name: str) -> bool:
        """
        Change the model used for detection.
        
        Args:
            model_name: Name of the model to use
            
        Returns:
            True if model was set successfully, False otherwise
        """
        if model_name in self.get_available_models():
            self.model_name = model_name
            self.logger.info(f"Model changed to: {model_name}")
            return True
        else:
            self.logger.error(f"Invalid model name: {model_name}")
            return False


def create_gender_detector(model_name: str = "VGG-Face") -> Optional[GenderDetector]:
    """
    Factory function to create a GenderDetector instance.
    
    Args:
        model_name: DeepFace model to use
        
    Returns:
        GenderDetector instance or None if DeepFace is not available
    """
    if not DEEPFACE_AVAILABLE:
        logging.error("DeepFace is not available. Install with: pip install deepface")
        return None
    
    return GenderDetector(model_name=model_name)


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create detector
    detector = create_gender_detector("VGG-Face")
    
    if detector:
        # Example usage
        print("Available models:", detector.get_available_models())
        
        # Test with a sample image
        sample_image = "../data/persons/person_1_Benni/profile.jpg"
        if os.path.exists(sample_image):
            result = detector.detect_gender(sample_image)
            print("Gender detection result:", result)
        else:
            print(f"Sample image not found: {sample_image}")
            print("Please check if the file exists.")
    else:
        print("Failed to create gender detector. Please install DeepFace.")
