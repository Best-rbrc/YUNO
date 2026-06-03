"""
Sprachausgabe (TTS) mit OpenAI
"""
import os
import tempfile

from src.openai_api import generate_speech_audio, generate_greeting_text

try:
    import pygame
    pygame.mixer.init()
except Exception:
    pygame = None


def speak(text: str, voice: str = "alloy"):
    """
    Spricht den Text mit OpenAI TTS aus.
    
    Args:
        text: Der zu sprechende Text
        voice: OpenAI Stimme (alloy, echo, fable, onyx, nova, shimmer)
    """
    if not text:
        return
    
    print(f'🔊 "{text}"')
    
    try:
        # Generiere Audio mit OpenAI TTS
        audio_data = generate_speech_audio(text, voice)
        
        # Speichere in temporäre Datei
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_audio:
            temp_audio.write(audio_data)
            temp_path = temp_audio.name
        
        # Spiele Audio ab
        if pygame:
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()
        
        # Lösche temporäre Datei
        try:
            os.unlink(temp_path)
        except:
            pass
            
    except Exception as e:
        print(f"⚠️ TTS Fehler: {e}")


def generate_and_speak_greeting(person_data: dict):
    """
    Generiert mit OpenAI eine personalisierte Erinnerung und spricht sie aus.
    Der Assistant erinnert den BENUTZER daran, woher er die Person kennt.
    
    Args:
        person_data: Dictionary mit:
            - name: str
            - context: str (Kontext/Geschichte der Person)
            - created_at: str (Datum des ersten Treffens)
    """
    name = person_data.get('name', 'unknown')
    
    try:
        # Generiere personalisierten Text mit OpenAI
        reminder_text = generate_greeting_text(person_data)
        
        # Sprich den generierten Text aus
        speak(reminder_text)
        
    except Exception as e:
        print(f"⚠️ Error generating the reminder: {e}")
        # Fallback
        if name and name != "unknown":
            speak(f"This is {name}.")
        else:
            speak("Person recognized, but no details available.")


def speak_unknown_person():
    """Announce an unknown person (without adding to the database)."""
    speak("Unknown person detected.")
