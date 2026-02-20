# ARIA v.1 — AI Desktop Assistant

**ARIA** (Artificially Resilient Intelligent Assistant) is a JARVIS-style AI desktop assistant for Linux. It combines voice input/output, WhatsApp automation, YouTube media control, system management, and more — all through natural language.

## ✨ Features

- 🗣️ **Voice I/O** — Natural speech input via Vosk + JARVIS-style voice output via XTTS-v2
- 💬 **WhatsApp** — Send messages, files, GIFs, stickers, and read conversations via bridge
- 🎵 **YouTube** — Search, play, pause, skip, fullscreen — all via voice
- 🖥️ **System Control** — Volume, brightness, screenshots, battery status, app launching
- 📧 **Gmail & Calendar** — Read emails, create events via Google API
- 📄 **PDF Tools** — Create PDFs, extract images from PDFs
- 🎨 **Image Generation** — Generate images via Gemini and set as wallpaper
- 🧠 **Memory** — Learns your preferences and remembers facts
- 🔧 **Shell Access** — Execute terminal commands via natural language

## 🚀 Quick Start

### Prerequisites
- **OS**: Ubuntu/Linux with X11
- **Python**: 3.10+
- **Node.js**: 18+ (for WhatsApp bridge)
- **GPU**: NVIDIA GPU recommended for XTTS voice (works on CPU too)

### 1. Clone & Setup

```bash
git clone https://github.com/Faykar78/ARIA-v.1.git
cd ARIA-v.1

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install system dependencies
sudo apt install xdotool wmctrl brightnessctl pulseaudio-utils
```

### 2. Configure API Keys

#### Google OAuth (Gmail & Calendar)
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable **Gmail API** and **Google Calendar API**
3. Create **OAuth 2.0 Client ID** (Desktop Application)
4. Download the credentials JSON
5. Copy to `data/google_credentials.json`:
```bash
cp data/google_credentials.example.json data/google_credentials.json
# Edit with your actual credentials
```

#### YouTube API Key
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable **YouTube Data API v3**
3. Create an **API Key**
4. Add it to `data/personal_context.json`:
```bash
cp data/personal_context.example.json data/personal_context.json
# Edit and add your YouTube API key
```

#### Gemini API (Image Generation)
Set the environment variable:
```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

#### DeepSeek API (Brain/LLM)
ARIA uses DeepSeek as its brain (via OpenAI-compatible API):
```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
```

### 3. Setup WhatsApp Bridge

```bash
cd whatsapp-bridge
npm install
node index.js
# Scan QR code with WhatsApp on first run
# Session persists in ~/.whatsapp-aria/
```

### 4. Download Voice Model

```bash
python3 download_voice.py
# Downloads XTTS-v2 model and JARVIS reference voice
```

### 5. Run ARIA

```bash
python3 aria_gui.py
```

## 📁 Project Structure

```
ARIA-v.1/
├── aria_gui.py              # Main GTK application (GUI + brain + voice)
├── main.py                  # Alternative launcher
├── requirements.txt         # Python dependencies
├── data/
│   ├── google_credentials.example.json  # Template for Google OAuth
│   └── personal_context.example.json    # Template for personal config
├── src/
│   ├── automation_tools.py  # System tools (volume, brightness, media, etc.)
│   ├── bridges/
│   │   ├── whatsapp_bridge.py    # Playwright-based WhatsApp bridge
│   │   ├── telegram_bridge.py    # Telegram integration
│   │   └── youtube_bridge.py     # YouTube utilities
│   ├── tools/
│   │   ├── google_gmail.py       # Gmail API integration
│   │   ├── google_calendar.py    # Calendar API integration
│   │   └── pdf_tools.py          # PDF creation & extraction
│   └── workflows/                # Automated workflows
├── whatsapp-bridge/          # Node.js WhatsApp Web bridge (HTTP API)
│   ├── index.js              # Express server + whatsapp-web.js
│   └── package.json
├── models/                   # Voice models (gitignored, download locally)
├── docs/
│   ├── CAPABILITIES.md       # Full feature documentation
│   └── GUI_FINETUNING_GUIDE.md
└── tests/                    # Test files
```

## 🎤 Voice Commands (Examples)

| Command | What it does |
|---------|-------------|
| "play chammak challo" | Searches YouTube & auto-plays |
| "pause" / "ruk ja" | Pauses playback |
| "full screen" / "bada karo" | Toggles fullscreen |
| "next song" / "skip" | Plays next video |
| "send hi to John on WhatsApp" | Sends WhatsApp message |
| "read my messages from KRACK" | Reads WhatsApp messages |
| "set brightness to 50" | Adjusts screen brightness |
| "volume max" / "blast it" | Sets volume to 100% |
| "take a screenshot" | Captures screen |
| "what's my battery?" | Shows battery status |
| "open file manager" | Launches Nautilus |
| "search Google for..." | Opens browser search |
| "create a PDF titled Notes" | Creates a PDF file |
| "remind me about meeting" | Adds calendar event |

## ⚙️ Configuration

### `data/personal_context.json`
Customize ARIA with your name, system specs, and API keys:
```json
{
    "user_profile": {
        "name": "YourName",
        "system": "Your hardware description"
    },
    "api_keys": {
        "youtube": "YOUR_YOUTUBE_API_KEY"
    }
}
```

### Environment Variables
| Variable | Purpose | Required |
|----------|---------|----------|
| `DEEPSEEK_API_KEY` | LLM brain | ✅ |
| `GEMINI_API_KEY` | Image generation | Optional |
| `YOUTUBE_API_KEY` | YouTube search (also configurable in personal_context.json) | Optional |

## 📝 License

MIT License

## 🙏 Credits

- [whatsapp-web.js](https://github.com/pedroslopez/whatsapp-web.js) — WhatsApp Web automation
- [Coqui XTTS-v2](https://github.com/coqui-ai/TTS) — JARVIS voice synthesis
- [Vosk](https://alphacephei.com/vosk/) — Offline speech recognition
- [DeepSeek](https://deepseek.com/) — LLM brain
