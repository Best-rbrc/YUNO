# Commands — Running & Testing the Modes

Quick reference for running each mode locally (Mac webcam) and on the Raspberry Pi.

## Setup (once per terminal)

Use the project virtualenv `.venv` — it has all dependencies (`onnxruntime`, `deepface`, etc.).
The conda env is **not** complete, so don't use it.

```bash
cd ~/Desktop/HandsOnHCI
source .venv/bin/activate        # then just use `python ...`
```

Or call it directly without activating:

```bash
.venv/bin/python main.py <command>
```

> First run on macOS will pop up **Camera** and **Microphone** permission prompts for
> your terminal app (Terminal / VS Code). Allow both, or you'll get a gray
> "NO CAMERA FOUND" placeholder image.

---

## Modes

| Mode | Command | What it does |
|------|---------|--------------|
| **Enroll** | `python main.py enroll --name "TestPerson"` | Webcam + mic → adds a new person (face + audio + context). Merges if the face is already known. |
| **Identify** | `python main.py identify` | Webcam → matches a face, speaks the result (TTS). |
| **Identify (local)** | `python main.py identify_local` | Same as identify but console-only, no audio. |
| **Add face** | `python main.py add_face --name "TestPerson"` | Photo-only enroll (no audio). Adds unknown faces in frame. |
| **Rizz Mode** | `python main.py rizz` | Webcam → gender detection → social tips. |
| **Sync** | `python main.py sync` | Syncs local DB with Supabase (needs `config/.env`). |
| **Button mode** | `python main.py button` | Raspberry Pi only — single-button listener (see below). |

### Enroll

```bash
python main.py enroll --name "TestPerson"
# or let it detect the name from speech:
python main.py enroll
```

### Identify

```bash
python main.py identify          # with TTS
python main.py identify_local    # console only, no audio
```

### Rizz Mode

```bash
python main.py rizz
```

### Sync

```bash
python main.py sync
```

---

## Button mode (Raspberry Pi only)

`python main.py button` needs `RPi.GPIO` and the physical button on **GPIO 17**.
It loads on Mac but the button callbacks never fire without the hardware, so test the
underlying actions with the direct commands above instead.

Single-button mapping:

| Press | Action | Equivalent test command |
|-------|--------|-------------------------|
| 1× | Enroll | `python main.py enroll` |
| 2× | Identify | `python main.py identify` |
| 3× | Rizz Mode | `python main.py rizz` |
| Hold | Sync | `python main.py sync` |

```bash
python main.py button
```

---

## Notes

- **Camera:** On Mac the webcam path is used automatically (OpenCV); on the Pi it uses
  `rpicam-still`. The 180° rotation is applied only on the Pi camera, not the Mac webcam.
- **Models:** `models/w600k_r50.onnx` (ArcFace) and `models/face_detection_yunet_2023mar.onnx`
  (YuNet) must be present.
- **Config:** `config/.env` holds OpenAI + Supabase credentials; `config/settings.yaml` holds
  app settings (language, thresholds).
