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
    """Send audio to OpenAI Whisper and return the transcribed text.

    A prompt biases Whisper toward accurate transcription of personal names
    from many cultures (Chinese, Malay, Indian/Tamil, Western). The configured
    language is passed only as a hint; set `language: "auto"` in settings.yaml
    to let Whisper auto-detect (better for heavily multilingual settings)."""
    name_hint = (
        "The audio may contain personal names from many cultures, including "
        "Chinese, Malay, Indian/Tamil, and Western names. Transcribe all names "
        "accurately and preserve their original spelling."
    )
    kwargs = {
        "model": "whisper-1",
        "prompt": name_hint,
    }
    lang = config.get("language")
    if lang and str(lang).lower() != "auto":
        kwargs["language"] = lang

    with open(file_path, "rb") as audio_file:
        kwargs["file"] = audio_file
        transcript = client.audio.transcriptions.create(**kwargs)
    return transcript.text

def analyze_text(text):
    """
    Analyze a conversation snippet and return structured data.
    Uses Structured Outputs to guarantee valid JSON.

    Returns:
        dict: Dictionary with fields name, topic, mood, context
    """
    import json

    prompt = f"""Analyze this conversation snippet and return structured data:
    - name: The person's full name if mentioned. Capture the COMPLETE name exactly
      as spoken, preserving every part and the original spelling. This includes
      non-Western names (e.g. Chinese, Malay, Indian/Tamil). Do NOT anglicize,
      translate, shorten, or reorder the name. If no name is mentioned, return "".
    - topic: The main topic of the conversation
    - mood: The mood/feeling of the conversation
    - context: Additional context or information

    Conversation:
    {text}
    """

    # JSON Schema for Structured Outputs
    json_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The person's full name as spoken, original spelling preserved, or \"\" if none"
            },
            "topic": {
                "type": "string",
                "description": "Main topic of the conversation"
            },
            "mood": {
                "type": "string",
                "description": "Mood or feeling of the conversation"
            },
            "context": {
                "type": "string",
                "description": "Context or additional information"
            }
        },
        "required": ["name", "topic", "mood", "context"],
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

    # Parse JSON from the response
    content = response.choices[0].message.content
    return json.loads(content)

# Instruction steering the TTS voice to pronounce names in their native
# language/accent instead of anglicizing them. Only used by gpt-4o-mini-tts.
TTS_PRONUNCIATION_INSTRUCTIONS = (
    "Speak naturally, warmly and clearly. Pronounce personal names accurately in "
    "their native language and accent — including Chinese (Mandarin), Malay, "
    "Indian/Tamil and Western names — rather than anglicizing them."
)


def generate_speech_audio(text: str, voice: str = "alloy"):
    """
    Generate audio with OpenAI TTS.

    Prefers `gpt-4o-mini-tts`, which accepts pronunciation instructions and
    handles multilingual names (e.g. Chinese/Malay/Tamil) far better than the
    older `tts-1`. Falls back to `tts-1` if the newer model is unavailable.

    Args:
        text: The text to speak
        voice: OpenAI voice (alloy, echo, fable, onyx, nova, shimmer)

    Returns:
        bytes: Audio data in MP3 format
    """
    try:
        response = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice=voice,
            input=text,
            instructions=TTS_PRONUNCIATION_INSTRUCTIONS,
        )
        return response.content
    except Exception as e:
        # Fallback for older SDKs / models without `instructions` support
        print(f"⚠️ gpt-4o-mini-tts unavailable ({e}); falling back to tts-1")
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        return response.content

def generate_greeting_text(person_data: dict):
    """
    Generate a personalized memory reminder with OpenAI.

    Args:
        person_data: Dictionary with:
            - name: str
            - context: str (context/history of the person)
            - created_at: str (date of first meeting)

    Returns:
        str: Generated reminder text
    """
    name = person_data.get('name', 'unknown')
    context = person_data.get('context', '')
    created_at = person_data.get('created_at', '')

    prompt = f"""You are a personal memory assistant for the user. The user is currently looking at a person and you help them remember who it is.

Information about the recognized person:
Name: {name}
First meeting: {created_at}
Context/Information: {context}

Write a short reminder (maximum 2-3 sentences) FOR THE USER, addressing them directly as "you":
- Who the person is (name)
- How YOU (the user) know this person
- When you met

IMPORTANT: Address the user directly as "you"! Keep the person's name exactly as written above — do not anglicize or change its spelling.

Good examples:
- "This is Jannik. You know him from the HCI course you attended on October 28, 2025."
- "This is Anna. You met her last month at yoga."
- "This is Max, your colleague from the marketing team. You saw each other last week at the team meeting."

Bad examples (do NOT do this):
- "This is Jannik. He is an acquaintance from the HCI course that he attended." ❌
- "This is Anna. She was met at yoga." ❌

Generate ONLY the reminder addressed to "you", without any additional explanations."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Cost-effective model for text generation
        messages=[
            {"role": "system", "content": "You are a memory assistant that helps the user remember people."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=150
    )

    return response.choices[0].message.content.strip()