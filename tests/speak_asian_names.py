"""
Speak Asian / non-ASCII names aloud through the real TTS path
(src.speech_output.speak -> OpenAI gpt-4o-mini-tts -> pygame playback).

Requires: config/.env with OPENAI_API_KEY, network access, working audio out.
Run from the project root:  python tests/speak_asian_names.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.speech_output import speak

NAMES = ["田中", "山田太郎", "김민준", "佐藤 花子", "Nguyễn"]

if __name__ == "__main__":
    for n in NAMES:
        sentence = f"Hello, this is {n}."
        speak(sentence)          # generates audio and plays it
        time.sleep(0.4)          # small gap between names
    print("Done.")
