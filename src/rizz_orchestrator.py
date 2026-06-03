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
    
    # Step 3: Generate tips — personalized with stored context if the person is known
    gender_raw = result.get('gender') or 'Unknown'
    gender = gender_raw.capitalize()
    confidence = result.get('confidence', 0.0)
    if gender.lower() == 'man':
        gender_speech = 'men'
    elif gender.lower() == 'woman':
        gender_speech = 'women'
    else:
        gender_speech = gender

    # Pull name + context (history of previous conversations) for personalization
    person_name = person_data.get('name') if person_data else None
    person_context = person_data.get('context') if person_data else None

    tips_data = rizz.generate_tips(
        gender_raw, confidence,
        person_name=person_name,
        person_context=person_context,
    )
    personalized = isinstance(tips_data, dict) and tips_data.get('personalized')

    if is_known and person_data:
        generate_and_speak_greeting(person_data)
        if personalized:
            speak(f"Here are some personalized flirting tips for talking to {person_name}.")
        else:
            speak(f"Here are some flirting tips for {gender_speech}.")
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
    """Speaks the pickup line and the short approach tips (in order)."""
    key_order = ['pickup_line', 'approach']
    separator_map = {
        'pickup_line': "Your pickup line:",
        'approach':    "How to play it:",
    }
    for key in key_order:
        if tips.get(key):
            lead = separator_map.get(key, key.capitalize() + ':')
            speak(f"{lead} {tips[key]}")
