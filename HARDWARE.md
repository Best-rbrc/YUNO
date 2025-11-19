# Hardware Setup Guide - Yuno Project

Comprehensive hardware requirements and setup instructions for the complete Yuno smart person recognition system.

---

##  Table of Contents

1. [System Overview](#system-overview)
2. [Hardware Components](#hardware-components)
3. [Raspberry Pi 1: Yuno Glasses Prototype](#raspberry-pi-1-yuno-glasses-prototype)
4. [Raspberry Pi 2: WaveShare Display Station](#raspberry-pi-2-waveshare-display-station)
5. [Arduino LCD Controller](#arduino-lcd-controller)
6. [Development System](#development-system)
7. [Network Architecture](#network-architecture)
8. [MQTT Broker Setup](#mqtt-broker-setup)
9. [Complete Wiring Guide](#complete-wiring-guide)
10. [Power Requirements](#power-requirements)
11. [Assembly Instructions](#assembly-instructions)

---

##  System Overview

The Yuno project consists of **two independent Raspberry Pi systems** that communicate via Supabase as the single source of truth:

1. **Raspberry Pi 1 (Yuno Glasses Prototype)**: Standalone wearable system with camera, microphone, Bluetooth speaker, and physical buttons for face recognition
2. **Raspberry Pi 2 (WaveShare Display)**: 64x64 RGB LED matrix display showing person slideshow and quiz mode
3. **Arduino with LCD & Joystick**: Controls the WaveShare display via MQTT (communicates only with Pi 2)
4. **Mac/PC (Development Only)**: Used for development, testing, and web frontend

**Communication Architecture:**
```
                        ┌─────────────────────┐
                        │     Supabase        │
                        │  (Single Source of  │
                        │      Truth)         │
                        │                     │
                        │  • Persons DB       │
                        │  • Photo Storage    │
                        │  • Audio Storage    │
                        └──────────┬──────────┘
                                   │
                    WiFi/Internet  │
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
           ▼                       ▼                       ▼
┌──────────────────────┐  ┌───────────────────┐  ┌──────────────────┐
│  Raspberry Pi 1      │  │  Raspberry Pi 2   │  │  Mac/PC          │
│  (Yuno Glasses)      │  │  (Display Station)│  │  (Development)   │
├──────────────────────┤  ├───────────────────┤  ├──────────────────┤
│  • Camera            │  │  • WaveShare RGB  │  │  • Face recog    │
│  • Microphone        │  │    64x64 Matrix   │  │    testing       │
│  • Bluetooth Speaker │  │  • MQTT Broker    │  │  • Frontend dev  │
│  • Normal Button     │  │  • Quiz mode      │  │  • DB management │
│  • Heartbeat Button  │  │  • TTS output     │  │                  │
│  • Face recognition  │  │  • Pixel art      │  └──────────────────┘
│  • Supabase sync     │  │  • Supabase sync  │
└──────────────────────┘  └─────────┬─────────┘
                                    │
     No direct communication    MQTT Broker
     between the two Pis         (Port 1883)
                                    │
                           ┌────────▼─────────┐
                           │  Arduino UNO R4  │
                           │  + LCD Display   │
                           │  + Joystick      │
                           │                  │
                           │  • Quiz control  │
                           │  • Person info   │
                           └──────────────────┘
```

**Key Principles:**
- **Supabase = Single Source of Truth**: Both Raspberry Pis sync data independently to/from Supabase
- **No Pi-to-Pi Communication**: The two Raspberry Pis operate independently and do not communicate directly
- **MQTT Only for Pi 2 ↔ Arduino**: Only the WaveShare display Pi communicates with Arduino via MQTT
- **Standalone Operation**: Each Pi can function without the other or the development Mac

---

## Hardware Components

### 1. Raspberry Pi 1: Yuno Glasses Prototype (Standalone Wearable)
**Purpose**: Portable face recognition system with audio interaction

**Required:**
- **Raspberry Pi 5** (4GB or 8GB RAM)
- **Camera Module**: Raspberry Pi Camera Module 3 or USB webcam
- **Microphone**: USB microphone or Raspberry Pi Audio HAT
- **Bluetooth Speaker**: Portable speaker for TTS audio output
- **Physical Buttons**:
  - Normal Button: GPIO pin for standard operation (identify mode)
  - Heartbeat Button: GPIO pin for enrollment mode
- **microSD Card**: 32GB+ (Class 10 or UHS-I)
- **Power Supply**: 5V/3A USB-C PD (portable power bank for mobile use)
- **Battery Pack** (optional): 20,000mAh USB-C power bank for portable operation

**Recommended:**
- Active cooling fan for continuous operation
- 3D-printed housing for wearable form factor
- Velcro straps or headband mount

### 2. Raspberry Pi 2: WaveShare Display Station
**Purpose**: Stationary display showing person slideshow with interactive quiz mode

**Required:**
- **Raspberry Pi 5** (4GB or 8GB RAM)
- **WaveShare RGB P3 Matrix Panel 64x64**
  - Model: 64x64 pixels, HUB75 interface
  - Pitch: 3mm (P3) for indoor visibility
  - Dimensions: 192mm x 192mm
  - Power: 5V DC, ~4A at full brightness
- **microSD Card**: 32GB+ (Class 10 or UHS-I)
- **Power Supply**: 5V/6A (27W) USB-C PD for Pi + Matrix
- **GPIO Ribbon Cable**: For HUB75 connection
- **Speakers** (optional): For TTS audio output

**Recommended:**
- Active cooling fan or heatsink for Raspberry Pi 5
- HDMI monitor for initial setup
- USB keyboard and mouse for configuration

### 3. Arduino LCD Controller (for WaveShare Display)
**Purpose**: Physical controller for WaveShare display quiz mode and person info display

**Required:**
- **Arduino UNO R4 WiFi** (with WiFiNINA support)
- **16x2 LCD Display** with I2C or parallel interface
- **Analog Joystick Module** (2-axis + button)
  - VCC: 5V
  - GND: Ground
  - VRx: X-axis analog output → A1
  - VRy: Y-axis analog output → A0
  - SW: Button digital output → Pin 7
- **Jumper Wires**: Male-to-male and male-to-female
- **Breadboard** (optional): For prototyping
- **USB Cable**: Type-B (for Arduino programming/power)

**LCD Wiring (Parallel Interface):**
- RS → Pin 12
- EN → Pin 11
- D4 → Pin 5
- D5 → Pin 4
- D6 → Pin 3
- D7 → Pin 2
- VSS → GND
- VDD → 5V
- V0 → 10kΩ potentiometer (contrast adjustment)

**Note**: Arduino only communicates with Raspberry Pi 2 (WaveShare display) via MQTT, not with Raspberry Pi 1 (Yuno Glasses).

### 4. Development System (Mac/PC)
**Purpose**: Development, testing, and web frontend access

- **Laptop or Desktop** (Mac/Windows/Linux)
- **Webcam** (optional): For testing face recognition locally
- **Minimum Specs**: 8GB RAM, Python 3.11+, 5GB free storage
- **Network**: WiFi or Ethernet connection
- **Development Tools**: Git, Python IDE (VS Code recommended), Arduino IDE

**Note**: The Mac/PC is NOT required for production operation. Both Raspberry Pis operate independently.

### 5. Network Equipment
- **WiFi Router**: 2.4GHz network (for Arduino compatibility)
- **Internet Connection**: Required for Supabase sync on both Raspberry Pis
- **Ethernet Cables** (optional): For stable Raspberry Pi connections

---

## Raspberry Pi 1: Yuno Glasses Prototype

### Hardware Assembly
1. **Install microSD Card**:
   - Flash Raspberry Pi OS Lite (64-bit, Bookworm) using Raspberry Pi Imager
   - Enable SSH in imager settings for headless setup
   - Configure WiFi credentials in imager

2. **Connect Camera**:
   - **Option A** (Raspberry Pi Camera Module): Insert ribbon cable into CSI port
   - **Option B** (USB Webcam): Plug into USB 3.0 port

3. **Connect Microphone**:
   - USB microphone: Plug into USB port
   - Test with `arecord -l` to verify detection

4. **Connect Bluetooth Speaker**:
   - Pair via `bluetoothctl`:
     ```bash
     bluetoothctl
     power on
     agent on
     default-agent
     scan on
     # Wait for speaker MAC address to appear
     pair XX:XX:XX:XX:XX:XX
     trust XX:XX:XX:XX:XX:XX
     connect XX:XX:XX:XX:XX:XX
     ```

5. **Connect Physical Buttons**:
   - **Normal Button**: Connect to GPIO 17 (Pin 11) and GND
   - **Heartbeat Button**: Connect to GPIO 27 (Pin 13) and GND
   - Use pull-up resistors (10kΩ) or enable internal pull-up in code

6. **Power Supply**:
   - For testing: 5V/3A USB-C PD adapter
   - For portable use: 20,000mAh USB-C power bank

### Software Installation (Raspberry Pi 1)
```bash
# 1. Update system
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install Python dependencies
sudo apt-get install -y python3-pip python3-venv python3-opencv

# 3. Install audio libraries
sudo apt-get install -y libasound2-dev portaudio19-dev libportaudio2 \
                        libportaudiocpp0 ffmpeg libav-tools pulseaudio \
                        bluez pulseaudio-module-bluetooth

# 4. Install camera libraries
sudo apt-get install -y python3-picamera2  # For Pi Camera Module
# OR for USB webcam, no additional install needed

# 5. Enable camera interface
sudo raspi-config
# Interface Options → Camera → Enable

# 6. Clone project and install Python packages
cd ~
git clone https://github.com/Best-rbrc/HandsOnHCI.git
cd HandsOnHCI
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 7. Configure GPIO for buttons
sudo apt-get install -y python3-rpi.gpio
```

### Configuration (Raspberry Pi 1)
Create `config/.env`:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-public-key
OPENAI_API_KEY=sk-proj-your-api-key-here

# Button GPIO pins
NORMAL_BUTTON_PIN=17
HEARTBEAT_BUTTON_PIN=27

# Audio output device (Bluetooth speaker)
AUDIO_OUTPUT_DEVICE=bluealsa
```

### Button Operation
- **Normal Button (GPIO 17)**: Press to start identify mode (recognize faces)
- **Heartbeat Button (GPIO 27)**: Press to start enrollment mode (add new person)

### Running Yuno Glasses
```bash
# Start button listener mode
cd ~/HandsOnHCI
source venv/bin/activate
python main.py button

# The system will:
# 1. Wait for button press
# 2. Capture photo on button press
# 3. Recognize face or enroll new person
# 4. Speak result via Bluetooth speaker
# 5. Sync to Supabase
# 6. Return to waiting state
```

---

## Raspberry Pi 2: WaveShare Display Station

### Hardware Assembly
1. **Install microSD Card**:
   - Flash Raspberry Pi OS (64-bit, Bookworm recommended) using Raspberry Pi Imager
   - Enable SSH in imager settings for headless setup

2. **Connect WaveShare RGB Matrix**:
   - Use GPIO header pins (see [Complete Wiring Guide](#complete-wiring-guide))
   - Connect HUB75 16-pin ribbon cable to matrix input
   - Connect 5V power to matrix barrel jack (separate from Pi power)

3. **Power Supply**:
   - Use 5V/6A power supply with USB-C PD for Raspberry Pi
   - LED matrix uses separate 5V/4A power (shared ground with Pi)

### Software Installation (Raspberry Pi 2)
```bash
# 1. Update system
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install Python dependencies
sudo apt-get install -y python3-pip python3-venv python3-pil python3-numpy

# 3. Install audio libraries (for TTS)
sudo apt-get install -y libportaudio2 espeak

# 4. Install MQTT broker (Mosquitto)
sudo apt-get install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# 5. Configure Mosquitto to listen on network
sudo nano /etc/mosquitto/mosquitto.conf
# Add these lines:
listener 1883
allow_anonymous true

# Restart Mosquitto
sudo systemctl restart mosquitto

# 6. Clone project and install Python packages
cd ~
git clone https://github.com/Best-rbrc/HandsOnHCI.git
cd HandsOnHCI
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 7. Install PioMatter RGB matrix driver
pip install adafruit-blinka-raspberry-pi5-piomatter

# 8. Configure GPIO permissions
sudo usermod -aG gpio $USER
sudo reboot
```

### Configuration
Create `config/.env`:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-public-key
OPENAI_API_KEY=sk-proj-your-api-key-here
```

### Network Setup
```bash
# Find Raspberry Pi IP address
hostname -I

# Test MQTT broker
mosquitto_sub -h localhost -t test
# In another terminal:
mosquitto_pub -h localhost -t test -m "Hello"
```

---

## Arduino LCD Controller

### Hardware Assembly
1. **Connect LCD Display** (parallel interface):
   - RS → Arduino Pin 12
   - EN → Arduino Pin 11
   - D4-D7 → Pins 5, 4, 3, 2
   - VSS → GND, VDD → 5V
   - V0 → Center pin of 10kΩ potentiometer (contrast)
   - A (backlight +) → 5V via 220Ω resistor
   - K (backlight -) → GND

2. **Connect Joystick Module**:
   - VCC → 5V
   - GND → GND
   - VRx → A1 (X-axis)
   - VRy → A0 (Y-axis)
   - SW → Pin 7 (button)

### Software Installation
1. **Install Arduino IDE**:
   - Download from [arduino.cc](https://www.arduino.cc/en/software)
   - Install **WiFiNINA** library (Tools → Manage Libraries)
   - Install **PubSubClient** library (for MQTT)
   - Install **LiquidCrystal** library (built-in)

2. **Upload Firmware**:
   ```bash
   # Open Arduino IDE
   # File → Open → Arduino/Commands_Senden_UP_RIGHT_LEFT_DOWN.ino
   # Select Board: Arduino UNO R4 WiFi
   # Select Port: (your Arduino COM port)
   # Click Upload
   ```

3. **Configure WiFi & MQTT**:
   Edit in `.ino` file:
   ```cpp
   const char* WIFI_SSID     = "YourWiFiName";
   const char* WIFI_PASSWORD = "YourWiFiPassword";
   const char* MQTT_HOST     = "192.168.1.XXX";  // Raspberry Pi 2 IP (WaveShare display)
   const uint16_t MQTT_PORT  = 1883;
   ```
   
   **Important**: Set MQTT_HOST to the IP address of **Raspberry Pi 2** (WaveShare display), NOT Raspberry Pi 1 (Yuno Glasses).

### Testing
```bash
# On Raspberry Pi 2 (WaveShare display), subscribe to Arduino topic:
mosquitto_sub -h localhost -t arduino/to/pi

# Move joystick on Arduino
# Should see: JOY:UP, JOY:DOWN, JOY:LEFT, JOY:RIGHT

# Publish command to Arduino:
mosquitto_pub -h localhost -t pi/to/arduino -m "NAME:John Doe"
mosquitto_pub -h localhost -t pi/to/arduino -m "DESC:Computer Science Student"
# LCD should display the text
```

---

## Development System (Mac/PC)

### Purpose
The Mac/PC is used **only for development and testing**. It is NOT required for production operation.

### Setup
1. **Clone Repository**:
   ```bash
   git clone https://github.com/Best-rbrc/HandsOnHCI.git
   cd HandsOnHCI
   ```

2. **Create Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # macOS/Linux
   # .\venv\Scripts\activate  # Windows
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment**:
   Create `config/.env`:
   ```bash
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-anon-public-key
   OPENAI_API_KEY=sk-proj-your-api-key-here
   ```

### Development Use Cases
- **Test Face Recognition**: `python main.py identify` (uses Mac webcam)
- **Enroll Test Persons**: `python main.py enroll`
- **Database Management**: `python main.py sync`
- **Frontend Development**: Open `frontend/index.html` in browser
- **Test Components**: Run scripts in `tests/` directory

### Web Frontend Access
```bash
# Open frontend in browser (file:// protocol)
open frontend/index.html  # macOS
start frontend/index.html  # Windows

# OR serve with Python HTTP server
cd frontend
python3 -m http.server 8000
# Open http://localhost:8000
```

---

## WaveShare RGB Matrix Wiring

### GPIO Wiring (Active3 Pinout)
Connect Raspberry Pi 5 GPIO to WaveShare HUB75 connector:

| HUB75 Pin | Signal  | Raspberry Pi GPIO | Physical Pin | Wire Color |
|-----------|---------|-------------------|--------------|------------|
| 1/2       | R1      | GPIO 11           | Pin 23       | Brown      |
| 3/4       | G1      | GPIO 27           | Pin 13       | Red        |
| 5/6       | B1      | GPIO 7            | Pin 26       | Orange     |
| 7/8       | 1/s     | GPIO 4            | Pin 7        | Yellow2    |
| 9/10      | R2      | GPIO 8            | Pin 24       | Green      |
| 11/12     | G2      | GPIO 9            | Pin 21       | Blue       |
| 13/14     | B2      | GPIO 10           | Pin 19       | Purple     |
| 15/16     | A       | GPIO 22           | Pin 15       | White      |
| 17/18     | B       | GPIO 23           | Pin 16       | Black      |
| 19/20     | C       | GPIO 24           | Pin 18       | Brown2     |
| 21/22     | D       | GPIO 25           | Pin 22       | Red2       |
| 23/24     | E       | GPIO 15           | Pin 10       | Gray       |
| 25/26     | CLK     | GPIO 17           | Pin 11       | Orange2    |
| 27/28     | LAT/STP | GPIO 4            | Pin 7        | Yellow2    |
| 29/30     | OE      | GPIO 18           | Pin 12       | Green2     |
| 31/32     | GND     | GND               | Pin 25       | Blue2      |

**Notes:**
- Odd-numbered HUB75 pins (1, 3, 5...) are signal pins
- Even-numbered HUB75 pins (2, 4, 6...) are ground pins
- Connect all grounds together (Pi GND + Matrix GND)
- PioMatter library handles pin mapping automatically

### Power Connection
- **LED Matrix**: 5V/4A via barrel jack connector (separate PSU)
- **Raspberry Pi**: 5V/3A via USB-C (can use same PSU with splitter if 6A+)
- **Ground**: Connect Pi GND to Matrix GND for common reference

### Testing WaveShare Display
```bash
# Run WaveShare display application on Raspberry Pi 2
cd ~/HandsOnHCI/waveshare
source ../venv/bin/activate
python main_app.py

# Should display:
# 1. Landing screen with "YUNO" branding (5 seconds)
# 2. Slideshow of all persons from Supabase database
# 3. Quiz questions with MQTT joystick control
```

---

## Network Architecture

### Network Topology
```
                    Internet (Supabase Cloud)
                            │
                            │ HTTPS (443)
                            │
                    ┌───────┴────────┐
                    │                │
                    ▼                ▼
         ┌──────────────────┐  ┌──────────────────┐
         │  Raspberry Pi 1  │  │  Raspberry Pi 2  │
         │  (Yuno Glasses)  │  │  (WaveShare)     │
         │  192.168.1.150   │  │  192.168.1.151   │
         │                  │  │                  │
         │  • Supabase sync │  │  • Supabase sync │
         │  • No MQTT       │  │  • MQTT Broker   │
         └──────────────────┘  └────────┬─────────┘
                                        │
              No communication      MQTT (1883)
              between the two Pis      │
                                       ▼
                              ┌──────────────────┐
                              │  Arduino UNO R4  │
                              │  192.168.1.200   │
                              │                  │
                              │  • MQTT Client   │
                              └──────────────────┘

         ┌──────────────────┐
         │  Mac/PC (Dev)    │  ← Development only
         │  192.168.1.100   │  ← Not required for
         │                  │     production
         │  • Testing       │
         │  • Frontend dev  │
         └──────────────────┘
```

### Communication Flows
1. **Raspberry Pi 1 ↔ Supabase**: WiFi/Internet → HTTPS (enrolls persons, syncs data)
2. **Raspberry Pi 2 ↔ Supabase**: WiFi/Internet → HTTPS (fetches persons for display)
3. **Raspberry Pi 2 ↔ Arduino**: Local Network → MQTT (quiz control, person info)
4. **Mac/PC ↔ Supabase**: Development/testing only (optional)

**Important**: The two Raspberry Pis **do not communicate directly**. They only sync via Supabase as the single source of truth.

### Port Configuration
- **MQTT Broker** (Raspberry Pi 2 only): Port 1883 (unencrypted, local network)
- **Supabase** (Both Raspberry Pis): HTTPS Port 443 (outbound to internet)
- **SSH** (Both Raspberry Pis): Port 22 (for remote access/debugging)
- **Web Frontend** (Mac/PC dev): Port 8000 (Python HTTP server, optional)

### Firewall Rules (Raspberry Pi 2 - WaveShare Display)
```bash
# Allow MQTT from local network (for Arduino)
sudo ufw allow from 192.168.1.0/24 to any port 1883

# Allow SSH
sudo ufw allow 22

# Allow outbound HTTPS for Supabase
sudo ufw allow out 443

# Enable firewall
sudo ufw enable
```

### Firewall Rules (Raspberry Pi 1 - Yuno Glasses)
```bash
# Allow SSH
sudo ufw allow 22

# Allow outbound HTTPS for Supabase
sudo ufw allow out 443

# Enable firewall
sudo ufw enable

# Note: No MQTT ports needed on Pi 1
```

---

## MQTT Broker Setup

### Installation (on Raspberry Pi 2 - WaveShare Display ONLY)

**Important**: MQTT broker is only installed on Raspberry Pi 2 (WaveShare display). Raspberry Pi 1 (Yuno Glasses) does NOT use MQTT.

```bash
# Install Mosquitto on Raspberry Pi 2
sudo apt-get install -y mosquitto mosquitto-clients

# Configure Mosquitto
sudo nano /etc/mosquitto/mosquitto.conf
```

Add configuration:
```conf
# Listen on all interfaces
listener 1883 0.0.0.0

# Allow anonymous connections (local network only)
allow_anonymous true

# Logging
log_dest file /var/log/mosquitto/mosquitto.log
log_type all

# Persistence
persistence true
persistence_location /var/lib/mosquitto/
```

Restart service:
```bash
sudo systemctl restart mosquitto
sudo systemctl enable mosquitto
```

### MQTT Topics
| Topic            | Publisher       | Subscriber             | Message Format      | Purpose                  |
|------------------|-----------------|------------------------|---------------------|--------------------------|
| `arduino/to/pi`  | Arduino         | Raspberry Pi 2 (WaveShare) | `JOY:UP/DOWN/...`   | Joystick commands        |
| `pi/to/arduino`  | Raspberry Pi 2  | Arduino                | `NAME:...`/`DESC:`  | Person info for LCD      |
| `waveshare/commands` | Arduino     | Raspberry Pi 2 (WaveShare) | `UP/DOWN/LEFT/...`  | Quiz navigation          |

**Note**: Raspberry Pi 1 (Yuno Glasses) does NOT publish or subscribe to any MQTT topics.

### Testing MQTT (on Raspberry Pi 2 only)
```bash
# Subscribe to all topics (debug)
mosquitto_sub -h localhost -t '#' -v

# Test Arduino → Pi 2
mosquitto_pub -h localhost -t arduino/to/pi -m "JOY:UP"

# Test Pi 2 → Arduino
mosquitto_pub -h localhost -t pi/to/arduino -m "NAME:Test User"
mosquitto_pub -h localhost -t pi/to/arduino -m "DESC:This is a test"
```

---

## Complete Wiring Guide

### Raspberry Pi 1 (Yuno Glasses) GPIO Connections
```
Camera Module:
  - Ribbon cable → CSI port (camera connector)
  OR USB webcam → USB 3.0 port

Microphone:
  - USB microphone → USB port

Bluetooth Speaker:
  - Paired via Bluetooth (no physical connection)

Normal Button:
  - One side → GPIO 17 (Pin 11)
  - Other side → GND (Pin 9)
  - Internal pull-up enabled in software

Heartbeat Button:
  - One side → GPIO 27 (Pin 13)
  - Other side → GND (Pin 14)
  - Internal pull-up enabled in software

Power:
  - USB-C → 5V/3A power adapter or power bank
```

### Raspberry Pi 2 (WaveShare Display) GPIO Pinout (40-pin Header)
```
        3V3  (1) (2)  5V
   GPIO2/SDA (3) (4)  5V
   GPIO3/SCL (5) (6)  GND
      GPIO4  (7) (8)  GPIO14/TXD
        GND  (9) (10) GPIO15/RXD
     GPIO17 (11) (12) GPIO18
     GPIO27 (13) (14) GND
     GPIO22 (15) (16) GPIO23
        3V3 (17) (18) GPIO24
     GPIO10 (19) (20) GND
      GPIO9 (21) (22) GPIO25
     GPIO11 (23) (24) GPIO8
        GND (25) (26) GPIO7
```

### Arduino UNO R4 WiFi Connections
```
Power:
  5V  → Joystick VCC, LCD VDD
  GND → Joystick GND, LCD VSS/K

Digital Pins:
  Pin 2  → LCD D7
  Pin 3  → LCD D6
  Pin 4  → LCD D5
  Pin 5  → LCD D4
  Pin 7  → Joystick SW (button)
  Pin 11 → LCD EN (enable)
  Pin 12 → LCD RS (register select)

Analog Pins:
  A0 → Joystick VRy (Y-axis)
  A1 → Joystick VRx (X-axis)
```

### Power Distribution

**Raspberry Pi 1 (Yuno Glasses):**
```
Power Bank or USB-C Adapter (5V/3A)
   │
   └─── USB-C → Raspberry Pi 1 (3A)
         │
         ├─── USB Microphone (powered by Pi)
         └─── USB Camera (if used, powered by Pi)

Bluetooth Speaker: Independent battery
```

**Raspberry Pi 2 (WaveShare Display):**
```
Main Power Supply (5V/6A)
   │
   ├─── USB-C → Raspberry Pi 2 (3A)
   │
   └─── Barrel Jack → WaveShare LED Matrix (4A)
         │
         └─── GND connected to Pi GND (common ground)
```

**Arduino:**
```
Separate:
   USB-B → Arduino UNO R4 (500mA from PC/USB adapter)
```

---

## Power Requirements

### Component Power Draw
| Component                    | Voltage | Current | Power  | Notes                          |
|------------------------------|---------|---------|--------|--------------------------------|
| Raspberry Pi 1 (Yuno Glasses)| 5V      | 3A      | 15W    | USB-C PD, portable             |
| Raspberry Pi 2 (WaveShare)   | 5V      | 3A      | 15W    | USB-C PD, stationary           |
| WaveShare LED Matrix         | 5V      | 4A      | 20W    | At full brightness (100%)      |
| WaveShare @ 50%              | 5V      | ~2A     | 10W    | Typical usage                  |
| Arduino UNO R4 WiFi          | 5V      | 500mA   | 2.5W   | Via USB or barrel jack         |
| USB Microphone               | 5V      | 100mA   | 0.5W   | Powered by Pi 1                |
| USB Webcam                   | 5V      | 500mA   | 2.5W   | Powered by Pi 1 (if used)      |
| Bluetooth Speaker            | 3.7V    | Varies  | N/A    | Independent battery            |

### Recommended Power Supplies

**Raspberry Pi 1 (Yuno Glasses) - Portable:**
- **Development/Testing**: Official 27W USB-C Power Supply
- **Portable Use**: 20,000mAh USB-C power bank (provides ~4 hours runtime)
- **Recommended**: Anker PowerCore 20100 or similar USB-C PD power bank

**Raspberry Pi 2 (WaveShare Display) - Stationary:**
- **Option 1** (Separate):
  - Raspberry Pi: Official 27W USB-C Power Supply
  - LED Matrix: 5V/5A switching power supply with barrel jack
  - Arduino: USB power from PC or 5V/1A wall adapter

- **Option 2** (Single PSU):
  - 5V/10A (50W) switching power supply
  - Split to USB-C for Pi (via PD trigger) and barrel jack for matrix
  - Arduino powered separately via USB

### Power Safety
- ⚠️ **Never connect 5V directly to GPIO pins** (use only for VCC pins)
- ✅ **Common ground required** between Pi and LED matrix
- ⚠️ **Avoid USB hub power** for Raspberry Pi (may be unstable)
- ✅ **Use ferrite cores** on power cables to reduce EMI

---

## Assembly Instructions

### Step 1: Raspberry Pi 1 (Yuno Glasses) Assembly
1. Flash Raspberry Pi OS Lite to microSD card
2. Insert microSD into Pi 1
3. Connect camera module or USB webcam
4. Connect USB microphone
5. Pair Bluetooth speaker via `bluetoothctl`
6. Connect Normal Button to GPIO 17 and GND
7. Connect Heartbeat Button to GPIO 27 and GND
8. Power on and complete OS setup
9. Enable SSH and configure WiFi
10. Update system: `sudo apt-get update && sudo apt-get upgrade`
11. Install software (see [Raspberry Pi 1 Setup](#raspberry-pi-1-yuno-glasses-prototype))
12. Configure `.env` with Supabase credentials
13. Test button functionality: `python main.py button`

### Step 2: Raspberry Pi 2 (WaveShare Display) Assembly
1. Flash Raspberry Pi OS to microSD card
2. Insert microSD into Pi 2
3. Connect HDMI monitor, keyboard, mouse (for initial setup)
4. Power on and complete OS setup
5. Enable SSH and configure WiFi
6. Update system: `sudo apt-get update && sudo apt-get upgrade`
7. Install MQTT Broker (see [MQTT Broker Setup](#mqtt-broker-setup))
8. Configure to listen on network (0.0.0.0:1883)
9. Note Raspberry Pi 2 IP address: `hostname -I`
10. Power off Pi 2
11. Connect WaveShare RGB Matrix (see wiring guide)
12. Power on and install software (see [Raspberry Pi 2 Setup](#raspberry-pi-2-waveshare-display-station))
13. Configure `.env` with Supabase credentials
14. Test display: `cd waveshare && python main_app.py`

### Step 3: Arduino Assembly
1. Connect LCD display to Arduino (pins 2-5, 11-12)
2. Connect joystick module (A0, A1, Pin 7)
3. Adjust LCD contrast with potentiometer
4. Upload firmware from `Arduino/Commands_Senden_UP_RIGHT_LEFT_DOWN/`
5. Configure WiFi SSID/password and MQTT broker IP (**Raspberry Pi 2 IP**)
6. Test: Joystick movements should send MQTT messages to Pi 2

### Step 4: System Integration Test
1. **Raspberry Pi 1 (Yuno Glasses)**:
   - Press Normal Button → should capture and identify face
   - Press Heartbeat Button → should start enrollment mode
   - Verify TTS output via Bluetooth speaker
   - Check Supabase for synced person data

2. **Raspberry Pi 2 (WaveShare Display)**:
   - Start MQTT broker: `sudo systemctl start mosquitto`
   - Run WaveShare app: `cd waveshare && python main_app.py`
   - Verify landing screen appears
   - Verify persons from Supabase appear in slideshow

3. **Arduino → Raspberry Pi 2 (MQTT)**:
   - Power on Arduino (should connect to WiFi and MQTT)
   - Move joystick → should see MQTT messages in Pi 2 terminal
   - Quiz mode should respond to joystick input
   - LCD should display person name/info

4. **End-to-End Test**:
   - Enroll new person on Raspberry Pi 1 (Heartbeat button)
   - Wait for Supabase sync (~30 seconds)
   - Verify new person appears on WaveShare display (Pi 2)
   - Both Pis operate independently via Supabase

### Step 5: Development System Setup (Optional)
1. On Mac/PC: Clone repository, create venv, install requirements
2. Configure `config/.env` with API keys
3. Test camera: `python main.py identify`
4. Enroll test person: `python main.py enroll`
5. Sync to Supabase: `python main.py sync`
6. Open frontend: `open frontend/index.html`
7. Verify persons appear in web dashboard

---

## Troubleshooting

### Raspberry Pi 1 (Yuno Glasses) Issues
- **Camera not detected**: Run `vcgencmd get_camera` or check `lsusb` for USB webcam
- **Button not responding**: Verify GPIO wiring, test with `gpio readall`
- **Bluetooth speaker connection lost**: Re-pair with `bluetoothctl connect MAC_ADDRESS`
- **Supabase sync failed**: Check internet connection, verify API keys in `.env`
- **TTS not working**: Test audio output with `speaker-test`, check Bluetooth connection

### Raspberry Pi 2 (WaveShare Display) Issues
- **No display on LED matrix**: Check power supply, verify GPIO connections
- **MQTT not accessible**: Check firewall, ensure Mosquitto listening on 0.0.0.0
- **GPIO permission denied**: Run `sudo usermod -aG gpio $USER` and reboot
- **Persons not appearing**: Verify Supabase connection, check data loader logs
- **Quiz mode not working**: Test MQTT with `mosquitto_sub -t '#'`

### Arduino Issues
- **WiFi connection failed**: Check SSID/password, ensure 2.4GHz network
- **MQTT not connecting**: Verify Raspberry Pi 2 IP (not Pi 1!), test with `ping`
- **LCD contrast too dark/light**: Adjust potentiometer on V0 pin
- **Joystick not responding**: Check analog pin connections (A0, A1)

### Network Issues
- **Arduino can't reach MQTT**: Ensure Arduino connected to same WiFi as Pi 2
- **MQTT timeout**: Check firewall rules on Raspberry Pi 2
- **Supabase connection failed**: Verify internet access, check API keys
- **Pi 1 and Pi 2 not syncing**: Check Supabase connection on BOTH Pis independently

### Data Sync Issues
- **Person enrolled on Pi 1 not appearing on Pi 2**: 
  - Check Supabase dashboard to verify person exists
  - Verify photo uploaded to Supabase Storage
  - Check Pi 2 data loader logs for sync errors
  - Wait up to 60 seconds for automatic refresh

---

## Notes

- **Raspberry Pi 5 Required**: PioMatter driver only supports Pi 5 (not compatible with Pi 4)
- **Two Independent Systems**: Pi 1 (Yuno Glasses) and Pi 2 (WaveShare) operate independently
- **Supabase as Single Source of Truth**: Both Pis sync to Supabase, no direct Pi-to-Pi communication
- **MQTT Only on Pi 2**: Only Raspberry Pi 2 runs MQTT broker (for Arduino communication)
- **Arduino R4 WiFi**: Older Arduino boards require separate WiFi shield
- **Power Consumption**: LED matrix at 50% brightness = optimal balance (bright + efficient)
- **Cooling**: Raspberry Pi 5 runs hot under load, active cooling recommended for both Pis
- **Cable Management**: Use cable ties to organize GPIO ribbon cables
- **Portable Operation**: Pi 1 can run on power bank for ~4 hours with 20,000mAh battery
- **Development Optional**: Mac/PC development system NOT required for production operation

---

## Related Documentation

- **Main README.md**: Software setup, Python environment, database configuration
- **src/README.md**: Face recognition backend, OpenAI integration, button handler
- **frontend/README.md**: Web dashboard for person management
- **waveshare/README.md**: RGB LED matrix display system details (Pi 2)
- **Arduino firmware**: `Arduino/Commands_Senden_UP_RIGHT_LEFT_DOWN/`

---

## System Comparison

| Feature                  | Raspberry Pi 1 (Yuno Glasses) | Raspberry Pi 2 (WaveShare Display) | Mac/PC (Development) |
|--------------------------|-------------------------------|-------------------------------------|----------------------|
| **Purpose**              | Portable face recognition     | Stationary display & quiz mode      | Development & testing|
| **Camera**               | ✅ Yes (Pi Camera or USB)     | ❌ No                               | ✅ Optional (for testing) |
| **Microphone**           | ✅ Yes (USB)                  | ❌ No                               | ✅ Optional          |
| **Audio Output**         | ✅ Bluetooth speaker          | ✅ Optional (TTS via speakers)      | ✅ Built-in speakers |
| **Physical Buttons**     | ✅ 2 buttons (GPIO 17, 27)    | ❌ No                               | ❌ No                |
| **WaveShare Display**    | ❌ No                         | ✅ Yes (64x64 RGB matrix)           | ❌ No                |
| **MQTT Broker**          | ❌ No                         | ✅ Yes (for Arduino)                | ❌ No                |
| **MQTT Client**          | ❌ No                         | ✅ Yes (receives from Arduino)      | ❌ No                |
| **Supabase Sync**        | ✅ Yes (enrolls & syncs)      | ✅ Yes (fetches persons)            | ✅ Optional          |
| **Face Recognition**     | ✅ Yes (ArcFace ONNX)         | ❌ No                               | ✅ Yes (testing)     |
| **Quiz Mode**            | ❌ No                         | ✅ Yes (OpenAI + joystick)          | ❌ No                |
| **Power Source**         | Portable (power bank)         | Stationary (AC adapter)             | AC adapter           |
| **Operation Mode**       | Standalone (no Mac needed)    | Standalone (no Mac needed)          | Development only     |
| **Communication**        | Supabase only                 | Supabase + MQTT (Arduino)           | Supabase only        |
