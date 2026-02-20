# ARIA Agent Automation Capabilities

This document outlines all the tools and APIs that ARIA can use to automate various platforms and systems.

---

## 🌐 Web & YouTube Automation

| Platform | Tool / API         | What it Automates       | Visible Output             |
| -------- | ------------------ | ----------------------- | -------------------------- |
| YouTube  | `pywhatkit`        | Search, play videos     | Browser opens, video plays |
| YouTube  | YouTube Data API   | Search, stats, comments | Data → GUI/log             |
| YouTube  | `pytube`, `yt-dlp` | Download videos/audio   | Files appear               |
| Web      | `requests`         | HTTP calls              | Data fetched               |
| Web      | `beautifulsoup4`   | HTML parsing            | Parsed content             |
| Web      | `scrapy`           | Large-scale scraping    | Data pipelines             |
| Search   | SerpAPI            | Google/Bing search      | Structured results         |

---

## 💬 Messaging & Communication

| Platform | Tool / API            | Capability             | Visible Output     |
| -------- | --------------------- | ---------------------- | ------------------ |
| WhatsApp | `pywhatkit`           | Send/schedule messages | WhatsApp Web sends |
| WhatsApp | Selenium / Playwright | Full chat automation   | Chats update live  |
| Email    | `smtplib`             | Send mail              | Email received     |
| Email    | `imaplib`             | Read inbox             | Mailbox changes    |
| Email    | Gmail API             | Full mailbox control   | Live inbox updates |
| Telegram | Bot API               | Messaging bots         | Messages appear    |
| Discord  | Discord API           | Bots, automation       | Messages, actions  |
| Slack    | Slack API             | Workspace automation   | Channel updates    |

---

## 🖥️ GUI & Desktop Automation

| Layer  | Tool            | Purpose                      | Visible Effect        |
| ------ | --------------- | ---------------------------- | --------------------- |
| GUI    | `pyautogui`     | Mouse, keyboard, screenshots | Cursor moves, typing  |
| GUI    | `pynput`        | Input hooks                  | Keystrokes captured   |
| X11    | `xdotool`       | Window & input control       | Windows move/type     |
| X11    | `wmctrl`        | Window management            | Focus, resize         |
| Screen | `opencv-python` | Button/image detection       | Smart clicking        |
| Screen | `pytesseract`   | OCR                          | Text read from screen |
| Screen | `easyocr`       | OCR (DL-based)               | Screen understanding  |

---

## ⚙️ OS & System Control

| Area     | Tool          | Capability           | Visible Output   |
| -------- | ------------- | -------------------- | ---------------- |
| OS       | `os`          | Files, env, paths    | FS changes       |
| OS       | `subprocess`  | Run commands         | Apps launch      |
| OS       | `psutil`      | CPU, RAM, processes  | System reacts    |
| System   | `systemctl`   | Services             | Services restart |
| Display  | `xrandr`      | Resolution, monitors | Screen changes   |
| Desktop  | `notify-send` | Notifications        | Popups           |
| Settings | `gsettings`   | GNOME config         | UI updates       |

---

## 📁 Files & Office Automation

| Domain | Tool            | Automates               | Visible Output     |
| ------ | --------------- | ----------------------- | ------------------ |
| Files  | `shutil`        | Copy, move, delete      | Files change       |
| Files  | `pathlib`       | Path ops                | Clean FS logic     |
| Files  | `watchdog`      | FS events               | Real-time triggers |
| Docs   | `python-docx`   | Word docs               | Docs update        |
| Excel  | `openpyxl`      | Spreadsheets            | Cells change       |
| Data   | `pandas`        | Data pipelines          | Tables, CSVs       |
| Slides | `python-pptx`   | Presentations           | Slides created     |
| Office | LibreOffice UNO | Full GUI office control | Docs open/edit     |

---

## 🎵 Media & Entertainment

| Platform | Tool / API      | Capability              | Visible Output   |
| -------- | --------------- | ----------------------- | ---------------- |
| Spotify  | Spotify Web API | Play, search, playlists | Music plays      |
| Spotify  | `spotipy`       | Python wrapper          | Playback control |
| Media    | VLC Python      | Media control           | Video/audio      |
| Media    | `python-mpv`    | Media player            | Playback         |
| Media    | DBus MPRIS      | Media control           | Player responds  |
| Media    | `ffmpeg`        | Edit/record             | Media files      |

---

## 🧠 Vision & AI Integration

| Component | Tool / Model    | Capability               | Visible Effect          |
| --------- | --------------- | ------------------------ | ----------------------- |
| VLM       | LLaVA / Qwen-VL | Visual reasoning         | Understands UI          |
| DOM       | Playwright      | Element extraction       | Accurate click targets  |
| Hybrid    | VLM + DOM       | State-aware automation   | Smart UI navigation     |
| OCR       | EasyOCR         | Text extraction          | Reads screen content    |
| Training  | Unsloth         | Fine-tune on UI data     | Improved accuracy       |
