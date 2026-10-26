# Yuno – Augmenting Human Memory in Social Contexts

**Smart glasses that help you remember the people you meet.** Yuno recognizes a face in real time and gives you a short audio cue: who the person is and what you talked about last time.

📄 **Published at ACM DIS 2026 (Interactivity / Live Demo), Singapore**
*Yuno: Augmenting Human Memory in Social Contexts Through Real-Time Face Recognition and Contextual Recall*
[doi.org/10.1145/3802974.3808029](https://doi.org/10.1145/3802974.3808029)

---

## How it works

```
 Glasses camera ──► YuNet face detection ──► ArcFace embedding (512-d) ──► cosine match
                                                                              │
     Bluetooth speaker ◄── OpenAI TTS ◄── GPT-4o-mini cue ◄── person context ◄┘
                                          (name + last conversation)
```

Yuno consists of three parts that sync through Supabase as the single source of truth:

- **Yuno Glasses** (Raspberry Pi 1): a wearable prototype with camera, microphone, Bluetooth speaker and a single button. It enrolls new people (photos + a spoken note about them), recognizes known faces and speaks a short reminder.
- **Display Station** (Raspberry Pi 2): a 64×64 RGB LED matrix that shows pixel-art portraits of the people you've met, with a quiz mode controlled by an Arduino joystick to practice remembering names.
- **Web Dashboard**: a browser interface for managing people, photos and context notes.

## Key Features

- **Real-time face recognition**: YuNet detection + ArcFace ONNX embeddings with cosine similarity matching, running on a Raspberry Pi
- **Contextual recall**: spoken notes are transcribed (Whisper) and condensed into one short, useful cue (GPT-4o-mini)
- **Hands-free interaction**: a single button with press patterns for enroll, identify and sync
- **Audio feedback**: OpenAI TTS-1, or offline pyttsx3
- **Distributed architecture**: two independent Raspberry Pis + web frontend synced via Supabase (PostgreSQL + storage), no direct Pi-to-Pi communication
- **Memory training**: pixel-art slideshow and quiz mode on the LED display

## Quick Start

```bash
python -m venv venv && source venv/bin/activate   # Python 3.11 recommended
pip install -r requirements.txt                   # if DeepFace/TensorFlow errors: pip install tf-keras
cp config/.env.example config/.env                # add OpenAI + Supabase keys
python main.py enroll      # enroll a new person (photos + audio note)
python main.py identify    # recognize and speak a reminder
python main.py button      # Raspberry Pi button mode
```

Full setup instructions are below. Hardware assembly is in [HARDWARE.md](HARDWARE.md).

## Documentation

- **[HARDWARE.md](HARDWARE.md)**: hardware setup for both Raspberry Pis and the Arduino controller (wiring, MQTT, power)
- **[src/README.md](src/README.md)**: backend modules (recognition pipeline, matching thresholds, Supabase, OpenAI integration)
- **[frontend/README.md](frontend/README.md)**: web dashboard
- **[waveshare/README.md](waveshare/README.md)**: LED matrix display system and quiz mode

## Experimental Features

The codebase also contains research prototypes that are not part of the core memory-assistant experience: a DeepFace-based attribute-detection module and a "social tips" mode (`python main.py rizz`) that generates conversation suggestions. They were built for exploration and testing.

---

##  Repository Structure

```
yuno/
├── README.md                          # This file - project overview
├── HARDWARE.md                        # Complete hardware setup guide
├── requirements.txt                   # Python dependencies
├── main.py                            # CLI entry point for all operations
│
├── config/                            # Configuration files
│   ├── .env                           # API keys (OpenAI, Supabase) - create this!
│   ├── .env.example                   # Example environment variables template
│   └── settings.yaml                  # App settings (language, thresholds, etc.)
│
├── models/                            # Pre-trained models
│   ├── w600k_r50.onnx                 # ArcFace face recognition model (required)
│   ├── face_detection_yunet_2023mar.onnx  # YuNet face detector (auto-downloaded)
│   └── README.md                      # Model information and download links
│
├── data/                              # Local data storage (auto-created)
│   ├── database/                      # SQLite database
│   │   └── memory.db                  # Local person database
│   ├── persons/                       # Enrolled person folders
│   │   └── person_X_Name/             # Individual person data
│   │       ├── faces/                 # Face images for training
│   │       ├── embeddings/            # Face embeddings (512-dim vectors)
│   │       └── audio/                 # Audio recordings
│   ├── photos/                        # Temporary photo storage
│   ├── audio/                         # Temporary audio recordings
│   └── temp/                          # Temporary processing files
│
├── src/                               # Backend source code
│   ├── README.md                      # 📖 Detailed backend documentation
│   ├── camera_manager.py              # Camera capture and frame processing
│   ├── face_recognizer.py             # Face detection and embedding generation
│   ├── identity_matcher.py            # Cosine similarity matching (threshold 0.45)
│   ├── database_handler.py            # SQLite database operations
│   ├── person_manager.py              # Person enrollment and identification
│   ├── gender_detector.py             # DeepFace gender/age/emotion detection
│   ├── rizz_mode.py                   # Social interaction tips generation
│   ├── rizz_orchestrator.py           # Rizz mode pipeline
│   ├── openai_api.py                  # OpenAI API (Whisper, GPT-4o, TTS-1)
│   ├── speech_output.py               # Audio playback (pygame, pyttsx3)
│   ├── audio_recorder.py              # Microphone recording (sounddevice)
│   ├── supabase_handler.py            # Supabase database and storage client
│   ├── sync_manager.py                # Bidirectional sync (local ↔ Supabase)
│   ├── input_handler.py               # Raspberry Pi GPIO button handler
│   └── path_manager.py                # File path management utilities
│
├── frontend/                          # Web dashboard
│   ├── README.md                      # 📖 Frontend documentation
│   ├── index.html                     # Single-page web application
│   ├── SUPABASE_SETUP.md              # Supabase configuration guide
│   └── src/
│       └── components/
│           └── PersonCard.jsx         # React component (if migrating)
│
├── waveshare/                         # RGB LED matrix display system
│   ├── README.md                      # 📖 WaveShare display documentation
│   ├── main_app.py                    # Main display application (700+ lines)
│   ├── data_loader.py                 # Fetch persons from Supabase
│   ├── pixel_art_generator.py         # Convert photos to 64x64 pixel art
│   ├── cache/                         # Photo cache directory
│   │   └── photos/                    # Cached person photos (person_X.jpg)
│   ├── sounds/                        # Background music playlist (.wav files)
│   └── simulation_output/             # Test output for debugging
│
├── Arduino/                           # Arduino firmware
│   └── Commands_Senden_UP_RIGHT_LEFT_DOWN/
│       └── Commands_Senden_UP_RIGHT_LEFT_DOWN.ino
│           # Arduino UNO R4 WiFi firmware for LCD display and joystick
│           # Connects to MQTT broker on Raspberry Pi 2 (WaveShare)
│           # Controls: UP/DOWN/LEFT/RIGHT joystick + button press
│           # Displays: Person name and description on 16x2 LCD
│
└── tests/                             # Test scripts for development
    ├── test_face_detection.py         # Test face detection on static images
    ├── test_face_identification.py    # Test face recognition accuracy
    ├── test_face_identification_with_context.py  # Test with person context
    ├── test_gender_detection.py       # Test gender detection on images
    ├── test_gender_video.py           # Test gender detection on video stream
    └── test_gender_with_pickuplines.py  # Test Rizz mode pipeline
```

---

## Quick Start

### Prerequisites
- **Python 3.11+** recommended
- **Raspberry Pi OS** (for hardware systems) or macOS/Linux (for development)
- **Supabase Account** (free tier sufficient)
- **OpenAI API Key** (for TTS and AI features)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Best-rbrc/yuno.git
   cd yuno
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # macOS/Linux
   # .\venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   # If DeepFace/TensorFlow errors:
   pip install tf-keras
   ```

4. **Configure environment**:
   Create `config/.env` (copy from `config/.env.example`):
   ```bash
   OPENAI_API_KEY=sk-proj-your-api-key-here
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-anon-public-key
   ```

5. **Adjust settings** (optional):
   Edit `config/settings.yaml`:
   ```yaml
   language: 'de'  # or 'en'
   similarity_threshold: 0.45
   ```

### Usage Commands

```bash
# Enroll a new person (camera + audio + context)
python main.py enroll

# Identify a person (camera + TTS feedback)
python main.py identify

# Identify without audio (console output only)
python main.py identify_local

# Add face photos only (no audio/context)
python main.py add_face

# Sync local database with Supabase
python main.py sync

# Raspberry Pi button mode (GPIO control)
python main.py button
```

### Hardware Systems

**Raspberry Pi 1 (Yuno Glasses)**:
```bash
# Run in button mode (wait for GPIO button press)
python main.py button
# Single button (GPIO 17):
#   1x Press  → Enroll
#   2x Press  → Identify
#   3x Press  → Experimental mode
#   Hold      → Sync
```

**Raspberry Pi 2 (WaveShare Display)**:
```bash
cd waveshare
python main_app.py
# Displays person slideshow with quiz mode
# Controlled via Arduino joystick (MQTT)
```

**Arduino LCD Controller**:
- Upload firmware from `Arduino/Commands_Senden_UP_RIGHT_LEFT_DOWN/`
- Configure WiFi and MQTT broker IP (Raspberry Pi 2)
- Joystick controls quiz navigation on WaveShare display

---

## Configuration Files

### `config/.env` - API Keys and Secrets
```bash
# OpenAI (required for TTS and text generation)
OPENAI_API_KEY=sk-proj-...

# Supabase (required for cloud sync and frontend)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key

# Optional: Raspberry Pi GPIO pins
NORMAL_BUTTON_PIN=17
HEARTBEAT_BUTTON_PIN=27
```

### `config/settings.yaml` - Application Settings

This YAML file controls various runtime parameters for the Yuno system:

```yaml
# Audio Recording Settings
record_duration: 20               # Duration in seconds for audio recording during enrollment
                                  # Used when capturing person context via microphone

# Language Settings
language: "de"                    # Language for TTS output and AI responses ('de' or 'en')
                                  # Affects OpenAI TTS voice and GPT response language

# File Paths (relative to project root)
photo_path: "data/photos/"        # Directory for temporary photo storage during capture
audio_path: "data/audio/"         # Directory for temporary audio recordings
database_path: "data/memory.db"   # SQLite database location (not used if Supabase sync active)

# Audio Hardware Configuration (Raspberry Pi specific)
audio_samplerate: 48000           # Sample rate in Hz (48 kHz standard for USB microphones)
                                  # Note: 44.1 kHz may not work with certain USB devices
audio_device_name: "AB13X USB Audio"  # Explicit USB microphone device name
                                  # Alternative ALSA format: "hw:2,0" (Card 2, Device 0)
                                  # Use `arecord -l` on Raspberry Pi to list available devices
```

**Common Configuration Adjustments**:

- **Change language**: Set `language: "en"` for English TTS and responses
- **Longer context recording**: Increase `record_duration: 30` for more detailed descriptions
- **Different microphone**: Update `audio_device_name` to match your USB device (check with `arecord -l`)
- **Audio issues**: Try different `audio_samplerate` values (44100, 48000, 96000) if recording fails

**Note**: The `database_path` setting is primarily for standalone/offline mode. When Supabase is configured in `.env`, the system automatically syncs with the cloud database.

---

## Testing

The `tests/` folder contains various test scripts for development:

- **`test_face_detection.py`**: Test face detection on static images
- **`test_face_identification.py`**: Test face recognition accuracy on enrolled persons
- **`test_face_identification_with_context.py`**: Test identification with context display
- **`test_gender_detection.py`**: Test gender detection on individual images
- **`test_gender_video.py`**: Test real-time gender detection on video stream
- **`test_gender_with_pickuplines.py`**: Test complete Rizz mode pipeline

Run tests:
```bash
python tests/test_face_detection.py
python tests/test_gender_video.py
```

---

## Database & Cloud Sync

### Supabase Schema
**Table: `persons`**
- `id` (int, primary key)
- `name` (text)
- `gender` (text)
- `context` (text) - Description/notes about the person
- `photo_url` (text) - Public URL to profile photo in Supabase Storage
- `audio_url` (text, optional) - URL to audio recording
- `created_at` (timestamp)

**Storage Buckets**:
- `person-photos`: Profile photos (private, use signed URLs)
- `person-audio`: Audio recordings (optional)

### Sync Behavior
- **Enroll/Identify on Pi 1**: Automatically syncs to Supabase
- **WaveShare Display (Pi 2)**: Fetches persons from Supabase every 5 minutes
- **Frontend**: Directly queries Supabase via JavaScript client
- **Conflict Resolution**: Supabase is the single source of truth

---

## Frontend Dashboard

Access the web dashboard:
```bash
# Option 1: Direct file access
open frontend/index.html  # macOS
start frontend/index.html  # Windows

# Option 2: HTTP server
cd frontend
python3 -m http.server 8000
# Open http://localhost:8000
```

Features:
- View all enrolled persons
- Edit person name and context
- Upload new photos
- Delete persons
- Real-time sync with Supabase
 **See [frontend/README.md](frontend/README.md) for detailed usage**

---

## Development Notes

### Project Structure Philosophy
- **Modular Architecture**: Each module has a single responsibility
- **Supabase as SSoT**: All systems sync via Supabase, no direct inter-Pi communication
- **Dual Operation Modes**: Standalone (Raspberry Pi) and development (Mac/PC)
- **Hardware Abstraction**: Same codebase runs on Pi and desktop with minimal changes

### Key Technologies
- **Face Recognition**: ArcFace ONNX (w600k_r50 model)
- **Face Detection**: YuNet CNN detector (`cv2.FaceDetectorYN`), with OpenCV Haar cascade fallback
- **Gender/Age Detection**: DeepFace with TensorFlow backend
- **Cloud Backend**: Supabase (PostgreSQL + Storage)
- **AI Services**: OpenAI (Whisper, GPT-4o-mini, TTS-1)
- **Audio**: sounddevice, pygame, pyttsx3
- **Hardware**: Raspberry Pi GPIO, WaveShare RGB LED matrix, Arduino WiFi

### Adding New Features
1. **Backend**: Add module to `src/` and document in `src/README.md`
2. **Frontend**: Extend `frontend/index.html` and update `frontend/README.md`
3. **Hardware**: Update `HARDWARE.md` with wiring and setup instructions
4. **Tests**: Create test script in `tests/` folder

---

## Troubleshooting

### Common Issues

**DeepFace/TensorFlow Error**:
```bash
pip install tf-keras
```

**Camera Not Detected**:
```bash
# Check available cameras
ls /dev/video*  # Linux/Pi
# Or try different camera_index in settings.yaml
```

**Supabase Connection Failed**:
- Verify `SUPABASE_URL` and `SUPABASE_KEY` in `.env`
- Check internet connection
- Ensure Supabase project is active

**Frontend Images Not Loading**:
- Check Supabase Storage bucket permissions
- Ensure signed URLs are generated correctly
- Verify RLS policies allow public access

**MQTT Connection Timeout** (Arduino ↔ Pi 2):
- Verify Raspberry Pi 2 IP address in Arduino code
- Check Mosquitto broker is running: `sudo systemctl status mosquitto`
- Test MQTT: `mosquitto_sub -h localhost -t '#'`

**GPIO Permission Denied** (Raspberry Pi):
```bash
sudo usermod -aG gpio $USER
sudo reboot
```

---

## License & Attribution

- **ArcFace Model**: w600k_r50.onnx from [InsightFace](https://github.com/deepinsight/insightface)
- **DeepFace**: [serengil/deepface](https://github.com/serengil/deepface)
- **Supabase**: [supabase.io](https://supabase.io)
- **OpenAI**: [platform.openai.com](https://platform.openai.com)

---

## Quick Links

-  **[HARDWARE.md](HARDWARE.md)** - Complete hardware setup guide
-  **[src/README.md](src/README.md)** - Backend technical documentation
-  **[frontend/README.md](frontend/README.md)** - Web dashboard guide
-  **[waveshare/README.md](waveshare/README.md)** - Display system documentation
-  **[Arduino Firmware](Arduino/Commands_Senden_UP_RIGHT_LEFT_DOWN/)** - LCD controller code
-  **[Tests Folder](tests/)** - Development test scripts

---

Built for the Yuno project at the University of St. Gallen · Presented at ACM DIS 2026