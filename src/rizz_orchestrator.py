"""
Rizz Orchestrator - Single entrypoint for the Rizz Mode AI pipeline
"""
import logging
import os
import sys
from typing import Optional

import cv2
import numpy as np
from datetime import datetime

from src.rizz_mode import create_rizz_mode
from src.face_recognizer import get_face_from_frame, get_all_faces_from_frame, get_recognizer
from src.identity_matcher import match_identity, THRESHOLD
from src.database_handler import get_person_by_id
from src.speech_output import speak, generate_and_speak_greeting, speak_unknown_person
from src.gender_detector import create_gender_detector

logger = logging.getLogger(__name__)


def run_rizz_pipeline():
    """
    Full Rizz Mode orchestration: scans camera, does gender/person detection, speaks context and flirting tips.
    """
    # Step 1: Take a photo using rizz_mode (ensures temp storage)
    rizz = create_rizz_mode()
    if not rizz:
        speak('Rizz Mode could not be initialized. Please check the DeepFace installation.')
        return

    result = rizz.capture_and_analyze(timeout=5)
    if not result or not result.get('success'):
        speak("No face could be detected or the analysis failed.")
        return

    face_path = result.get('face_path')
    frame = cv2.imread(face_path)
    if frame is None:
        speak("The detected face could not be loaded.")
        return
    
    # Step 2: Recognize person (ArcFace embedding, DB lookup)
    recognizer = get_recognizer()
    face_result = get_face_from_frame(frame)
    is_known = False
    person_data = None
    
    if face_result:
        face_img, bbox = face_result
        try:
            embedding = recognizer.get_embedding(face_img)
            match = match_identity(embedding, threshold=THRESHOLD)
        except Exception as e:
            logger.error(f"Fehler beim Face Embedding/Matching: {str(e)}")
            match = None

        if match and match.get("match_found"):
            is_known = True
            person_data = get_person_by_id(match["person_id"])
    
    # Step 3: Output context if person known, otherwise generic
    gender = result.get('gender', '').capitalize() if result.get('gender') else 'Unknown'
    if gender.lower() == 'man':
        gender_speech = 'men'
    elif gender.lower() == 'woman':
        gender_speech = 'women'
    else:
        gender_speech = gender
    tips_data = result.get('tips', {})

    if is_known and person_data:
        generate_and_speak_greeting(person_data)
        speak(f"Here are some flirting tips for {gender_speech}.")
        if isinstance(tips_data, dict) and tips_data.get('enabled', True) and tips_data.get('tips'):
            _speak_tips_block(tips_data['tips'])
        elif isinstance(tips_data, dict) and tips_data.get('error'):
            speak(f"Error: {tips_data['error']}")
        else:
            speak("No specific tips available.")
    else:
        speak_unknown_person()
        speak(f"Here are some general flirting tips for {gender_speech}.")
        if isinstance(tips_data, dict) and tips_data.get('enabled', True) and tips_data.get('tips'):
            _speak_tips_block(tips_data['tips'])
        elif isinstance(tips_data, dict) and tips_data.get('error'):
            speak(f"Error: {tips_data['error']}")
        else:
            speak("No specific tips available.")


def _speak_tips_block(tips: dict):
    """Speaks all keys/sections from the OpenAI-generated tips dict (in order)."""
    key_order = ['opener', 'body_language', 'conversation', 'confidence_boosters', 'red_flags']
    separator_map = {
        'opener':              "Opener:",
        'body_language':       "Body language:",
        'conversation':        "Conversation tips:",
        'confidence_boosters': "Confidence boosters:",
        'red_flags':           "What to avoid:",
    }
    for key in key_order:
        if tips.get(key):
            lead = separator_map.get(key, key.capitalize()+':')
            speak(f"{lead} {tips[key]}")
