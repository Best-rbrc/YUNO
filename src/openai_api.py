import yaml
import os
from dotenv import load_dotenv
from openai import OpenAI

# 1️⃣ Load .env file for secrets
load_dotenv(dotenv_path="config/.env")

# 2️⃣ Load settings.yaml for configuration
with open("config/settings.yaml", "r") as f:
    config = yaml.safe_load(f)

# 3️⃣ Initialize OpenAI client using API key from .env
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("❌ Missing OPENAI_API_KEY in .env file!")

client = OpenAI(api_key=api_key)

def transcribe_audio(file_path):
    """Sendet Audio an OpenAI Whisper und gibt Text zurück."""
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=config["language"]
        )
    return transcript.text

def analyze_text(text):
    """
    Analysiert einen Gesprächsauszug und gibt strukturierte Daten zurück.
    Verwendet Structured Outputs für garantiertes JSON-Format.
    
    Returns:
        dict: Dictionary mit Feldern name, thema, stimmung, kontext
    """
    import json
    
    prompt = f"""
    Analysiere diesen Gesprächsauszug und gib strukturierte Daten zurück:
    - name: Name der Person (falls erwähnt)
    - thema: Hauptthema des Gesprächs
    - stimmung: Stimmung/Gefühl des Gesprächs
    - kontext: Kontext oder zusätzliche Informationen

    Gespräch:
    {text}
    """
    
    # JSON Schema für Structured Outputs
    json_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name der Person, falls im Gespräch erwähnt"
            },
            "thema": {
                "type": "string",
                "description": "Hauptthema des Gesprächs"
            },
            "stimmung": {
                "type": "string",
                "description": "Stimmung oder Gefühl des Gesprächs"
            },
            "kontext": {
                "type": "string",
                "description": "Kontext oder zusätzliche Informationen"
            }
        },
        "required": ["name", "thema", "stimmung", "kontext"],
        "additionalProperties": False  # Required for strict mode
    }
    
    response = client.beta.chat.completions.create(
        model="gpt-4o-mini",  # Structured Outputs supported model
        messages=[{"role": "user", "content": prompt}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "conversation_analysis",
                "strict": True,
                "schema": json_schema
            }
        }
    )
    
    # Parse JSON aus der Response
    content = response.choices[0].message.content
    return json.loads(content)

def generate_speech_audio(text: str, voice: str = "alloy"):
    """
    Generiert Audio mit OpenAI TTS.
    
    Args:
        text: Der zu sprechende Text
        voice: OpenAI Stimme (alloy, echo, fable, onyx, nova, shimmer)
    
    Returns:
        bytes: Audio-Daten im MP3-Format
    """
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text
    )
    return response.content

def generate_greeting_text(person_data: dict):
    """
    Generiert mit OpenAI eine personalisierte Erinnerung.
    
    Args:
        person_data: Dictionary mit:
            - name: str
            - context: str (Kontext/Geschichte der Person)
            - created_at: str (Datum des ersten Treffens)
    
    Returns:
        str: Generierter Erinnerungstext
    """
    name = person_data.get('name', 'unknown')
    context = person_data.get('context', '')
    created_at = person_data.get('created_at', '')
    
    prompt = f"""Du bist ein persönlicher Memory-Assistent für den Benutzer. Der Benutzer sieht gerade eine Person und du hilfst ihm sich zu erinnern, wer das ist.

Informationen über die erkannte Person:
Name: {name}
Erstes Treffen: {created_at}
Kontext/Informationen: {context}

Erstelle eine kurze Erinnerung (maximal 2-3 Sätze) FÜR DEN BENUTZER in der DU-Form:
- Wer die Person ist (Name)
- Woher DU (der Benutzer) die Person kennst
- Wann IHR euch getroffen habt

WICHTIG: Sprich den Benutzer direkt mit "Du" an!

Richtige Beispiele:
- "Das ist Jannik. Du kennst ihn vom HCI Kurs, den du am 28. Oktober 2025 besucht hast."
- "Das ist Anna. Du hast sie letzten Monat beim Yoga kennengelernt."
- "Das ist Max, dein Kollege aus dem Marketing Team. Ihr habt euch letzte Woche bei der Teambesprechung gesehen."

FALSCHE Beispiele (NICHT so):
- "Das ist Jannik. Er ist ein Bekannter aus dem HCI-Kurs, den er getroffen hat." ❌
- "Das ist Anna. Sie wurde beim Yoga kennengelernt." ❌

Generiere NUR die Erinnerung in der DU-Form, ohne zusätzliche Erklärungen."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Cost-effective model for text generation
        messages=[
            {"role": "system", "content": "Du bist ein Memory-Assistent der dem Benutzer hilft, sich an Menschen zu erinnern."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=150
    )
    
    return response.choices[0].message.content.strip()