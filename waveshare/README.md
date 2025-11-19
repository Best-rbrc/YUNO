# WaveShare RGB Matrix Display System

Comprehensive display system for WaveShare RGB P3 Matrix Panel 64x64 HUB75 connected to Raspberry Pi 5. Features interactive quiz mode with OpenAI integration, MQTT joystick controls, text-to-speech narration, pixel art rendering, and multi-threaded slideshow management.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Modules](#core-modules)
4. [Technologies](#technologies)
5. [Hardware Requirements](#hardware-requirements)
6. [Installation](#installation)
7. [Configuration](#configuration)
8. [Usage](#usage)
9. [Features](#features)
10. [File Structure](#file-structure)

---

## Overview

The WaveShare display system transforms the Yuno face recognition project into an interactive RGB LED matrix experience. It fetches recognized persons from Supabase, generates 64x64 pixel art portraits, and displays them in a continuous slideshow with optional quiz mode for interactive learning.

**Key Capabilities:**
- **Pixel Art Rendering**: Converts photos to 64x64 LED-optimized pixel art with contrast enhancement
- **Interactive Quiz Mode**: OpenAI-powered questions with TTS narration and MQTT joystick controls
- **Real-time Data Sync**: Fetches person data from Supabase database with photo caching
- **Multi-threaded Architecture**: Separate threads for display rendering, MQTT listener, and quiz management
- **Background Music**: Playlist support with crossfade transitions
- **Landing Screen**: Animated welcome screen with brand identity

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    main_app.py (Main App)                   │
├─────────────────────────────────────────────────────────────┤
│  • RGB Matrix Control (PioMatter driver)                    │
│  • MQTT Listener Thread (Joystick input)                    │
│  • Quiz Queue Thread (OpenAI + TTS)                         │
│  • Background Music Thread (Playlist mgmt)                  │
│  • Slideshow State Machine (Landing/Quiz/Display)           │
└────────┬────────────────────────────────────┬───────────────┘
         │                                    │
    ┌────▼────────┐                    ┌─────▼──────────┐
    │ DataLoader  │                    │ PixelArtGen    │
    │             │                    │                │
    │ • Supabase  │                    │ • PIL Resize   │
    │   fetch     │                    │ • Contrast++   │
    │ • Photo     │                    │ • Color        │
    │   download  │                    │   quantize     │
    │ • Caching   │                    │ • NumPy array  │
    └─────────────┘                    └────────────────┘
         │                                    │
         │            ┌──────────────┐        │
         └────────────►  Supabase    ◄────────┘
                      │              │
                      │ • Persons DB │
                      │ • Photo URLs │
                      │ • Context    │
                      └──────────────┘

External Integrations:
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ MQTT Broker  │     │ OpenAI API   │     │ pyttsx3 TTS  │
│ (Joystick)   │     │ (Quiz Gen)   │     │ (Narration)  │
└──────────────┘     └──────────────┘     └──────────────┘
```

### Threading Model

- **Main Thread**: Runs display loop (landing screen → slideshow → quiz mode)
- **MQTT Thread**: Listens for joystick commands (UP/DOWN/LEFT/RIGHT), updates state
- **Quiz Thread**: Pre-generates quiz questions in background for seamless transitions
- **Music Thread**: Manages background music playback with fade transitions

### State Machine

```
┌──────────────┐
│   LANDING    │ (5 seconds)
│   SCREEN     │
└──────┬───────┘
       │
       ▼
┌──────────────┐     Quiz Mode?
│  SLIDESHOW   │────────────┐
│  (Persons)   │            │
└──────┬───────┘            │
       │                    ▼
       │             ┌──────────────┐
       │             │  QUIZ MODE   │
       │             │  (Questions) │
       │             └──────┬───────┘
       │                    │
       └────────────────────┘
```

---

## Core Modules

### `main_app.py`

The primary application orchestrating the entire display system.

**Classes:**
- `YunoDisplayApp`: Main application class managing all subsystems

**Key Methods:**
- `init_hardware()`: Initializes RGB matrix display (64x64, PioMatter driver)
- `init_mqtt()`: Sets up MQTT client for joystick communication (broker: localhost:1883)
- `on_message()`: MQTT callback handler for joystick events (UP/DOWN/LEFT/RIGHT)
- `render_landing_frame()`: Draws animated landing screen with YUNO branding
- `render_person_on_matrix()`: Displays person pixel art with name text overlay
- `speak_context()`: TTS narration of person context using OpenAI or pyttsx3
- `generate_quiz_for_person()`: OpenAI GPT-4o-mini question generation
- `present_quiz_question()`: Renders quiz question with answer options on LED matrix
- `init_quiz_queue()`: Background thread for pre-generating quiz questions
- `play_background_music()`: Playlist manager with crossfade and volume control
- `run()`: Main application loop with state management

**Configuration Constants:**
- `MATRIX_WIDTH = 64`, `MATRIX_HEIGHT = 64`
- `BRIGHTNESS = 50` (0-100 scale)
- `DISPLAY_DURATION = 5` (seconds per person)
- `LANDING_DURATION = 5` (seconds on startup)
- `QUIZ_DISPLAY_DURATION = 15` (seconds per question)
- `MQTT_TOPIC = "waveshare/commands"` (joystick input topic)

**Threading:**
- MQTT listener runs in daemon thread
- Quiz queue runs in daemon thread with queue size 3
- Background music runs in daemon thread

### `data_loader.py`

Handles Supabase integration for fetching person data and downloading photos.

**Classes:**
- `DataLoader`: Supabase client wrapper for person data management

**Key Methods:**
- `is_connected()`: Verifies Supabase connection status
- `fetch_all_persons()`: Retrieves all persons from `persons` table
- `download_photo(photo_url, person_id)`: Downloads photo from Supabase storage
- `load_persons_with_photos()`: Fetches persons and downloads photos with caching
- `clear_cache()`: Clears local photo cache directory

**Caching Strategy:**
- Photos cached in `waveshare/cache/photos/` as `person_{id}.jpg`
- Cache persists across runs for performance
- Downloads only if photo not already cached
- Uses Supabase Storage API with signed URLs

**Dependencies:**
- `src.supabase_handler.SupabaseHandler` for database access
- Requires `SUPABASE_URL` and `SUPABASE_KEY` in environment

### `pixel_art_generator.py`

Converts photos to 64x64 pixel art optimized for RGB LED matrix display.

**Classes:**
- `PixelArtGenerator`: Image processing pipeline for LED matrix

**Key Methods:**
- `load_image(image_path)`: Loads image and converts to RGB
- `resize_with_preserve_aspect()`: Letterboxing resize (no cropping)
- `enhance_contrast(factor=1.8)`: Boosts contrast for LED visibility
- `reduce_colors(palette_size=64)`: Quantizes colors for pixel art effect
- `generate_pixel_art(image_path)`: Full pipeline returning NumPy array
- `pixel_art_to_matrix_format()`: Clips values to 0-255 uint8 range

**Image Processing Pipeline:**
1. Load image → Convert to RGB
2. Resize to 64x64 with letterboxing (preserve aspect ratio, black borders)
3. Enhance contrast by 1.8x for LED brightness
4. Reduce to 64 colors using quantization
5. Return as NumPy array (64, 64, 3) with RGB values 0-255

**Technology:**
- **PIL (Pillow)**: Image loading, resizing with LANCZOS resampling
- **NumPy**: Array manipulation for matrix display
- **Quantization**: Reduces color palette for retro pixel art aesthetic

---

## Technologies

### Hardware Integration
- **adafruit_blinka_raspberry_pi5_piomatter**: RGB LED matrix driver for Raspberry Pi 5
  - Used for direct control of WaveShare P3 HUB75 panel
  - Handles PWM signal generation for LED brightness
  - Supports 64x64 resolution at 50% brightness

### Communication Protocols
- **paho-mqtt**: MQTT client library for IoT device communication
  - Broker: localhost:1883 (Mosquitto)
  - Topic: `waveshare/commands` (joystick input)
  - Commands: `UP`, `DOWN`, `LEFT`, `RIGHT` (quiz navigation)
  - QoS: 0 (fire-and-forget)

### Audio Systems
- **pyttsx3**: Offline text-to-speech engine
  - Fallback TTS when OpenAI unavailable
  - Voice: default system voice (macOS Samantha, Linux espeak)
  - Rate: 175 words per minute
  - Volume: 0.9 (90%)

- **pygame.mixer**: Audio playback for background music
  - Supports .wav files in `sounds/` directory
  - Crossfade transitions between tracks
  - Volume control (default 0.3 for background music)

- **OpenAI TTS-1**: Cloud-based high-quality speech synthesis
  - Voice: `nova` (clear, professional female voice)
  - Speed: 1.0 (normal rate)
  - Format: MP3 via tempfile, converted to WAV for pygame

### AI Integration
- **OpenAI GPT-4o-mini**: Quiz question generation
  - Model: `gpt-4o-mini` (fast, cost-effective)
  - Temperature: 0.7 (balanced creativity)
  - Max tokens: 150 per question
  - Prompt: Generates 4 multiple-choice options from person context

### Image Processing
- **PIL (Pillow)**: Image manipulation library
  - LANCZOS resampling for high-quality downscaling
  - ImageEnhance.Contrast for LED optimization
  - Image.quantize() for color reduction
  - ImageDraw for text rendering on matrix

- **NumPy**: Numerical computing for pixel arrays
  - RGB array manipulation (64, 64, 3)
  - Value clipping (0-255 range)
  - Type casting (uint8 for matrix driver)

### Database
- **Supabase**: PostgreSQL database + cloud storage
  - Table: `persons` (id, name, gender, context, photo_url, created_at)
  - Storage: `person-photos` bucket for profile pictures
  - API: REST API with signed URLs for photo downloads
  - Uses `src.supabase_handler.SupabaseHandler` wrapper

### Development Tools
- **dotenv**: Environment variable management
  - Loads `.env` from `config/` directory
  - Required vars: `SUPABASE_URL`, `SUPABASE_KEY`, `OPENAI_API_KEY`
- **threading**: Multi-threaded architecture for concurrent operations
- **pathlib**: Modern file path handling (cross-platform)
- **subprocess**: Shell command execution for audio conversion

---

## Hardware Requirements

### Required Components
1. **Raspberry Pi 5** (4GB+ RAM recommended)
   - Runs PioMatter RGB matrix driver
   - Handles MQTT, OpenAI API calls, audio playback
   - Requires 5V/6A power supply

2. **WaveShare RGB P3 Matrix Panel 64x64**
   - 64x64 pixel resolution (4096 total pixels)
   - HUB75 interface (16-pin ribbon cable)
   - 3mm pitch (P3) for indoor visibility
   - Dimensions: 192mm x 192mm
   - Power: 5V DC, ~4A at full brightness

3. **Power Supply**
   - 5V/6A minimum for Pi + LED matrix
   - Barrel jack connector for matrix panel
   - USB-C PD for Raspberry Pi 5

4. **MQTT Joystick Controller** (Optional, for quiz mode)
   - Arduino with joystick module
   - Publishes UP/DOWN/LEFT/RIGHT to `waveshare/commands`
   - See `Arduino/Commands_Senden_UP_RIGHT_LEFT_DOWN/` for firmware

### Wiring Diagram (Active3 Pinout)
```
HUB75 Pin → Signal → GPIO Pin (Raspberry Pi 5)
──────────────────────────────────────────────────
Pin 1/2   → R1     → GPIO 11 (Pin 23) - brown
Pin 3/4   → G1     → GPIO 27 (Pin 13) - red
Pin 5/6   → B1     → GPIO 7  (Pin 26) - orange
Pin 7/8   → 1/s    → GPIO 4  (Pin 7)  - yellow2
Pin 9/10  → R2     → GPIO 8  (Pin 24) - green
Pin 11/12 → G2     → GPIO 9  (Pin 21) - blue
Pin 13/14 → B2     → GPIO 10 (Pin 19) - purple
Pin 15/16 → A      → GPIO 22 (Pin 15) - white
Pin 17/18 → B      → GPIO 23 (Pin 16) - black
Pin 19/20 → C      → GPIO 24 (Pin 18) - brown2
Pin 21/22 → D      → GPIO 25 (Pin 22) - red2
Pin 23/24 → E      → GPIO 15 (Pin 10) - gray
Pin 25/26 → CLK    → GPIO 17 (Pin 11) - orange2
Pin 27/28 → LAT/STP → GPIO 4 (Pin 7)  - yellow2
Pin 29/30 → OE     → GPIO 18 (Pin 12) - green2
Pin 31/32 → GND    → GND     (Pin 25) - blue2

Note: Active3 uses PioMatter library with automatic pin mapping.
Pins 1, 3, 5, 7... are signal pins
Pins 2, 4, 6, 8... are GND pins
```

### Optional Components
- **HDMI Monitor**: For debugging (SSH recommended for headless)
- **Speakers**: For TTS narration and background music
- **USB Keyboard**: For manual controls if MQTT unavailable

---

## Installation

### Prerequisites
- Python 3.11+ recommended
- Raspberry Pi OS (Bookworm 64-bit)
- Internet connection for Supabase and OpenAI

### System Dependencies (Raspberry Pi)
```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Python dependencies
sudo apt-get install -y python3-pip python3-venv python3-pil python3-numpy

# Install audio libraries
sudo apt-get install -y libportaudio2 espeak

# Install MQTT broker (optional, for local testing)
sudo apt-get install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

### Python Environment Setup
```bash
# Navigate to project root
cd /path/to/HandsOnHCI

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Raspberry Pi Specific
```bash
# Install PioMatter RGB matrix driver
pip install adafruit-blinka-raspberry-pi5-piomatter

# Configure permissions for GPIO access
sudo usermod -aG gpio $USER
sudo reboot
```

---

## Configuration

### Environment Variables
Create or edit `config/.env` in project root:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-public-key

# OpenAI Configuration (optional, for quiz mode)
OPENAI_API_KEY=sk-proj-your-api-key-here

# MQTT Configuration (optional, defaults shown)
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_TOPIC=waveshare/commands
```

### Application Settings
Edit constants in `main_app.py`:

```python
# Display Settings
MATRIX_WIDTH = 64
MATRIX_HEIGHT = 64
BRIGHTNESS = 50  # 0-100, default 50 for indoor use
DISPLAY_DURATION = 5  # Seconds per person in slideshow
LANDING_DURATION = 5  # Seconds on landing screen

# Quiz Settings
QUIZ_MODE_ENABLED = True  # Set False to disable quiz
QUIZ_DISPLAY_DURATION = 15  # Seconds per quiz question
QUIZ_FREQUENCY = 5  # Show quiz every N persons

# Audio Settings
BACKGROUND_MUSIC_ENABLED = True
MUSIC_VOLUME = 0.3  # 0.0 to 1.0
TTS_VOLUME = 0.9  # 0.0 to 1.0

# MQTT Settings
MQTT_TOPIC = "waveshare/commands"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
```

### Background Music
Place `.wav` files in `waveshare/sounds/` directory:
```
waveshare/sounds/
├── Espresso.wav
├── Fortnite Festival.wav
├── Fortnite OG.wav
├── Juno.wav
└── Subway.wav
```

Files play in alphabetical order with crossfade transitions.

---

## Usage

### Basic Usage
```bash
# Activate virtual environment
source venv/bin/activate

# Run the application (on Raspberry Pi)
cd waveshare
python main_app.py
```

### Command-Line Options
Currently, `main_app.py` does not support CLI arguments. To modify behavior:
1. Edit configuration constants in `main_app.py`
2. Toggle features via environment variables
3. Use keyboard interrupt (Ctrl+C) to exit gracefully

### Operation Modes

#### 1. Normal Mode (Default)
- Shows landing screen for 5 seconds
- Displays slideshow of all persons with pixel art
- Narrates context via TTS for each person
- Shows quiz questions every 5 persons (if enabled)
- Background music plays continuously

#### 2. Quiz Mode
- Activated automatically during slideshow
- Displays multiple-choice question about person
- MQTT joystick controls:
  - **UP**: Select option A
  - **RIGHT**: Select option B
  - **DOWN**: Select option C
  - **LEFT**: Select option D
- TTS narrates question and correct answer
- Returns to slideshow after 15 seconds

#### 3. Test Mode (Manual Testing)
```bash
# Test data loader independently
cd waveshare
python data_loader.py

# Test pixel art generator with sample image
python pixel_art_generator.py /path/to/image.jpg
```

### MQTT Joystick Control

Publish commands to MQTT broker:
```bash
# Using mosquitto_pub (command line)
mosquitto_pub -h localhost -t waveshare/commands -m "UP"
mosquitto_pub -h localhost -t waveshare/commands -m "RIGHT"

# Using Arduino joystick (see Arduino/ folder)
# Upload Commands_Senden_UP_RIGHT_LEFT_DOWN.ino to Arduino
# Connects to WiFi and publishes joystick movements
```

### Graceful Shutdown
- Press **Ctrl+C** to stop the application
- Signal handler ensures clean shutdown:
  - Stops MQTT listener thread
  - Stops quiz queue thread
  - Stops background music thread
  - Clears LED matrix display

---

## Features

### 1. Dynamic Person Slideshow
- Fetches all recognized persons from Supabase database
- Downloads and caches profile photos locally
- Converts photos to 64x64 pixel art with contrast enhancement
- Displays person name as text overlay on LED matrix
- Cycles through all persons with configurable duration

### 2. Interactive Quiz Mode
- Generates multiple-choice questions using OpenAI GPT-4o-mini
- Based on person's context field from database
- 4 answer options (one correct, three plausible distractors)
- MQTT joystick navigation (UP/RIGHT/DOWN/LEFT)
- TTS narration of question and answer feedback
- Background thread pre-generates questions for smooth transitions

### 3. Text-to-Speech Narration
- **Primary**: OpenAI TTS-1 with `nova` voice (cloud-based)
- **Fallback**: pyttsx3 offline TTS (when OpenAI unavailable)
- Narrates person context during slideshow
- Reads quiz questions and answers aloud
- Adjustable speech rate and volume

### 4. Background Music System
- Plays `.wav` files from `sounds/` directory in alphabetical order
- Crossfade transitions between tracks (1-second fade)
- Volume control separate from TTS (default 30%)
- Loops through playlist continuously
- Runs in daemon thread for non-blocking playback

### 5. Landing Screen Animation
- Displays "YUNO" branding on startup
- Animated gradient background with sine wave pattern
- Custom font rendering with PIL ImageDraw
- Shows for 5 seconds before entering slideshow

### 6. Multi-threaded Architecture
- **Main thread**: Display loop (rendering frames at ~30 FPS)
- **MQTT thread**: Listens for joystick commands (non-blocking)
- **Quiz thread**: Pre-generates questions in background (queue size 3)
- **Music thread**: Manages audio playback with fade control
- Thread-safe state management with locks

### 7. Photo Caching System
- Downloads photos from Supabase Storage only once
- Caches in `waveshare/cache/photos/` directory
- Keyed by person ID: `person_{id}.jpg`
- Reduces bandwidth and speeds up slideshow
- Persistent across application restarts

### 8. Error Handling & Resilience
- Graceful degradation when OpenAI unavailable (uses pyttsx3)
- Skips persons without photos (no blank displays)
- MQTT connection retry logic with timeout
- Signal handlers for clean Ctrl+C shutdown
- Exception logging for debugging

---

## File Structure

```
waveshare/
├── main_app.py              # Main application (700+ lines)
├── data_loader.py           # Supabase data fetching & photo download
├── pixel_art_generator.py   # Image → 64x64 pixel art conversion
├── README.md                # This documentation
├── __init__.py              # Python package marker
├── cache/                   # Photo cache directory
│   └── photos/              # Cached person photos (person_{id}.jpg)
├── sounds/                  # Background music playlist
│   ├── Espresso.wav
│   ├── Fortnite Festival.wav
│   ├── Fortnite OG.wav
│   ├── Juno.wav
│   └── Subway.wav
└── simulation_output/       # Test output for debugging (unused in production)
```

### Removed Files (No Longer Used)
The following files were removed during cleanup as they are not imported by `main_app.py`:
- `config.py` - Configuration superseded by inline constants
- `joystick_listener.py` - MQTT handling moved to main_app.py
- `landing_screen.py` - Landing screen rendering inline in main_app.py
- `mqtt_client.py` - MQTT client implemented directly in main_app.py
- `quiz_mode.py` - Quiz logic integrated into main_app.py
- `slideshow.py` - Slideshow logic implemented in main_app.py
- `test_pi_*.py` - Test files no longer needed
- `aduino/` - Typo folder (Arduino firmware in root `Arduino/` instead)

---

## Related Documentation

- **Root README**: Overall project setup, Supabase configuration, environment variables
- **src/README.md**: Backend modules (face recognition, identity matching, OpenAI API)
- **frontend/README.md**: Web dashboard for person management
- **Arduino/**: Joystick firmware for MQTT control

---

## Notes

- **Raspberry Pi 5 Required**: PioMatter driver only supports Pi 5 (not compatible with Pi 4)
- **Supabase Connection**: Application will skip persons without Supabase access
- **OpenAI Optional**: Quiz mode works with pyttsx3 fallback if OpenAI key missing
- **Performance**: Rendering 64x64 pixels at 50% brightness runs smoothly at ~30 FPS
- **Power Consumption**: LED matrix at 50% brightness draws ~2A, plan power supply accordingly
