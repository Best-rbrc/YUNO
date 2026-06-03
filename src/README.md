# src/ – Core Application Modules

This folder contains the core logic for camera capture, face recognition, identity matching, database management, Supabase synchronization, OpenAI integration, and specialized modes like Rizz Mode. Each module is designed to be modular and reusable across different application flows.

---

## Table of Contents

1. [Module Overview](#module-overview)
2. [Technology Stack](#technology-stack)
3. [Detailed Module Documentation](#detailed-module-documentation)
4. [Application Pipelines](#application-pipelines)
5. [Configuration](#configuration)
6. [Common Issues & Troubleshooting](#common-issues--troubleshooting)

---

## Module Overview

### Core Recognition & Detection
- **`face_recognizer.py`**: Face detection and embedding extraction using ArcFace ONNX
- **`identity_matcher.py`**: Cosine similarity-based identity matching against database embeddings
- **`gender_detector.py`**: Gender, age, and emotion detection using DeepFace

### Data Management
- **`database_handler.py`**: SQLite database operations for persons, embeddings, and metadata
- **`path_manager.py`**: File system structure management (per-person directories)
- **`supabase_handler.py`**: Supabase PostgreSQL and Storage client
- **`sync_manager.py`**: Bidirectional sync between local SQLite and Supabase

### Input/Output
- **`camera_manager.py`**: Multi-platform camera capture (Raspberry Pi CSI, USB, fallback)
- **`audio_recorder.py`**: Audio recording with sounddevice/pyaudio
- **`speech_output.py`**: Text-to-Speech using OpenAI TTS and pygame playback

### AI Integration
- **`openai_api.py`**: OpenAI API wrapper (Whisper, GPT-4, TTS, Structured Outputs)
- **`rizz_mode.py`**: AI-powered flirting assistant with gender-based tips
- **`rizz_orchestrator.py`**: End-to-end Rizz Mode pipeline orchestration

### High-Level Flows
- **`person_manager.py`**: Orchestrates enroll, identify, and add_face workflows
- **`input_handler.py`**: Raspberry Pi GPIO button listener for triggering actions

---

## Technology Stack

### Computer Vision & Face Recognition
- **OpenCV (`cv2`)**: Image processing, camera capture, face detection
- **ONNX Runtime (`onnxruntime`)**: Runs ArcFace model for face embeddings
- **ArcFace ONNX Model (`w600k_r50.onnx`)**: Pre-trained face recognition model generating 512-dimensional embeddings
- **YuNet (`cv2.FaceDetectorYN`)**: CNN-based face detector — robust across ethnicities and head poses, light enough for a Raspberry Pi (auto-downloaded)
- **Haar Cascade**: Legacy frontal face detector (from OpenCV), kept as an automatic fallback
- **DeepFace**: Multi-task facial analysis (gender, age, emotion, race)

### Audio Processing
- **sounddevice**: Cross-platform audio recording (primary, macOS/Linux)
- **pyaudio**: Audio recording fallback (Raspberry Pi)
- **wave**: WAV file writing
- **pygame**: Audio playback for TTS

### AI & NLP
- **OpenAI API**:
  - **Whisper**: Audio transcription (multilingual)
  - **GPT-4o-mini**: Text analysis, greeting generation, conversation analysis
  - **TTS-1**: Text-to-Speech with multiple voices
  - **Structured Outputs**: JSON schema validation for reliable parsing
  
### Database & Backend
- **SQLite3**: Local embedded database for persons and embeddings
- **Supabase Python Client**: PostgreSQL database and cloud storage integration
- **pickle**: Python object serialization (embeddings as BLOBs)

### Utilities
- **NumPy**: Numerical operations, array handling, embedding normalization
- **Pillow (PIL)**: Image manipulation, brightness enhancement, rotation
- **python-dotenv**: Environment variable management
- **PyYAML**: Configuration file parsing

---

## Detailed Module Documentation

### `camera_manager.py`

**Purpose**: Cross-platform camera capture with intelligent fallback mechanisms.

**Key Features**:
- **Raspberry Pi CSI Camera**: Primary method using `rpicam-still` (Pi 5) or `libcamera-still` (older Pi versions)
- **USB Camera Fallback**: Uses OpenCV `VideoCapture` on non-Pi systems
- **Auto-Brightness**: Detects dark images and applies automatic brightness enhancement
- **180° Rotation**: Built-in image rotation for camera mounting orientation
- **Multi-Photo Capture**: Callback-based function for capturing multiple photos during audio recording
- **Camera Availability Check**: Pre-flight check to detect camera hardware

**Technologies Used**:
- `subprocess` for calling system camera utilities (`rpicam-still`, `libcamera-still`)
- OpenCV for USB camera capture and brightness analysis
- Pillow for image enhancement and rotation
- NumPy for brightness calculations

**Configuration**:
- Camera resolution: 1920x1080 (Full HD)
- Timeout: 2 seconds for capture
- No preview mode (headless operation)

---

### `face_recognizer.py`

**Purpose**: Face detection and embedding extraction using ArcFace ONNX model.

**Key Features**:
- **ArcFace Model**: State-of-the-art face recognition with 512-dimensional embeddings
- **YuNet Detection**: CNN-based face detection (`cv2.FaceDetectorYN`), robust across ethnicities/poses; falls back to Haar Cascade if YuNet is unavailable
- **Face Validation**: Multi-criteria validation to reduce false positives:
  - Aspect ratio check (0.6-1.5)
  - Minimum size threshold (100x100 pixels)
  - Brightness variance check
  - Image quality validation
- **Center-Priority Selection**: Prioritizes faces closest to frame center
- **Multi-Face Support**: Can detect and process all faces in a frame
- **Preprocessing Pipeline**: BGR→RGB conversion, normalization to [-1,1], CHW format
- **L2 Normalization**: Embeddings are normalized for cosine similarity

**Technologies Used**:
- **ONNX Runtime**: Efficient model inference
- **YuNet (`cv2.FaceDetectorYN`)**: Primary CNN detector (`face_detection_yunet_2023mar.onnx`)
- **OpenCV Haar Cascade**: `haarcascade_frontalface_default.xml` (fallback)
- **NumPy**: Embedding normalization and array operations

**Model Specifications**:
- Input: 112×112 RGB image (CHW format)
- Output: 512-dimensional float32 embedding
- Normalization: L2 (unit vector)

**Detection Parameters**:
- YuNet score threshold: 0.6 · NMS threshold: 0.3
- Haar fallback — scale factor: 1.1, min neighbors: 7 (higher = fewer false positives), min size: 100×100 pixels

---

### `identity_matcher.py`

**Purpose**: Match face embeddings against stored database embeddings using cosine similarity.

**Key Features**:
- **Cosine Similarity**: Dot product of L2-normalized embeddings
- **Threshold-Based Matching**: Default threshold of 0.45 (configurable)
- **Best Candidates**: Returns top 3 matches with similarity scores
- **Suggestion Threshold**: 0.40 for "best guess" when no confident match

**Technologies Used**:
- **NumPy**: Dot product calculation
- **SQLite3**: Database queries for stored embeddings
- **pickle**: Deserialization of BLOB embeddings

**Matching Logic**:
```python
similarity = np.dot(embedding1, embedding2)  # For normalized embeddings
if similarity >= 0.45:  # Match found
    return person_id, name, similarity
```

**Similarity Ranges**:
- 0.90-1.00: Very high confidence (same person)
- 0.70-0.89: High confidence
- 0.45-0.69: Match threshold
- 0.40-0.44: Suggestion only
- < 0.40: No match

---

### `database_handler.py`

**Purpose**: SQLite database operations for person records and face embeddings.

**Schema**:
```sql
CREATE TABLE persons (
    id INTEGER PRIMARY KEY,
    name TEXT,
    context TEXT,
    photo_path TEXT,
    audio_path TEXT,
    embedding BLOB,  -- Pickled NumPy array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sync_metadata (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Key Functions**:
- `init_db()`: Create tables if not exist
- `add_person()`: Insert new person with embedding
- `update_person()`: Update person data (appends context, replaces files)
- `get_person_by_id()`: Retrieve person details
- `get_all_embeddings()`: Fetch all embeddings for matching
- `bulk_insert_persons()`: Efficient batch insert for sync
- `get/set_local_db_version()`: Version tracking for sync

**Technologies Used**:
- **SQLite3**: Embedded SQL database
- **pickle**: Embedding serialization/deserialization
- **NumPy**: Embedding array handling

**Location**: `data/database/memory.db`

---

###  `path_manager.py`

**Purpose**: Manages file system structure with per-person directories.

**Directory Structure**:
```
data/
├── database/
│   └── memory.db
└── persons/
    ├── person_1_MaxMustermann/
    │   ├── profile.jpg
    │   ├── audio.wav
    │   └── faces/
    │       ├── face_001.jpg
    │       ├── face_002.jpg
    │       └── ...
    ├── person_2_AnnaSchmidt/
    └── ...
```

**Key Features**:
- **Name Sanitization**: Removes special characters from names
- **Person Directory Creation**: `person_{id}_{name}/` format
- **Face Collection**: Separate `faces/` subdirectory for multiple face images
- **Path Resolution**: Centralized path management for all modules

**Technologies Used**:
- **os/pathlib**: File system operations
- **re**: Regular expressions for name sanitization

---

###  `supabase_handler.py`

**Purpose**: Supabase PostgreSQL and Storage integration for cloud sync.

**Key Features**:
- **Database Operations**: CRUD operations on `persons` table
- **Storage Management**: Upload/download photos and audio files
- **Signed URLs**: Generate temporary URLs for private storage buckets
- **Embedding Serialization**: Hex encoding for BYTEA column
- **Error Handling**: Graceful fallback when Supabase unavailable

**Technologies Used**:
- **supabase-py**: Official Python client
- **pickle**: Embedding serialization
- **requests**: HTTP operations for signed URLs

**Storage Buckets**:
- `persons-photos`: Profile images
- `persons-audio`: Audio recordings

**Environment Variables**:
- `SUPABASE_URL`: Project URL
- `SUPABASE_KEY`: Service role or anon key

---

###  `sync_manager.py`

**Purpose**: Bidirectional synchronization between local SQLite and Supabase.

**Sync Strategies**:
1. **Pull from Supabase**: Download all persons and files to local
2. **Push to Supabase**: Upload local persons and files to cloud
3. **Version Tracking**: Prevents unnecessary re-downloads

**Key Features**:
- **File Downloads**: Parallel download of photos and audio
- **Local Caching**: Avoids re-downloading unchanged files
- **Batch Operations**: Efficient bulk inserts
- **Auto-Retry**: Handles transient network errors
- **Background Sync**: Can run as daemon process

**Technologies Used**:
- **SupabaseHandler**: Cloud operations
- **DatabaseHandler**: Local operations
- **PathManager**: File system management
- **datetime/timedelta**: Cooldown periods

---

###  `audio_recorder.py`

**Purpose**: Cross-platform audio recording with real-time callbacks.

**Key Features**:
- **Platform Detection**: Automatically selects sounddevice (macOS/Linux) or pyaudio (Pi)
- **Device Selection**: By name or ID from configuration
- **Progress Callbacks**: Real-time elapsed time updates
- **Quality Settings**: 44.1kHz sample rate (CD quality)
- **Volume Check**: Warns if recording is too quiet
- **Thread-Safe**: Callback execution in separate thread

**Technologies Used**:
- **sounddevice**: Primary audio library (preferred)
- **pyaudio**: Fallback for Raspberry Pi
- **wave**: WAV file encoding
- **threading**: Callback management
- **NumPy**: Audio level analysis

**Configuration** (`settings.yaml`):
- `record_duration`: Recording length (default: 20s)
- `audio_samplerate`: Sample rate (default: 44100 Hz)
- `audio_device_name`: Optional device name
- `audio_device_id`: Optional device ID

---

### `speech_output.py`

**Purpose**: Text-to-Speech output using OpenAI TTS and pygame playback.

**Key Features**:
- **OpenAI TTS-1**: High-quality voice synthesis
- **Voice Selection**: 6 voices (alloy, echo, fable, onyx, nova, shimmer)
- **Greeting Generation**: Personalized greetings with GPT-4o-mini
- **Memory Context**: Reminders about when/where user met someone
- **Temporary Files**: Auto-cleanup of MP3 files
- **Fallback**: Prints to console if pygame unavailable

**Technologies Used**:
- **OpenAI TTS-1**: Text-to-speech model
- **pygame.mixer**: Audio playback
- **tempfile**: Temporary MP3 storage

**Voice Characteristics**:
- **alloy**: Neutral, balanced (default)
- **echo**: Clear, articulate
- **fable**: Warm, expressive
- **onyx**: Deep, authoritative
- **nova**: Energetic, friendly
- **shimmer**: Soft, gentle

---

###  `openai_api.py`

**Purpose**: Centralized OpenAI API client with specialized functions.

**Key Functions**:

1. **`transcribe_audio(file_path)`**: 
   - Uses Whisper-1 model
   - Language: Configured in `settings.yaml`
   - Returns: Transcript text

2. **`analyze_text(text)`**:
   - Uses GPT-4o-mini with Structured Outputs
   - JSON Schema validation for guaranteed format
   - Returns: `{name, thema, stimmung, kontext}`

3. **`generate_speech_audio(text, voice)`**:
   - TTS-1 model with selectable voice
   - Returns: MP3 audio bytes

4. **`generate_greeting_text(person_data)`**:
   - Personalized memory reminders
   - Uses "Du" form (German informal)
   - Context: Name, when met, relationship
   - Returns: 2-3 sentence greeting

**Technologies Used**:
- **OpenAI Python SDK**: Official client library
- **Structured Outputs**: JSON schema enforcement
- **python-dotenv**: API key management

**Models Used**:
- **whisper-1**: Audio transcription
- **gpt-4o-mini**: Text generation (cost-effective)
- **tts-1**: Text-to-speech

---

###  `gender_detector.py`

**Purpose**: Gender, age, emotion, and race detection using DeepFace.

**Key Features**:
- **Multi-Task Analysis**: Gender, age, emotion, race in one pass
- **Multiple Models**: VGG-Face (default), ArcFace, Facenet, Dlib, OpenFace
- **Batch Processing**: Can analyze multiple faces
- **Confidence Scores**: Returns probability distributions
- **Fallback Handling**: Graceful degradation if face not detected

**Technologies Used**:
- **DeepFace**: Facial attribute analysis library
- **TensorFlow/Keras**: Backend for DeepFace models
- **tf-keras**: Compatibility layer

**Analysis Output**:
```python
{
    "gender": {"Woman": 0.87, "Man": 0.13},
    "dominant_gender": "Woman",
    "age": 28,
    "emotion": {"happy": 0.65, "neutral": 0.25, ...},
    "dominant_emotion": "happy",
    "race": {"asian": 0.01, "white": 0.85, ...},
    "dominant_race": "white"
}
```

**Models**:
- **VGG-Face**: Most accurate, slower
- **ArcFace**: Fast, accurate
- **Facenet**: Balanced
- **Dlib**: Lightweight

---

###  `rizz_mode.py` & `rizz_orchestrator.py`

**Purpose**: AI-powered flirting assistant with context-aware pickup lines.

**Rizz Mode Class** (`rizz_mode.py`):
- **Gender Detection**: Uses DeepFace to determine target gender
- **Personalized Tips**: GPT-4o-mini generates culturally appropriate tips
- **Structured Output**: JSON schema for guaranteed parsing
- **Context Integration**: Uses known person context if available
- **German Language**: Tips in German with appropriate tone

**Rizz Orchestrator** (`rizz_orchestrator.py`):
- **End-to-End Pipeline**: Camera → Face Detection → Identity Matching → Gender Detection → Tip Generation
- **No DB Writes**: Unknown persons are not persisted (privacy-focused)
- **Speech Output**: Speaks both person context and tips
- **Error Handling**: Graceful fallback at each step

**Technologies Used**:
- **OpenAI GPT-4o-mini**: Tip generation
- **DeepFace**: Gender detection
- **ArcFace**: Face recognition (for known persons)
- **TTS**: Spoken output

**Output Format**:
```json
{
    "tips": [
        {"tip": "Kompliment zu ihrer Ausstrahlung", "kategorie": "Eröffnung"},
        {"tip": "Frage nach ihrem Lieblingshobby", "kategorie": "Gesprächseinstieg"},
        {"tip": "Augenkontakt halten", "kategorie": "Körpersprache"}
    ]
}
```

---

### `person_manager.py`

**Purpose**: High-level orchestration of person enrollment, identification, and face addition.

**Workflows**:

1. **`enroll_person()`**:
   - Audio recording (20s with progress callback)
   - Multi-photo capture during recording
   - Whisper transcription
   - GPT-4o text analysis (name, context extraction)
   - Face detection and selection (center-priority)
   - Embedding generation
   - Database persistence
   - Directory structure creation
   - Optional Supabase upload

2. **`identify_person()`**:
   - Photo capture
   - Multi-face detection
   - Embedding extraction for each face
   - Database matching with similarity threshold
   - Personalized greeting generation
   - Speech output (known persons)
   - Console output (unknown persons)

3. **`identify_local()`**:
   - Same as identify but without speech output
   - Console-only mode for testing

4. **`add_face()`**:
   - Photo capture
   - Face detection
   - Check against database (unknown persons only)
   - Directory creation without audio
   - Store face with minimal metadata

**Technologies Used**:
- Orchestrates: `camera_manager`, `audio_recorder`, `face_recognizer`, `identity_matcher`, `database_handler`, `openai_api`, `speech_output`

---

### `input_handler.py`

**Purpose**: Raspberry Pi GPIO button listener for physical interaction.

**Key Features**:
- **Button Debouncing**: Prevents multiple triggers
- **Action Mapping**: Different actions for short/long press
- **Background Thread**: Non-blocking button monitoring
- **Camera Check**: Pre-flight camera availability test
- **Auto-Sync**: Periodic Supabase synchronization

**Actions**:
- **Short Press**: Identify person
- **Long Press**: Enroll new person

**Technologies Used**:
- **GPIO libraries**: RPi.GPIO or similar
- **threading**: Background monitoring
- **time**: Debouncing and timing

---

## Application Pipelines

### Enroll Pipeline (`python main.py enroll`)

**Purpose**: Register a new person with audio context and face embeddings.

**Steps**:
1. **Audio Recording** (20 seconds)
   - User speaks about the person
   - Progress displayed in console
   
2. **Multi-Photo Capture**
   - 3-5 photos taken during audio recording
   - Each photo triggers face detection
   
3. **Transcription & Analysis**
   - Whisper transcribes audio to text
   - GPT-4o extracts: name, topic, mood, context
   
4. **Face Detection**
   - All photos analyzed for faces
   - Center-priority selection for profile photo
   - Face validation to eliminate false positives
   
5. **Embedding Generation**
   - ArcFace model generates 512-dim embedding
   - L2 normalization for cosine similarity
   
6. **Database Persistence**
   - SQLite record created
   - Person ID generated
   - Embedding stored as BLOB
   
7. **File Organization**
   - Directory created: `data/persons/person_{id}_{name}/`
   - Profile photo saved
   - Audio file saved
   - Additional faces stored in `faces/` subfolder
   
8. **Cloud Sync** (Optional)
   - Upload to Supabase if configured
   - Photos → Storage bucket
   - Metadata → PostgreSQL table
   - Embedding → BYTEA column (hex-encoded)

**Error Handling**:
- No face detected: Offers retry or manual photo
- Transcription failure: Uses fallback name "Unknown"
- Database error: Transaction rollback

---

### Identify Pipeline (`python main.py identify`)

**Purpose**: Recognize known persons from camera and provide context.

**Steps**:
1. **Photo Capture**
   - Single photo from camera
   - Auto-brightness adjustment
   
2. **Multi-Face Detection**
   - YuNet detects all faces (Haar Cascade fallback)
   - Quality validation for each face
   - Bounding boxes extracted
   
3. **Embedding Extraction**
   - ArcFace processes each detected face
   - 512-dim embeddings generated
   - L2 normalization applied
   
4. **Database Matching**
   - Compare against all stored embeddings
   - Cosine similarity calculation
   - Threshold: 0.45 for positive match
   
5. **Result Processing**
   - **Known Person**:
     - Fetch person data (name, context, created_at)
     - Generate personalized greeting with GPT-4o
     - Speak greeting with OpenAI TTS
     - Display similarity score
   - **Unknown Person**:
     - Display "Unknown person" message
     - Show best candidates if similarity > 0.40
     - Console output only (no speech)
   
6. **Visual Feedback**
   - Bounding boxes drawn on photo
   - Name labels for known persons
   - Similarity scores displayed
   - Color coding: green (known), red (unknown)

**Performance**:
- Face detection: ~100-200ms
- Embedding extraction: ~50-100ms per face
- Database matching: ~10-50ms
- Total latency: ~500ms (excluding speech generation)

---

### Rizz Mode Pipeline (`python main.py rizz`)

**Purpose**: Generate gender-based flirting tips for social situations.

**Steps**:
1. **Photo Capture**
   - Single photo from camera
   
2. **Center Face Detection**
   - Prioritizes face closest to center
   - Ensures single-person targeting
   
3. **Identity Check** (Optional)
   - Attempt to match against database
   - If known: Retrieve context and relationship info
   - If unknown: Proceed without context
   
4. **Gender Detection**
   - DeepFace analyzes face
   - Returns: gender, age, emotion
   - Confidence scores provided
   
5. **Tip Generation**
   - GPT-4o-mini creates personalized tips
   - Input: gender, age (optional), known context (optional)
   - Output: 3-5 structured tips in German
   - Categories: Eröffnung, Gesprächseinstieg, Körpersprache, Komplimente
   
6. **Speech Output**
   - If known person: Speak context first
   - Speak generated tips
   - OpenAI TTS with "alloy" voice
   
7. **Privacy**
   - **No database writes** for unknown persons
   - Tips are ephemeral (not stored)
   - No photos saved

**Tip Structure**:
```json
{
    "tips": [
        {
            "tip": "Authentisches Kompliment zu ihrer Ausstrahlung",
            "kategorie": "Eröffnung"
        },
        {
            "tip": "Frage nach ihrem Lieblingsreiseziel",
            "kategorie": "Gesprächseinstieg"
        },
        {
            "tip": "Offene Körperhaltung zeigen",
            "kategorie": "Körpersprache"
        }
    ]
}
```

---

## Configuration

### Environment Variables (`config/.env`)

```bash
# OpenAI Configuration (Required)
OPENAI_API_KEY=sk-proj-...

# Supabase Configuration (Optional, for cloud sync)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJhbGc...  # Service role key preferred
```

### Settings File (`config/settings.yaml`)

```yaml
# Language for Whisper transcription and TTS
language: 'de'  # 'de' for German, 'en' for English

# Audio Recording Settings
record_duration: 20  # seconds
audio_samplerate: 44100  # Hz (CD quality)

# Optional: Specific audio device
# audio_device_name: "USB Microphone"  # Device name (partial match)
# audio_device_id: 0  # Or device ID

# OpenAI Voice Selection
tts_voice: "alloy"  # alloy, echo, fable, onyx, nova, shimmer
```

---

## Common Issues & Troubleshooting

###  DeepFace / TensorFlow Errors

**Error**: `AttributeError: module 'keras.api._v2.keras.xxx' has no attribute 'yyy'`

**Solution**:
```bash
pip install tf-keras
```

**Explanation**: DeepFace requires TensorFlow's Keras implementation. Recent TensorFlow versions need the `tf-keras` compatibility package.

---

###  Missing ArcFace Model

**Error**: `FileNotFoundError: Model not found: models/w600k_r50.onnx`

**Solution**:
1. Ensure `models/` directory exists in project root
2. Download the ArcFace ONNX model:
   ```bash
   cd models
   # Download from official source or use provided model
   ```
3. Verify file exists: `ls -lh models/w600k_r50.onnx`

**Model Specs**:
- Size: ~166 MB
- Format: ONNX (cross-platform)
- Architecture: ResNet-50 backbone

---

###  Raspberry Pi Camera Not Detected

**Error**: `no cameras available`

**Solution**:
1. Enable camera interface:
   ```bash
   sudo raspi-config
   # → Interface Options → Camera → Enable
   # Reboot after enabling
   ```

2. Test camera:
   ```bash
   rpicam-hello --timeout 2000
   ```

3. Check camera connection:
   - CSI cable firmly connected to port J4
   - Blue side of ribbon facing USB ports
   - Camera module compatible with Pi 5

4. Update firmware:
   ```bash
   sudo apt update
   sudo apt upgrade
   sudo rpi-update
   ```

---

###  No Audio Playback (Headless Systems)

**Issue**: pygame mixer not available on headless Raspberry Pi

**Behavior**: 
- TTS text printed to console
- No audio playback
- Application continues normally

**Solution** (if audio needed):
1. Install ALSA libraries:
   ```bash
   sudo apt-get install libasound2-dev
   ```

2. Configure audio output:
   ```bash
   sudo raspi-config
   # → System Options → Audio → Select output device
   ```

3. Test audio:
   ```bash
   speaker-test -t wav -c 2
   ```

---

###  Supabase Connection Failures

**Error**: Connection timeout or authentication failure

**Checklist**:
1. Verify `.env` file exists in `config/` directory
2. Check `SUPABASE_URL` format: `https://xxx.supabase.co`
3. Verify `SUPABASE_KEY` is service role key (full access) or anon key with RLS policies
4. Test connection:
   ```bash
   python -c "from src.supabase_handler import SupabaseHandler; h = SupabaseHandler(); print(h.client)"
   ```

5. Check Supabase project status in dashboard
6. Verify RLS policies allow your operations

---

### Low Face Recognition Accuracy

**Issue**: Faces not matching correctly or too many false positives

**Tuning Parameters** in `face_recognizer.py`:

1. **Detection Strictness**:
   ```python
   # YuNet (primary): raise the score threshold to reduce false positives
   YUNET_SCORE_THRESHOLD = 0.6  # Higher = stricter

   # Haar Cascade (fallback): raise minNeighbors to reduce false positives
   faces = self.face_cascade.detectMultiScale(
       gray,
       scaleFactor=1.1,
       minNeighbors=7,  # Default: 7, Higher = stricter
       minSize=(100, 100)  # Minimum face size
   )
   ```

2. **Matching Threshold** in `identity_matcher.py`:
   ```python
   THRESHOLD = 0.45  # Default: 0.45
   # Lower = more strict (fewer false matches)
   # Higher = more lenient (more matches but less accurate)
   ```

3. **Image Quality**:
   - Ensure good lighting
   - Face directly facing camera
   - Minimal occlusion (no masks, sunglasses)
   - Distance: 0.5-2 meters from camera

---

###  Database Lock Errors

**Error**: `sqlite3.OperationalError: database is locked`

**Causes**:
- Multiple processes accessing database simultaneously
- Long-running transaction

**Solutions**:
1. Ensure only one instance of application running
2. Add timeout to connections:
   ```python
   conn = sqlite3.connect(db_path, timeout=10.0)
   ```
3. Close connections properly:
   ```python
   conn.close()  # Always close after operations
   ```

---

###  Audio Recording Too Quiet

**Issue**: Whisper transcription fails due to low audio level

**Solutions**:
1. Check microphone selection in `settings.yaml`:
   ```yaml
   audio_device_name: "Your Microphone Name"
   ```

2. List available devices:
   ```python
   import sounddevice as sd
   print(sd.query_devices())
   ```

3. Increase system microphone gain:
   - **macOS**: System Preferences → Sound → Input → Input Volume
   - **Linux**: `alsamixer` → F4 (capture) → adjust levels
   - **Raspberry Pi**: `alsamixer` → adjust capture levels

4. Check recording level warning:
   ```
   ⚠️  Warnung: Aufnahme sehr leise! Prüfe Mikrofon-Lautstärke.
   Max Pegel: 3.2%  # Should be > 5%
   ```

---

## Performance Metrics

**Typical Latency** (Raspberry Pi 5):
- Photo capture: 1-2 seconds
- Face detection: 100-200ms
- Embedding extraction: 50-100ms per face
- Database matching: 10-50ms
- Total identification: ~2-3 seconds

**Typical Latency** (MacBook Pro M1):
- Photo capture: <100ms
- Face detection: 20-50ms
- Embedding extraction: 10-20ms per face
- Database matching: 5-10ms
- Total identification: ~200-500ms

**Model Sizes**:
- ArcFace ONNX: ~166 MB
- DeepFace models: 150-300 MB (cached on first use)

**Database Size**:
- Per person: ~500 KB - 2 MB (depends on photo quality)
- Embedding: 2 KB (512 floats × 4 bytes)
- 100 persons ≈ 50-200 MB total

---

##  Privacy & Security Notes

1. **Local-First**: All data stored locally by default
2. **Optional Cloud**: Supabase sync is opt-in
3. **Embedding Security**: Embeddings cannot be reversed to reconstruct faces
4. **No Tracking**: No analytics or external tracking
5. **Rizz Mode Privacy**: Unknown persons not saved to database
6. **Audio Cleanup**: Temporary audio files deleted after processing
7. **API Keys**: Keep `.env` file out of version control (add to `.gitignore`)

---

## Additional Resources

- **ArcFace Paper**: [ArcFace: Additive Angular Margin Loss for Deep Face Recognition](https://arxiv.org/abs/1801.07698)
- **DeepFace Documentation**: [https://github.com/serengil/deepface](https://github.com/serengil/deepface)
- **OpenAI API Docs**: [https://platform.openai.com/docs](https://platform.openai.com/docs)
- **Supabase Docs**: [https://supabase.com/docs](https://supabase.com/docs)

---

## Contributing

When modifying modules, follow these principles:
1. **Separation of Concerns**: Each module has a single responsibility
2. **Error Handling**: Always provide graceful fallbacks
3. **Logging**: Use descriptive print statements or logging
4. **Type Hints**: Add type hints for function parameters and returns
5. **Documentation**: Update docstrings when changing behavior

---

**Last Updated**: November 2025
