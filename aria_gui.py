#!/usr/bin/env python3
"""
ARIA — Autonomous Responsive Interface Assistant
═══════════════════════════════════════════════════
Futuristic JARVIS-like GTK3 Interface
"""

# Auto-activate venv if not already active
import os, sys
_venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python3")
if os.path.exists(_venv_python) and sys.executable != _venv_python:
    os.execv(_venv_python, [_venv_python] + sys.argv)

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo

import cairo
import math
import time
import threading
import subprocess
import sys
import os
import re
import json

# Add project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.automation_tools import AutomationTools
from src.brain import LocalBrain
from src.voice_engine import VoiceEngine

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
WINDOW_W, WINDOW_H = 1200, 750
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "deepseek-v3.1:671b-cloud"

# Colors (R, G, B, A) — JARVIS palette
COL_BG          = (0.039, 0.039, 0.059, 1.0)       # #0a0a0f
COL_PANEL       = (0.102, 0.102, 0.180, 0.85)       # #1a1a2e
COL_PANEL_EDGE  = (0.0, 0.898, 1.0, 0.25)           # cyan glow border
COL_CYAN        = (0.0, 0.898, 1.0, 1.0)            # #00e5ff
COL_CYAN_DIM    = (0.0, 0.898, 1.0, 0.35)
COL_TEXT        = (0.88, 0.92, 0.96, 1.0)            # off-white
COL_TEXT_DIM    = (0.55, 0.60, 0.68, 1.0)
COL_USER_BUB    = (0.0, 0.898, 1.0, 0.13)
COL_ARIA_BUB    = (0.12, 0.12, 0.20, 0.90)
COL_GREEN       = (0.18, 0.85, 0.45, 1.0)
COL_RED         = (0.92, 0.25, 0.25, 1.0)
COL_ORANGE      = (1.0, 0.65, 0.0, 1.0)
COL_MAGENTA     = (0.75, 0.20, 0.85, 1.0)

# States
STATE_IDLE       = "IDLE"
STATE_LISTENING  = "LISTENING"
STATE_PROCESSING = "PROCESSING"
STATE_SPEAKING   = "SPEAKING"
STATE_ERROR      = "ERROR"


# ══════════════════════════════════════════════════════════════════════════════
# REFLEX ENGINE — Inline subset from main.py for immediate command dispatch
# ══════════════════════════════════════════════════════════════════════════════

REFLEX_PATTERNS = {
    "open browser": {"tool": "run_command", "args": {"command": "xdg-open https://google.com"}},
    "open google":  {"tool": "run_command", "args": {"command": "xdg-open https://google.com"}},
    "open whatsapp": {"tool": "run_command", "args": {"command": "xdg-open https://web.whatsapp.com"}},
    "open gemini":  {"tool": "run_command", "args": {"command": "xdg-open https://gemini.google.com"}},
    "open chatgpt": {"tool": "run_command", "args": {"command": "xdg-open https://chat.openai.com"}},
    "open claude":  {"tool": "run_command", "args": {"command": "xdg-open https://claude.ai"}},
}

REGEX_COMMANDS = [
    # Volume
    (r'(?:set\s+)?volume\s+(?:to\s+)?(\d+)', lambda m: ("set_volume", {"level": int(m.group(1))})),
    (r'volume\s+up', lambda m: ("run_command", {"command": "pactl set-sink-volume @DEFAULT_SINK@ +10%"})),
    (r'volume\s+down', lambda m: ("run_command", {"command": "pactl set-sink-volume @DEFAULT_SINK@ -10%"})),
    (r'mute', lambda m: ("run_command", {"command": "pactl set-sink-mute @DEFAULT_SINK@ 1"})),
    (r'unmute', lambda m: ("run_command", {"command": "pactl set-sink-mute @DEFAULT_SINK@ 0"})),
    # Brightness
    (r'(?:set\s+)?brightness\s+(?:to\s+)?(\d+)', lambda m: ("set_brightness", {"level": int(m.group(1))})),
    (r'brightness\s+up', lambda m: ("run_command", {"command": "brightnessctl set +10%"})),
    (r'brightness\s+down', lambda m: ("run_command", {"command": "brightnessctl set 10%-"})),
    # YouTube (ONLY when "youtube" is explicitly mentioned)
    (r'(?:play|search)\s+(.+?)\s+on\s+youtube\s*$',
     lambda m: ("youtube_search", {"query": m.group(1).strip()})),
    (r'(?:play|search)\s+(?:on\s+)?youtube\s+(.+)',
     lambda m: ("youtube_search", {"query": m.group(1).strip()})),
    # Email
    (r'send\s+(?:an?\s+)?email\s+to\s+(\S+)\s+(?:subject\s+)?["\'](.+?)["\']\s+(?:body\s+)?["\'](.+?)["\']',
     lambda m: ("email_send", {"to": m.group(1), "subject": m.group(2), "body": m.group(3)})),
    (r'read\s+(?:my\s+)?emails?', lambda m: ("email_read", {"limit": 5})),
    # Web/Google search (generic "search for X", "google X", "look up X")
    (r'(?:google|search\s+for|search|look\s+up)\s+(.+?)(?:\s+on\s+(?:the\s+)?web)?\s*$',
     lambda m: ("run_command", {"command": f"xdg-open 'https://www.google.com/search?q={m.group(1).strip().replace(' ', '+')}'"})),
    # System info
    (r'system\s+(?:info|status)', lambda m: ("get_system_info", {})),
    # Keyboard backlight
    (r'keyboard\s+(?:light\s+)?(?:backlight\s+)?on', lambda m: ("run_command", {"command": os.path.expanduser("~/Downloads/mightbe_done/scripts/kb_backlight.sh") + " on"})),
    (r'keyboard\s+(?:light\s+)?(?:backlight\s+)?off', lambda m: ("run_command", {"command": os.path.expanduser("~/Downloads/mightbe_done/scripts/kb_backlight.sh") + " off"})),
    (r'keyboard\s+(?:color\s+)?(?:to\s+)?(red|blue|green|white|purple|orange|cyan|pink|yellow)',
     lambda m: ("run_command", {"command": os.path.expanduser("~/Downloads/mightbe_done/scripts/kb_backlight.sh") + f" color {{'red':'FF0000','blue':'0000FF','green':'00FF00','white':'FFFFFF','purple':'800080','orange':'FFA500','cyan':'00FFFF','pink':'FFC0CB','yellow':'FFFF00'}}['{m.group(1)}']"})),
    # Notification
    (r'notify\s+(.+)', lambda m: ("notify", {"title": "ARIA", "message": m.group(1).strip()})),
]


def resolve_command(text):
    """Match user text to a tool + args. Returns (tool_name, kwargs) or None."""
    lower = text.lower().strip()

    # Exact match
    for pattern, action in REFLEX_PATTERNS.items():
        if lower == pattern or lower.startswith(pattern + " "):
            return (action["tool"], action["args"])

    # Regex match
    for pattern, builder in REGEX_COMMANDS:
        m = re.search(pattern, lower)
        if m:
            return builder(m)

    return None


# ══════════════════════════════════════════════════════════════════════════════
# SERVICE STATUS CHECKER
# ══════════════════════════════════════════════════════════════════════════════

def check_services():
    """Return dict of service → bool."""
    results = {}

    # WhatsApp bridge
    try:
        import requests
        r = requests.get("http://localhost:3001/status", timeout=2)
        results["WhatsApp"] = r.status_code == 200
    except Exception:
        results["WhatsApp"] = False

    # Telegram
    try:
        from src.bridges.telegram_bridge import telegram_bridge
        results["Telegram"] = bool(telegram_bridge.token and telegram_bridge.token != "YOUR_TOKEN_HERE")
    except Exception:
        results["Telegram"] = False

    # Email
    try:
        from src.bridges.email_bridge import email_bridge
        results["Email"] = email_bridge._is_configured()
    except Exception:
        results["Email"] = False

    # Volume (pactl)
    try:
        r = subprocess.run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], capture_output=True, timeout=3)
        results["Volume"] = r.returncode == 0
    except Exception:
        results["Volume"] = False

    # Brightness (brightnessctl)
    try:
        r = subprocess.run(["brightnessctl", "-m"], capture_output=True, timeout=3)
        results["Brightness"] = r.returncode == 0
    except Exception:
        results["Brightness"] = False

    # YouTube (pywhatkit)
    try:
        import pywhatkit  # noqa: F401
        results["YouTube"] = True
    except ImportError:
        results["YouTube"] = False

    # Ollama LLM
    try:
        import requests as _req
        r = _req.get("http://localhost:11434/api/tags", timeout=2)
        results["Ollama"] = r.status_code == 200
    except Exception:
        results["Ollama"] = False

    return results


# ══════════════════════════════════════════════════════════════════════════════
# CAIRO DRAWING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def draw_rounded_rect(cr, x, y, w, h, r=12):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def draw_text(cr, text, x, y, size=13, color=COL_TEXT, bold=False, max_width=None):
    layout = PangoCairo.create_layout(cr)
    weight = "Bold" if bold else "Regular"
    layout.set_font_description(Pango.FontDescription(f"Sans {weight} {size}"))
    if max_width:
        layout.set_width(int(max_width * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
    layout.set_text(text, -1)
    cr.set_source_rgba(*color)
    cr.move_to(x, y)
    PangoCairo.show_layout(cr, layout)
    return layout.get_pixel_size()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class ARIAWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="A.R.I.A")
        self.set_default_size(WINDOW_W, WINDOW_H)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_decorated(False)
        self.set_app_paintable(True)

        # Transparency
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        # State
        self.state = STATE_IDLE
        self.messages = []  # list of (role, text, timestamp)
        self.tools = AutomationTools()
        self.brain = None  # Lazy-init LocalBrain
        self.personal_context = self._load_personal_context()
        self.brain_ready = False
        self.services = {}
        self.voice = VoiceEngine()
        self.bridge_proc = None  # WhatsApp bridge subprocess
        self.anim_t = 0.0
        self.orb_rings = [0.0] * 5  # ring phase offsets
        self.dragging = False
        self.drag_x = 0
        self.drag_y = 0

        # Build UI
        self._build_ui()
        self._apply_css()

        # Animation timer (60 FPS)
        GLib.timeout_add(16, self._tick)

        # Check services + init brain + voice + auto-start bridge in background
        threading.Thread(target=self._load_services, daemon=True).start()
        threading.Thread(target=self._init_brain, daemon=True).start()
        threading.Thread(target=self._start_whatsapp_bridge, daemon=True).start()
        # Auto-accept XTTS license and load voice engine
        os.environ['COQUI_TOS_AGREED'] = '1'
        self.voice.init_async()

        # Welcome message
        self._add_message("aria", "Systems online. How can I assist you?")

        self.connect("destroy", self._on_destroy)
        self.connect("button-press-event", self._on_button_press)
        self.connect("button-release-event", self._on_button_release)
        self.connect("motion-notify-event", self._on_motion)
        self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK)

        self.show_all()

    # ─────────────────────────────────────────────────────────────────────
    # UI BUILD
    # ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Main overlay for background painting
        overlay = Gtk.Overlay()
        self.add(overlay)

        # Background canvas
        self.canvas = Gtk.DrawingArea()
        self.canvas.connect("draw", self._draw_background)
        overlay.add(self.canvas)

        # Content box on top
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_margin_top(0)
        overlay.add_overlay(vbox)

        # ── Titlebar ──
        titlebar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        titlebar.set_size_request(-1, 44)
        titlebar.get_style_context().add_class("titlebar")

        title_label = Gtk.Label()
        title_label.set_markup(
            '<span font="16" weight="bold" foreground="#00e5ff">  ◈  A.R.I.A</span>'
            '<span font="10" foreground="#555a6e">  —  Autonomous Responsive Interface Assistant</span>'
        )
        title_label.set_halign(Gtk.Align.START)
        titlebar.pack_start(title_label, True, True, 10)

        # Window controls
        for icon, action in [("─", self.iconify), ("☐", self._toggle_maximize), ("✕", self.close)]:
            btn = Gtk.Button(label=icon)
            btn.set_size_request(36, 30)
            btn.get_style_context().add_class("win-btn")
            btn.connect("clicked", lambda w, a=action: a())
            titlebar.pack_end(btn, False, False, 2)

        vbox.pack_start(titlebar, False, False, 0)

        # ── Separator ──
        sep = Gtk.DrawingArea()
        sep.set_size_request(-1, 1)
        sep.connect("draw", lambda w, cr: (cr.set_source_rgba(*COL_CYAN_DIM), cr.paint()))
        vbox.pack_start(sep, False, False, 0)

        # ── Main content (3-column) ──
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        vbox.pack_start(hbox, True, True, 0)

        # LEFT: Service Status
        left_panel = self._build_status_panel()
        hbox.pack_start(left_panel, False, False, 0)

        # CENTER: Orb + Chat + Input
        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        hbox.pack_start(center, True, True, 0)

        # Orb area
        self.orb_area = Gtk.DrawingArea()
        self.orb_area.set_size_request(-1, 170)
        self.orb_area.connect("draw", self._draw_orb)
        center.pack_start(self.orb_area, False, False, 0)

        # State label
        self.state_label = Gtk.Label()
        self.state_label.set_markup(f'<span font="10" foreground="#00e5ff">{self.state}</span>')
        center.pack_start(self.state_label, False, False, 2)

        # Chat scroll
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.get_style_context().add_class("chat-scroll")

        self.chat_area = Gtk.DrawingArea()
        self.chat_area.connect("draw", self._draw_chat)
        self.chat_area.set_size_request(-1, 2000)
        scroll.add(self.chat_area)
        self.chat_scroll = scroll
        center.pack_start(scroll, True, True, 5)

        # Input area
        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        input_box.set_margin_start(15)
        input_box.set_margin_end(15)
        input_box.set_margin_bottom(12)
        input_box.set_margin_top(4)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Command ARIA…")
        self.entry.get_style_context().add_class("cmd-entry")
        self.entry.connect("activate", self._on_send)
        input_box.pack_start(self.entry, True, True, 0)

        mic_btn = Gtk.Button(label="🎤")
        mic_btn.set_size_request(42, 38)
        mic_btn.get_style_context().add_class("mic-btn")
        mic_btn.set_tooltip_text("Voice Input (Vosk)")
        mic_btn.connect("clicked", self._on_mic)
        input_box.pack_start(mic_btn, False, False, 0)

        send_btn = Gtk.Button(label="➤")
        send_btn.set_size_request(42, 38)
        send_btn.get_style_context().add_class("send-btn")
        send_btn.connect("clicked", self._on_send)
        input_box.pack_start(send_btn, False, False, 0)

        center.pack_start(input_box, False, False, 0)

        # RIGHT: Quick Actions
        right_panel = self._build_actions_panel()
        hbox.pack_end(right_panel, False, False, 0)

    def _build_status_panel(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_size_request(185, -1)
        box.set_margin_top(12)
        box.set_margin_start(10)
        box.set_margin_bottom(10)
        box.get_style_context().add_class("side-panel")

        header = Gtk.Label()
        header.set_markup('<span font="11" weight="bold" foreground="#00e5ff">SERVICES</span>')
        header.set_halign(Gtk.Align.START)
        header.set_margin_start(12)
        header.set_margin_top(10)
        box.pack_start(header, False, False, 0)

        self.service_labels = {}
        services = ["Ollama", "WhatsApp", "Telegram", "Email", "YouTube", "Volume", "Brightness"]
        for svc in services:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.set_margin_start(12)
            row.set_margin_top(4)

            dot = Gtk.Label()
            dot.set_markup('<span foreground="#555a6e">●</span>')
            row.pack_start(dot, False, False, 0)

            lbl = Gtk.Label(label=svc)
            lbl.set_halign(Gtk.Align.START)
            lbl.get_style_context().add_class("svc-label")
            row.pack_start(lbl, True, True, 0)

            self.service_labels[svc] = dot
            box.pack_start(row, False, False, 0)

        # Spacer
        box.pack_start(Gtk.Box(), True, True, 0)

        # System info area
        self.sys_label = Gtk.Label()
        self.sys_label.set_markup('<span font="8" foreground="#555a6e">Loading…</span>')
        self.sys_label.set_halign(Gtk.Align.START)
        self.sys_label.set_margin_start(12)
        self.sys_label.set_margin_bottom(10)
        self.sys_label.set_line_wrap(True)
        self.sys_label.set_max_width_chars(22)
        box.pack_start(self.sys_label, False, False, 0)

        return box

    def _build_actions_panel(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_size_request(175, -1)
        box.set_margin_top(12)
        box.set_margin_end(10)
        box.set_margin_bottom(10)
        box.get_style_context().add_class("side-panel")

        header = Gtk.Label()
        header.set_markup('<span font="11" weight="bold" foreground="#00e5ff">QUICK ACTIONS</span>')
        header.set_halign(Gtk.Align.START)
        header.set_margin_start(10)
        header.set_margin_top(10)
        box.pack_start(header, False, False, 0)

        actions = [
            ("🔊  Volume Up",     "volume up"),
            ("🔉  Volume Down",   "volume down"),
            ("🔇  Mute Toggle",   "mute"),
            ("☀️  Bright +",      "brightness up"),
            ("🌙  Bright −",      "brightness down"),
            ("🎵  YouTube",       "play lofi hip hop on youtube"),
            ("📧  Read Email",    "read emails"),
            ("💻  Sys Info",      "system info"),
            ("🔔  Notify",        "notify ARIA is running"),
            ("🌐  Open Browser",  "open browser"),
        ]

        for label, cmd in actions:
            btn = Gtk.Button(label=label)
            btn.set_size_request(-1, 34)
            btn.get_style_context().add_class("action-btn")
            btn.connect("clicked", lambda w, c=cmd: self._execute_text(c))
            box.pack_start(btn, False, False, 0)

        box.pack_start(Gtk.Box(), True, True, 0)
        return box

    # ─────────────────────────────────────────────────────────────────────
    # CSS
    # ─────────────────────────────────────────────────────────────────────

    def _apply_css(self):
        css = b"""
        window {
            background-color: rgba(10, 10, 15, 0.95);
        }
        .titlebar {
            background-color: rgba(14, 14, 24, 0.95);
            padding: 4px 6px;
        }
        .win-btn {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(0,229,255,0.15);
            border-radius: 4px;
            color: #8892a4;
            font-size: 14px;
            padding: 0;
            min-width: 30px;
            min-height: 26px;
        }
        .win-btn:hover {
            background: rgba(0,229,255,0.12);
            color: #00e5ff;
        }
        .side-panel {
            background-color: rgba(18, 18, 36, 0.70);
            border: 1px solid rgba(0, 229, 255, 0.12);
            border-radius: 10px;
            padding: 4px;
        }
        .svc-label {
            color: #8892a4;
            font-size: 12px;
        }
        .action-btn {
            background: rgba(0, 229, 255, 0.06);
            border: 1px solid rgba(0, 229, 255, 0.18);
            border-radius: 6px;
            color: #c0cad8;
            font-size: 11px;
            padding: 4px 8px;
            margin: 1px 6px;
        }
        .action-btn:hover {
            background: rgba(0, 229, 255, 0.16);
            color: #00e5ff;
            border-color: rgba(0, 229, 255, 0.45);
        }
        .cmd-entry {
            background: rgba(15, 15, 30, 0.85);
            border: 1px solid rgba(0, 229, 255, 0.25);
            border-radius: 8px;
            color: #e0e8f0;
            font-size: 13px;
            padding: 8px 14px;
            caret-color: #00e5ff;
        }
        .cmd-entry:focus {
            border-color: rgba(0, 229, 255, 0.6);
            box-shadow: 0 0 8px rgba(0, 229, 255, 0.15);
        }
        .mic-btn, .send-btn {
            background: rgba(0, 229, 255, 0.08);
            border: 1px solid rgba(0, 229, 255, 0.25);
            border-radius: 8px;
            color: #00e5ff;
            font-size: 16px;
            padding: 0;
        }
        .mic-btn:hover, .send-btn:hover {
            background: rgba(0, 229, 255, 0.22);
        }
        .chat-scroll {
            background: transparent;
        }
        scrollbar {
            background: transparent;
        }
        scrollbar slider {
            background: rgba(0, 229, 255, 0.18);
            border-radius: 4px;
            min-width: 6px;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # ─────────────────────────────────────────────────────────────────────
    # DRAWING
    # ─────────────────────────────────────────────────────────────────────

    def _draw_background(self, widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        # Dark gradient background
        pat = cairo.LinearGradient(0, 0, 0, h)
        pat.add_color_stop_rgba(0, 0.035, 0.035, 0.065, 1)
        pat.add_color_stop_rgba(0.5, 0.045, 0.04, 0.08, 1)
        pat.add_color_stop_rgba(1, 0.03, 0.03, 0.055, 1)
        cr.set_source(pat)
        # Rounded window
        draw_rounded_rect(cr, 0, 0, w, h, 14)
        cr.fill()

        # Subtle grid overlay
        cr.set_source_rgba(0.0, 0.898, 1.0, 0.015)
        cr.set_line_width(0.5)
        for gx in range(0, w, 40):
            cr.move_to(gx, 0)
            cr.line_to(gx, h)
        for gy in range(0, h, 40):
            cr.move_to(0, gy)
            cr.line_to(w, gy)
        cr.stroke()

        # Window border
        cr.set_source_rgba(*COL_PANEL_EDGE)
        cr.set_line_width(1.2)
        draw_rounded_rect(cr, 0.5, 0.5, w - 1, h - 1, 14)
        cr.stroke()

    def _draw_orb(self, widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        cx, cy = w / 2, h / 2 + 5
        t = self.anim_t

        # State-dependent params
        if self.state == STATE_LISTENING:
            base_r, pulse_amp, speed, glow = 38, 8, 3.0, 0.5
        elif self.state == STATE_PROCESSING:
            base_r, pulse_amp, speed, glow = 36, 5, 5.0, 0.6
        elif self.state == STATE_SPEAKING:
            base_r, pulse_amp, speed, glow = 40, 6, 2.0, 0.45
        elif self.state == STATE_ERROR:
            base_r, pulse_amp, speed, glow = 35, 3, 1.5, 0.3
        else:  # IDLE
            base_r, pulse_amp, speed, glow = 34, 4, 1.0, 0.3

        pulse = math.sin(t * speed) * pulse_amp
        r = base_r + pulse

        # Outer glow rings
        for i in range(4, 0, -1):
            ring_r = r + i * 14 + math.sin(t * speed * 0.7 + i) * 3
            alpha = glow * (0.08 / (i * 0.7))
            cr.set_source_rgba(0.0, 0.898, 1.0, alpha)
            cr.set_line_width(1.0 + (4 - i) * 0.3)
            cr.arc(cx, cy, ring_r, 0, 2 * math.pi)
            cr.stroke()

        # Rotating arcs (JARVIS style)
        for i in range(3):
            angle_offset = t * (0.8 + i * 0.3) + i * 2.094
            arc_r = r + 20 + i * 12
            arc_len = 0.8 + math.sin(t * 1.5 + i) * 0.3
            cr.set_source_rgba(0.0, 0.898, 1.0, 0.12 + i * 0.04)
            cr.set_line_width(1.5)
            cr.arc(cx, cy, arc_r, angle_offset, angle_offset + arc_len)
            cr.stroke()

        # Main orb — radial gradient
        pat = cairo.RadialGradient(cx, cy, r * 0.1, cx, cy, r)
        if self.state == STATE_ERROR:
            pat.add_color_stop_rgba(0, 1.0, 0.3, 0.3, 0.9)
            pat.add_color_stop_rgba(1, 0.5, 0.1, 0.1, 0.3)
        else:
            pat.add_color_stop_rgba(0, 0.15, 0.95, 1.0, 0.85)
            pat.add_color_stop_rgba(0.6, 0.0, 0.6, 0.85, 0.45)
            pat.add_color_stop_rgba(1, 0.0, 0.3, 0.5, 0.1)
        cr.set_source(pat)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.fill()

        # Inner bright core
        pat2 = cairo.RadialGradient(cx - r * 0.15, cy - r * 0.15, 0, cx, cy, r * 0.5)
        pat2.add_color_stop_rgba(0, 1, 1, 1, 0.7)
        pat2.add_color_stop_rgba(1, 1, 1, 1, 0)
        cr.set_source(pat2)
        cr.arc(cx, cy, r * 0.5, 0, 2 * math.pi)
        cr.fill()

    def _draw_chat(self, widget, cr):
        w = widget.get_allocated_width()
        y = 10
        bubble_max_w = min(480, w - 60)

        for role, text, ts in self.messages:
            is_user = role == "user"
            pad = 12
            # Measure text
            layout = PangoCairo.create_layout(cr)
            layout.set_font_description(Pango.FontDescription("Sans 12"))
            layout.set_width(int((bubble_max_w - pad * 2) * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            layout.set_text(text, -1)
            tw, th = layout.get_pixel_size()

            bub_w = tw + pad * 2
            bub_h = th + pad * 2 + 14  # extra for timestamp

            if is_user:
                bx = w - bub_w - 20
                cr.set_source_rgba(*COL_USER_BUB)
            else:
                bx = 20
                cr.set_source_rgba(*COL_ARIA_BUB)

            draw_rounded_rect(cr, bx, y, bub_w, bub_h, 10)
            cr.fill()

            # Border
            cr.set_source_rgba(*COL_PANEL_EDGE)
            cr.set_line_width(0.8)
            draw_rounded_rect(cr, bx, y, bub_w, bub_h, 10)
            cr.stroke()

            # Role label
            role_color = COL_CYAN if not is_user else (0.6, 0.75, 0.9, 0.8)
            draw_text(cr, "ARIA" if not is_user else "YOU", bx + pad, y + 6, size=8, color=role_color, bold=True)

            # Message text
            cr.set_source_rgba(*COL_TEXT)
            cr.move_to(bx + pad, y + 20)
            PangoCairo.show_layout(cr, layout)

            # Timestamp
            draw_text(cr, ts, bx + pad, y + bub_h - 14, size=7, color=COL_TEXT_DIM)

            y += bub_h + 8

        # Resize canvas to fit
        needed = max(y + 20, 200)
        if widget.get_size_request()[1] != needed:
            widget.set_size_request(-1, needed)

    # ─────────────────────────────────────────────────────────────────────
    # ANIMATION
    # ─────────────────────────────────────────────────────────────────────

    def _tick(self):
        self.anim_t += 0.016
        self.orb_area.queue_draw()
        return True  # keep running

    # ─────────────────────────────────────────────────────────────────────
    # WINDOW DRAGGING (frameless)
    # ─────────────────────────────────────────────────────────────────────

    def _on_button_press(self, widget, event):
        if event.button == 1 and event.y < 48:
            self.dragging = True
            self.drag_x = event.x
            self.drag_y = event.y

    def _on_button_release(self, widget, event):
        self.dragging = False

    def _on_motion(self, widget, event):
        if self.dragging:
            x, y = self.get_position()
            self.move(int(x + event.x - self.drag_x),
                      int(y + event.y - self.drag_y))

    def _toggle_maximize(self):
        if self.is_maximized():
            self.unmaximize()
        else:
            self.maximize()

    # ─────────────────────────────────────────────────────────────────────
    # MESSAGES
    # ─────────────────────────────────────────────────────────────────────

    def _add_message(self, role, text):
        ts = time.strftime("%H:%M:%S")
        self.messages.append((role, text, ts))
        self.chat_area.queue_draw()
        # Auto-scroll to bottom
        GLib.idle_add(self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        adj = self.chat_scroll.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
        return False

    # ─────────────────────────────────────────────────────────────────────
    # COMMAND DISPATCH
    # ─────────────────────────────────────────────────────────────────────

    def _on_send(self, widget):
        text = self.entry.get_text().strip()
        if not text:
            return
        self.entry.set_text("")
        self._execute_text(text)

    def _execute_text(self, text):
        self._add_message("user", text)
        self._set_state(STATE_PROCESSING)

        def worker():
            result_text = self._run_command(text)
            GLib.idle_add(self._on_result, result_text)

        threading.Thread(target=worker, daemon=True).start()

    def _load_personal_context(self):
        """Load persistent personal context from data/personal_context.json."""
        ctx_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "personal_context.json")
        try:
            with open(ctx_path, "r") as f:
                ctx = json.load(f)
                n_inst = len(ctx.get("instructions", []))
                n_facts = len(ctx.get("learned_facts", []))
                print(f"[✓] Personal context loaded: {n_inst} instructions, {n_facts} facts")
                return ctx
        except FileNotFoundError:
            print("[*] No personal context found, creating default...")
            ctx = {
                "user_profile": {"name": "User", "system": "Linux", "preferences": []},
                "instructions": [],
                "learned_facts": [],
                "conversation_insights": []
            }
            os.makedirs(os.path.dirname(ctx_path), exist_ok=True)
            with open(ctx_path, "w") as f:
                json.dump(ctx, f, indent=2)
            return ctx

    def _save_personal_context(self):
        """Save personal context to disk."""
        ctx_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "personal_context.json")
        try:
            with open(ctx_path, "w") as f:
                json.dump(self.personal_context, f, indent=2)
        except Exception as e:
            print(f"[!] Failed to save personal context: {e}")

    def _add_personal_fact(self, fact: str):
        """Add a learned fact to personal context."""
        if fact not in self.personal_context.get("learned_facts", []):
            self.personal_context.setdefault("learned_facts", []).append(fact)
            self._save_personal_context()
            return True
        return False

    def _add_instruction(self, instruction: str):
        """Add a custom instruction."""
        if instruction not in self.personal_context.get("instructions", []):
            self.personal_context.setdefault("instructions", []).append(instruction)
            self._save_personal_context()
            return True
        return False

    def _build_desktop_prompt(self):
        """Build a desktop-assistant system prompt with real action types from main.py."""
        tools_text = self.tools.get_tools_prompt()

        # Build personal context section
        personal_section = ""
        ctx = self.personal_context
        profile = ctx.get("user_profile", {})
        instructions = ctx.get("instructions", [])
        facts = ctx.get("learned_facts", [])

        if profile.get("name") or instructions or facts:
            personal_section = "\n=== PERSONAL CONTEXT (about the user) ===\n"
            if profile.get("name"):
                personal_section += f"User: {profile['name']}\n"
            if profile.get("system"):
                personal_section += f"System: {profile['system']}\n"
            if instructions:
                personal_section += "\nUser's custom instructions:\n"
                for inst in instructions:
                    personal_section += f"- {inst}\n"
            if facts:
                personal_section += "\nLearned facts about the user:\n"
                for fact in facts[-20:]:  # Last 20 facts
                    personal_section += f"- {fact}\n"
            personal_section += "\nUse this context to personalize your responses. Remember these details.\n"

        return f"""You are ARIA, a JARVIS-like AI desktop assistant on Linux (Ubuntu). You are smart, proactive, and helpful. You control the system via JSON actions.
{personal_section}

ALWAYS respond with exactly ONE valid JSON object.

=== AVAILABLE ACTIONS ===

--- WhatsApp (bridge at localhost:3001) ---
{{"action": "send_message", "recipient": "<name>", "message": "<text>"}}
{{"action": "send_file", "recipient": "<name>", "file_path": "<absolute path>"}}
{{"action": "send_gif", "recipient": "<name>", "query": "<gif search term>"}}
{{"action": "send_sticker", "recipient": "<name>", "file_path": "<image path>"}}
{{"action": "read_whatsapp", "contact": "<optional contact name>"}}

--- Browser ---
{{"action": "browse", "url": "<url>"}}

--- System ---
{{"action": "shell", "command": "<command>"}}
{{\"action\": \"launch\", \"app\": \"<app_name>\"}}
{{"action": "launch", "app": "<app_name>"}}
{{"action": "wallpaper", "query": "<search term>"}}

--- Image Generation (Gemini AI) ---
{{"action": "generate_image", "prompt": "<detailed image description>", "filename": "<optional filename.png>"}}

--- PDF Tools ---
{{"action": "create_pdf", "text": "<content text>", "title": "<optional title>", "filename": "<optional.pdf>"}}
{{"action": "images_to_pdf", "image_paths": ["<path1.png>", "<path2.jpg>"], "filename": "<optional.pdf>"}}
{{"action": "pdf_to_images", "pdf_path": "<path to pdf>"}}
{{"action": "extract_images", "pdf_path": "<path to pdf>"}}

--- Google Calendar ---
{{"action": "calendar_list", "date": "<YYYY-MM-DD or empty for today>"}}
{{"action": "calendar_create", "summary": "<event title>", "start_time": "<HH:MM or YYYY-MM-DD HH:MM>", "end_time": "<optional>", "location": "<optional>"}}

--- Gmail ---
{{\"action\": \"gmail_send\", \"to\": \"<email address>\", \"subject\": \"<subject>\", \"body\": \"<message body>\"}}
{{\"action\": \"gmail_read\", \"max_results\": 5, \"unread_only\": true}}

--- Tools (registered) ---
{tools_text}
{{\"action\": \"tool\", \"tool_name\": \"<name>\", \"tool_args\": {{}}, \"reason\": \"<why>\"}}

--- Conversational ---
{{\"action\": \"reply\", \"message\": \"<your response>\"}}

=== MULTI-STEP TASKS ===
When a request needs multiple steps, use "steps" to chain actions:
{{"action": "steps", "steps": [
  {{"action": "shell", "command": "..."}},
  {{"action": "send_file", "recipient": "...", "file_path": "..."}}
]}}

=== INTELLIGENCE RULES ===
1. THINK about what the user ACTUALLY wants. If they say "create a blank PDF and send it", you need to CREATE it first (with real content, not just touch) then send it.
2. For creating files: use proper commands. For PDFs: python3 -c "from reportlab.lib.pagesizes import letter; ..." or echo text | libreoffice or similar. NEVER just use "touch" for non-empty files.
3. REMEMBER CONTEXT: Look at the conversation history. If the user says "send that to X", figure out what "that" refers to from recent messages.
4. "play a song" / "play music" / "play another song" → use youtube_search tool: {{"action": "tool", "tool_name": "youtube_search", "tool_args": {{"query": "..."}}}}
5. "play X on youtube" → youtube_search tool.
6. Web search / Google / "search for X" → {{"action": "browse", "url": "https://www.google.com/search?q=..."}}
7. WhatsApp: ALWAYS use send_message/send_file/send_gif/send_sticker actions.
8. Use "reply" ONLY for questions, chat, or when no action is needed.
9. NEVER output raw JSON to the user — always pick the right action.
10. Keep reply messages to 2-3 sentences maximum. Be concise like JARVIS. ALWAYS address the user as "sir".
11. NEVER wrap JSON in markdown code blocks.
12. For shell commands that create files, use absolute paths under /home/harsha/.
13. If the user tells you personal info (preferences, facts about themselves), use the "remember" action to save it.
14. For image generation ("generate an image", "create a picture", "draw", "make an image of"), use the "generate_image" action with a detailed, descriptive prompt.

=== REMEMBER (save user facts) ===
When the user shares personal info or preferences:
{{"action": "remember", "fact": "<what to remember>"}}
Examples: "my favorite language is Python", "I use kde plasma", "I prefer dark themes"

=== EXAMPLES (each shows MANY natural phrasings → same action) ===

--- WhatsApp Messaging ---
User: "send hello to Mom on whatsapp" / "msg Mom hello" / "text Mom hi" / "tell Mom hello on whatsapp" / "whatsapp Mom saying hey" / "drop a hi to Mom" / "ping Mom on whatsapp" / "buzz Mom" / "say hi to Mom for me" / "just tell Mom hey" / "message Mom real quick" / "shoot Mom a text saying hello"
{{"action": "send_message", "recipient": "Mom", "message": "hello"}}

User: "forward this file to KRACK" / "send this to KRACK on whatsapp" / "share the file with KRACK" / "pass this file to KRACK" / "give KRACK this file" / "attach this and send to KRACK" / "upload this to KRACK" / "hand this over to KRACK on whatsapp"
{{"action": "send_file", "recipient": "KRACK", "file_path": "<file_path>"}}

User: "read my whatsapp" / "check whatsapp messages" / "any new messages?" / "show my chats" / "what did I miss on whatsapp?" / "unread messages?" / "who texted me?" / "any texts?"
{{"action": "read_whatsapp"}}

--- Music & Media ---
User: "play a song" / "play some music" / "put on some tunes" / "i wanna listen to music" / "play something" / "let's hear some music" / "throw on a song" / "get some music going" / "hit me with a banger" / "jam something" / "play me a track" / "music please" / "can you play music?" / "ARIA play songs"
{{"action": "tool", "tool_name": "youtube_search", "tool_args": {{"query": "popular music"}}, "reason": "Playing music on YouTube"}}

User: "play lofi music" / "put on some lofi" / "i want lofi vibes" / "play chill beats" / "play something relaxing" / "lo-fi please" / "chill music" / "study music" / "put on background music" / "relaxing beats" / "calm music" / "vibes music"
{{"action": "tool", "tool_name": "youtube_search", "tool_args": {{"query": "lofi hip hop music"}}, "reason": "Playing lofi music"}}

User: "play another song" / "next one" / "something else" / "play a different song" / "change the song" / "I'm bored of this" / "not this one" / "different track" / "switch it up" / "play something new" / "another one" / "one more"
{{"action": "tool", "tool_name": "youtube_search", "tool_args": {{"query": "trending songs"}}, "reason": "Playing next song"}}

User: "play Arijit Singh" / "play KGF songs" / "play Telugu songs" / "Bollywood music" / "play Dil Se Re" / "play some Hindi songs"
{{"action": "tool", "tool_name": "youtube_search", "tool_args": {{"query": "<the artist or song>"}}, "reason": "Playing requested music"}}

User: "pause" / "stop the music" / "pause it" / "hold on" / "pause the video" / "shut it for a sec" / "ruk ja" / "stop" / "wait" / "shh" / "quiet now" / "pause kar" / "hold up" / "sshhh" / "enough music" / "stop the video" / "freeze" / "hold it" / "abhi ruk" / "ek sec ruko" / "just pause" / "stop playing"
{{"action": "tool", "tool_name": "media_control", "tool_args": {{"action": "pause"}}, "reason": "Pausing playback"}}

User: "resume" / "play" / "continue" / "unpause" / "carry on" / "start it again" / "chalu kar" / "go on" / "keep playing" / "continue the song" / "back to the music" / "play it again" / "phir se chalu" / "continue playing" / "resume it" / "start again" / "play karo" / "resume the video" / "let it play" / "go ahead" / "play the video" / "start the video"
{{"action": "tool", "tool_name": "media_control", "tool_args": {{"action": "play"}}, "reason": "Resuming playback"}}

User: "next song" / "skip" / "skip this" / "next track" / "I don't like this one" / "agla gaana" / "next" / "skip skip" / "nah next" / "pass" / "boring, next" / "move on" / "next video" / "skip this song" / "agle pe ja" / "next one play karo" / "change it" / "I don't want this"
{{"action": "tool", "tool_name": "media_control", "tool_args": {{"action": "next"}}, "reason": "Skipping to next"}}

User: "previous song" / "go back" / "play the last one" / "previous track" / "rewind to last song" / "pichla gaana" / "the one before" / "back" / "I liked the previous one" / "replay last" / "previous video" / "go to previous" / "peeche ja" / "last waala play karo" / "pichla one" / "before waala"
{{"action": "tool", "tool_name": "media_control", "tool_args": {{"action": "previous"}}, "reason": "Going to previous"}}

User: "mute" / "silence" / "mute it" / "shut the sound" / "turn off audio" / "sound off" / "kill the audio" / "no sound" / "awaaz band kar" / "chup karo" / "sound band" / "mute karo"
{{"action": "tool", "tool_name": "media_control", "tool_args": {{"action": "mute"}}, "reason": "Muting audio"}}

User: "full screen" / "fullscreen" / "make it full screen" / "I want to see the video" / "make it big" / "bigger screen" / "zoom in" / "full screen kar" / "bada karo" / "expand the video" / "maximize the video" / "go full screen" / "play it in full screen" / "watch in full screen" / "poora screen" / "full screen mode" / "enlarge" / "full size" / "I want to watch it properly"
{{"action": "tool", "tool_name": "media_control", "tool_args": {{"action": "fullscreen"}}, "reason": "Toggling fullscreen"}}

User: "fast forward" / "skip ahead" / "go forward" / "aage badho" / "jump ahead" / "forward 10 seconds" / "skip 10 sec" / "forward" / "aage" / "thoda aage" / "forward karo"
{{"action": "tool", "tool_name": "media_control", "tool_args": {{"action": "forward"}}, "reason": "Skipping forward"}}

User: "rewind" / "go back a bit" / "rewind it" / "peeche karo" / "back 10 seconds" / "go back 10 sec" / "thoda peeche" / "rewind back" / "peeche ja thoda" / "rewind karo"
{{"action": "tool", "tool_name": "media_control", "tool_args": {{"action": "rewind"}}, "reason": "Rewinding"}}

--- Volume & System ---
User: "set volume to max" / "max volume" / "turn it up to full" / "volume 100" / "crank it up" / "louder" / "full volume" / "blast it" / "pump up the volume" / "I can't hear it" / "make it louder" / "volume up" / "increase volume"
{{"action": "tool", "tool_name": "set_volume", "tool_args": {{"level": 100}}, "reason": "Setting volume to maximum"}}

User: "lower the volume" / "turn it down" / "quieter" / "volume down" / "reduce volume" / "too loud" / "softer" / "keep it low" / "decrease volume" / "bring it down" / "not so loud" / "tone it down"
{{"action": "tool", "tool_name": "set_volume", "tool_args": {{"level": 40}}, "reason": "Lowering volume"}}

User: "set volume to 50" / "volume 50" / "half volume" / "medium volume" / "volume at 50 percent"
{{"action": "tool", "tool_name": "set_volume", "tool_args": {{"level": 50}}, "reason": "Setting volume to 50"}}

User: "increase brightness" / "brighter" / "screen too dark" / "turn up brightness" / "more brightness" / "I can't see" / "brighten up"
{{"action": "tool", "tool_name": "set_brightness", "tool_args": {{"level": 80}}, "reason": "Increasing brightness"}}

User: "dim the screen" / "lower brightness" / "too bright" / "reduce brightness" / "darken the screen" / "easy on the eyes"
{{"action": "tool", "tool_name": "set_brightness", "tool_args": {{"level": 30}}, "reason": "Dimming screen"}}

--- App Launching ---
User: "open file manager" / "open files" / "show my files" / "file explorer" / "open nautilus" / "browse files" / "where are my files?"
{{"action": "launch", "app": "nautilus"}}

User: "open terminal" / "launch terminal" / "I need a terminal" / "give me a console" / "shell please" / "command line"
{{"action": "launch", "app": "gnome-terminal"}}

User: "open browser" / "launch firefox" / "open firefox" / "I need the browser" / "internet please" / "go online"
{{"action": "launch", "app": "firefox"}}

User: "open settings" / "system settings" / "preferences" / "go to settings" / "I need to change settings"
{{"action": "launch", "app": "gnome-control-center"}}

User: "open calculator" / "I need a calculator" / "calc" / "launch calculator"
{{"action": "launch", "app": "gnome-calculator"}}

--- Web & Search ---
User: "search for cat images" / "look up cat photos" / "find cat pictures" / "google cat images" / "search cat pics" / "show me cats" / "I wanna see cat photos" / "search the web for cats"
{{"action": "browse", "url": "https://www.google.com/search?q=cat+images"}}

User: "open youtube" / "go to youtube" / "take me to youtube" / "launch youtube" / "youtube please" / "I wanna watch something"
{{"action": "browse", "url": "https://www.youtube.com"}}

User: "open google" / "go to google" / "google.com" / "take me to google" / "search engine"
{{"action": "browse", "url": "https://www.google.com"}}

User: "open github" / "go to github" / "take me to github" / "github.com"
{{"action": "browse", "url": "https://www.github.com"}}

User: "what's the weather?" / "weather today" / "is it gonna rain?" / "how's the weather?" / "temperature outside"
{{"action": "browse", "url": "https://www.google.com/search?q=weather+today"}}

--- PDF Operations ---
User: "create a PDF with my notes about AI" / "make a PDF about AI" / "write up a PDF on AI" / "generate a PDF document about AI" / "I need a PDF with some text" / "make me a PDF" / "create a document" / "PDF banana hai ek" / "type up a PDF for me"
{{"action": "create_pdf", "text": "Artificial Intelligence notes...", "title": "AI Notes"}}

User: "create a blank PDF" / "make an empty PDF" / "just give me a blank PDF" / "fresh PDF" / "new PDF"
{{"action": "create_pdf", "text": " ", "title": "Blank Document"}}

User: "convert this image to PDF" / "make a PDF from this photo" / "turn these images into a PDF" / "put these pictures in a PDF" / "images to PDF" / "photo to PDF please" / "combine photos into PDF" / "PDF from pictures"
{{"action": "images_to_pdf", "image_paths": ["<path>"], "filename": "images.pdf"}}

User: "convert this PDF to images" / "turn PDF pages into pictures" / "extract pages as images from this PDF" / "PDF to PNG" / "PDF to images" / "save PDF pages as photos" / "I want pictures of each page"
{{"action": "pdf_to_images", "pdf_path": "<path>"}}

User: "extract images from this PDF" / "pull out the pictures from this PDF" / "get the images inside this PDF" / "rip images from the PDF" / "take out all images from this PDF" / "what images are in this PDF?" / "grab the photos from the PDF"
{{"action": "extract_images", "pdf_path": "<path>"}}

--- Image Generation ---
User: "generate an image of a sunset" / "make me a picture of a sunset" / "draw a sunset" / "create an image of sunset over mountains" / "I want a sunset picture" / "can you make a sunset image?" / "paint me a sunset" / "design a sunset wallpaper" / "make a cool sunset pic"
{{"action": "generate_image", "prompt": "A breathtaking sunset over snow-capped mountains with warm golden and orange hues reflecting on a crystal clear lake in the foreground, photorealistic style"}}

User: "draw a cat wearing a top hat" / "make a cat with a hat" / "generate a fancy cat picture" / "create an image of a cat" / "I want a picture of a cat in a hat" / "cat with hat image"
{{"action": "generate_image", "prompt": "A cute fluffy cat wearing an elegant black top hat, sitting on a velvet cushion, detailed digital art illustration"}}

User: "make my wallpaper a nature scene" / "set wallpaper to something cool" / "change wallpaper" / "new wallpaper please" / "wallpaper badal do" / "put a nice background" / "I want a cool desktop background"
{{"action": "wallpaper", "query": "nature wallpaper 4K"}}

--- Calendar ---
User: "what's on my schedule?" / "any meetings today?" / "show my calendar" / "what do I have today?" / "am I free today?" / "kya hai aaj schedule mein?" / "busy hu kya?" / "any events?" / "what's happening today?" / "plans for today?" / "do I have anything?"
{{"action": "calendar_list"}}

User: "add a meeting at 3pm" / "schedule a call at 3" / "put a meeting on my calendar at 3pm" / "remind me about the meeting at 3" / "I have a meeting at 3" / "book 3pm for a meeting" / "3 baje meeting hai" / "3pm meeting set kar" / "create an event at 3"
{{"action": "calendar_create", "summary": "Meeting", "start_time": "15:00"}}

--- Email ---
User: "read my emails" / "check my inbox" / "any new emails?" / "show my mail" / "do I have any emails?" / "koi mail aaya?" / "inbox check kar" / "read inbox" / "what's in my email?" / "unread emails?"
{{"action": "gmail_read", "max_results": 5, "unread_only": true}}

User: "send an email to john@example.com" / "email John saying hello" / "compose an email to John" / "mail kar John ko" / "write an email" / "send mail" / "draft an email to John"
{{"action": "gmail_send", "to": "john@example.com", "subject": "Hello", "body": "Hello John!"}}

--- System Info ---
User: "what's my battery?" / "battery level" / "how much charge?" / "battery status" / "am I charging?" / "kitna battery hai?"
{{"action": "tool", "tool_name": "battery_status", "tool_args": {{}}, "reason": "Checking battery"}}

User: "how much RAM am I using?" / "system status" / "CPU usage" / "memory usage" / "how's my system doing?" / "system info" / "check resources" / "kitna RAM use ho raha?"
{{"action": "tool", "tool_name": "system_info", "tool_args": {{}}, "reason": "Checking system resources"}}

User: "take a screenshot" / "screenshot" / "capture my screen" / "ss le lo" / "screen capture" / "snap the screen" / "screengrab"
{{"action": "tool", "tool_name": "screenshot", "tool_args": {{}}, "reason": "Taking screenshot"}}

--- File Management ---
User: "list files in Downloads" / "show files in Downloads" / "what's in my Downloads?" / "ls Downloads" / "files in downloads folder" / "kya hai Downloads mein?"
{{"action": "shell", "command": "ls -la /home/harsha/Downloads"}}

User: "how much disk space do I have?" / "check storage" / "disk usage" / "am I running out of space?" / "space kitna hai?"
{{"action": "shell", "command": "df -h / /home"}}

--- Conversational ---
User: "what is machine learning?" / "explain ML to me" / "tell me about machine learning" / "what's ML?" / "how does machine learning work?" / "ML kya hota hai?" / "define machine learning"
{{"action": "reply", "message": "Machine learning is a subset of artificial intelligence where systems learn patterns from data to make predictions without being explicitly programmed, sir."}}

User: "who are you?" / "what can you do?" / "introduce yourself" / "what are you?" / "tu kaun hai?" / "tell me about yourself" / "what's your name?" / "your capabilities?"
{{"action": "reply", "message": "I am ARIA, your AI desktop assistant, sir. I can control your system, browse the web, send messages on WhatsApp, play music, generate images, create PDFs, manage your calendar, and much more."}}

User: "thank you" / "thanks" / "good job" / "nice one" / "well done" / "shukriya" / "perfect" / "awesome work" / "you're the best" / "nailed it"
{{"action": "reply", "message": "Happy to help, sir. Let me know if there's anything else."}}

User: "good morning" / "morning" / "hey ARIA" / "hi" / "hello" / "what's up" / "sup" / "yo"
{{"action": "reply", "message": "Good day, sir. All systems are online. How can I assist you?"}}

User: "good night" / "I'm going to sleep" / "bye" / "see ya" / "chal soja" / "shutting down for the night"
{{"action": "reply", "message": "Good night, sir. I'll be here whenever you need me."}}

--- Remember / Memory ---
User: "remember that my favorite language is Python" / "note that I prefer dark mode" / "keep in mind I use KDE" / "yaad rakh Python pasand hai"
{{"action": "remember", "fact": "favorite programming language is Python"}}

--- Multi-Step Tasks ---
User: "extract images from ~/doc.pdf and send the first one to KRACK on whatsapp" / "pull images from the PDF and whatsapp them to KRACK" / "PDF se images nikaal ke KRACK ko bhej" / "get the pictures out of this PDF and share with KRACK"
{{"action": "steps", "steps": [
  {{"action": "extract_images", "pdf_path": "/home/harsha/doc.pdf"}},
  {{"action": "send_file", "recipient": "KRACK", "file_path": "/home/harsha/Documents/aria_pdfs/doc_images/doc_img1.png"}}
]}}

User: "take a screenshot and send it to Mom on whatsapp" / "screenshot my screen and forward it to Mom" / "capture screen and send to Mom" / "ss le ke Mom ko bhej de" / "snap my screen and whatsapp to Mom"
{{"action": "steps", "steps": [
  {{"action": "tool", "tool_name": "screenshot", "tool_args": {{}}, "reason": "Taking screenshot"}},
  {{"action": "send_file", "recipient": "KRACK", "file_path": "/tmp/screenshot.png"}}
]}}

User: "create a picture and send it to KRACK on whatsapp" / "generate an image and share it with KRACK" / "make something cool and send to KRACK" / "ek photo bana ke KRACK ko bhej"
{{"action": "steps", "steps": [
  {{"action": "generate_image", "prompt": "<detailed description>", "filename": "generated.png"}},
  {{"action": "send_file", "recipient": "KRACK", "file_path": "/home/harsha/Pictures/aria_generated/generated.png"}}
]}}

User: "create a blank PDF and send it to KRACK on whatsapp" / "make an empty PDF and forward to KRACK" / "blank PDF bana ke KRACK ko de do"
{{"action": "steps", "steps": [
  {{"action": "create_pdf", "text": " ", "title": "Blank Document", "filename": "blank.pdf"}},
  {{"action": "send_file", "recipient": "KRACK", "file_path": "/home/harsha/Documents/aria_pdfs/blank.pdf"}}
]}}

User: "generate a sunset wallpaper and set it as my desktop background" / "create a cool wallpaper and apply it" / "make me a wallpaper and set it"
{{"action": "steps", "steps": [
  {{"action": "generate_image", "prompt": "Ultra wide 4K sunset wallpaper with mountains and ocean, vibrant colors", "filename": "custom_wallpaper.png"}},
  {{"action": "shell", "command": "gsettings set org.gnome.desktop.background picture-uri 'file:///home/harsha/Pictures/aria_generated/custom_wallpaper.png'"}}
]}}
"""

    def _run_command(self, text):
        # ── Fast-path: Reflex patterns for instant system commands ──
        resolved = resolve_command(text)
        if resolved:
            tool_name, kwargs = resolved
            try:
                result = self.tools.execute(tool_name, **kwargs)
                return self._format_tool_result(tool_name, result, "⚡")
            except Exception as e:
                return f"❌ Error: {e}"

        # ── Personal context commands ──
        lower = text.lower().strip()

        # "remember that ..." → save a fact
        if lower.startswith("remember that ") or lower.startswith("remember "):
            fact = text.split(" ", 1)[1] if lower.startswith("remember ") else text[len("remember that "):]
            fact = fact.strip()
            if fact:
                if self._add_personal_fact(fact):
                    return f"🧠 ✅ I'll remember that: {fact}"
                else:
                    return f"🧠 I already know that."

        # "add instruction ..." → save a custom instruction
        if lower.startswith("add instruction "):
            instruction = text[len("add instruction "):].strip()
            if instruction:
                if self._add_instruction(instruction):
                    return f"🧠 ✅ Instruction added: {instruction}"
                else:
                    return f"🧠 That instruction already exists."

        # "show my context" / "my instructions" → display personal context
        if lower in ("show my context", "my context", "my instructions", "show instructions", "personal context"):
            ctx = self.personal_context
            parts = ["📋 **Your Personal Context:**"]
            profile = ctx.get("user_profile", {})
            if profile.get("name"):
                parts.append(f"\n**Name:** {profile['name']}")
            if profile.get("system"):
                parts.append(f"**System:** {profile['system']}")
            instructions = ctx.get("instructions", [])
            if instructions:
                parts.append("\n**Instructions:**")
                for i, inst in enumerate(instructions, 1):
                    parts.append(f"  {i}. {inst}")
            facts = ctx.get("learned_facts", [])
            if facts:
                parts.append(f"\n**Learned Facts ({len(facts)}):**")
                for i, fact in enumerate(facts[-10:], 1):
                    parts.append(f"  {i}. {fact}")
                if len(facts) > 10:
                    parts.append(f"  ... and {len(facts) - 10} more")
            return "\n".join(parts)

        # "forget ..." → remove a fact
        if lower.startswith("forget "):
            target = text[len("forget "):].strip().lower()
            facts = self.personal_context.get("learned_facts", [])
            removed = [f for f in facts if target in f.lower()]
            if removed:
                for f in removed:
                    facts.remove(f)
                self._save_personal_context()
                return f"🧠 ✅ Forgot: {', '.join(removed)}"
            return "🧠 I don't have any facts matching that."

        # ── Primary: DeepSeek Brain with full action dispatch ──
        return self._ask_brain(text)

    def _bridge_request(self, endpoint, payload, timeout=30):
        """POST to WhatsApp bridge with auto-reconnect on detached frame.
        Returns (data, error_string). On success error_string is None."""
        import requests as req
        import time as _time

        BRIDGE = "http://localhost:3001"

        for attempt in range(2):
            try:
                r = req.post(f"{BRIDGE}{endpoint}", json=payload, timeout=timeout)
                data = r.json()
                if data.get("success"):
                    return data, None
                err = data.get("error", "Unknown error")

                # Detached frame → trigger reconnect and retry
                if "detached Frame" in err and attempt == 0:
                    print("  🔄 Bridge session lost, triggering reconnect...")
                    try:
                        req.post(f"{BRIDGE}/restart", timeout=5)
                    except Exception:
                        pass
                    # Wait for bridge to reconnect (up to 30s)
                    for _ in range(30):
                        _time.sleep(1)
                        try:
                            st = req.get(f"{BRIDGE}/status", timeout=2).json()
                            if st.get("ready") and not st.get("reconnecting"):
                                print("  ✅ Bridge reconnected, retrying...")
                                break
                        except Exception:
                            pass
                    continue  # retry

                return data, err

            except Exception as e:
                if attempt == 0 and "Connection refused" in str(e):
                    # Bridge might not be running — try starting it
                    print("  🔄 Bridge not reachable, attempting start...")
                    self._start_whatsapp_bridge()
                    continue
                return None, str(e)

        return None, "Bridge reconnect failed after retry"

    def _ask_brain(self, text):
        """Send to Ollama and dispatch the real action types from main.py."""
        try:
            import requests as req

            # Build messages with context (expanded window for better memory)
            messages = [{"role": "system", "content": self._build_desktop_prompt()}]
            for role, msg, ts in self.messages[-12:]:
                r = "user" if role == "user" else "assistant"
                messages.append({"role": r, "content": msg})
            messages.append({"role": "user", "content": text})

            payload = {
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1, "num_ctx": 8192}
            }

            resp = req.post(OLLAMA_URL, json=payload, timeout=120)
            if resp.status_code != 200:
                return f"❌ Ollama error: HTTP {resp.status_code}"

            content = resp.json().get("message", {}).get("content", "")
            if not content:
                return "⚠️ Brain returned empty response."

            # Parse JSON
            try:
                decision = json.loads(content.strip())
            except json.JSONDecodeError:
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    try:
                        decision = json.loads(match.group())
                    except json.JSONDecodeError:
                        return f"🧠 {content.strip()}"
                else:
                    return f"🧠 {content.strip()}"

            action = decision.get("action", "").lower()

            # ── Multi-step: execute actions sequentially ──
            if action == "steps":
                steps = decision.get("steps", [])
                if not steps:
                    return "🧠 No steps provided."
                results = []
                for i, step in enumerate(steps):
                    step_result = self._execute_single_action(step)
                    results.append(step_result)
                    # If a step fails, stop the chain
                    if step_result.startswith("❌"):
                        break
                return "\n".join(results)

            return self._execute_single_action(decision)

        except Exception as e:
            print(f"[!] Brain error: {e}")
            import traceback
            traceback.print_exc()
            return f"❌ Brain error: {e}"

    def _execute_single_action(self, decision):
        """Execute a single action from the brain's JSON decision."""
        try:
            import requests as req
            action = decision.get("action", "").lower()

            # ── WhatsApp: send_message (bridge:3001) ──
            if action in ("send_message", "send_whatsapp"):
                recipient = decision.get("recipient", decision.get("contact", ""))
                msg = decision.get("message", "")
                print(f"  🧠 Sending '{msg}' to '{recipient}' via WhatsApp bridge...")
                payload = {"searchName": recipient, "message": msg}
                data, err = self._bridge_request("/send", payload)
                if err:
                    return f"❌ WhatsApp: {err}"
                return f"🧠 ✅ Message sent to {recipient}"

            # ── WhatsApp: send_file (bridge:3001) ──
            elif action == "send_file":
                recipient = decision.get("recipient", decision.get("contact", ""))
                file_path = decision.get("file_path", decision.get("path", ""))
                caption = decision.get("caption", decision.get("message", ""))
                print(f"  🧠 Sending file '{file_path}' to '{recipient}'...")
                payload = {"searchName": recipient, "mediaPath": file_path}
                if caption:
                    payload["message"] = caption
                data, err = self._bridge_request("/send", payload, timeout=60)
                if err:
                    return f"❌ WhatsApp file: {err}"
                return f"🧠 ✅ File sent to {recipient}"

            # ── WhatsApp: send_gif (bridge:3001/send-gif) ──
            elif action == "send_gif":
                recipient = decision.get("recipient", decision.get("contact", ""))
                query = decision.get("query", "funny")
                print(f"  🧠 Sending '{query}' GIF to '{recipient}'...")
                payload = {"searchName": recipient, "query": query}
                data, err = self._bridge_request("/send-gif", payload)
                if err:
                    return f"❌ WhatsApp GIF: {err}"
                return f"🧠 ✅ GIF sent to {recipient}"

            # ── WhatsApp: send_sticker (bridge:3001 with sendAsSticker) ──
            elif action == "send_sticker":
                recipient = decision.get("recipient", decision.get("contact", ""))
                file_path = decision.get("file_path", decision.get("path", ""))
                print(f"  🧠 Sending sticker '{file_path}' to '{recipient}'...")
                payload = {"searchName": recipient, "mediaPath": file_path, "sendAsSticker": True}
                data, err = self._bridge_request("/send", payload)
                if err:
                    return f"❌ WhatsApp sticker: {err}"
                return f"🧠 ✅ Sticker sent to {recipient}"

            # ── WhatsApp: read_whatsapp (bridge API) ──
            elif action == "read_whatsapp":
                contact = decision.get("contact", decision.get("recipient", ""))
                print(f"  🧠 Reading WhatsApp messages{' from ' + contact if contact else ''}...")
                try:
                    import requests as req
                    BRIDGE = "http://localhost:3001"

                    # Check bridge status first
                    try:
                        status = req.get(f"{BRIDGE}/status", timeout=3).json()
                        if not status.get("ready"):
                            return "❌ WhatsApp bridge is not connected yet. Please scan the QR code first."
                    except Exception:
                        return "❌ WhatsApp bridge is not running. Please restart ARIA."

                    if contact:
                        # Step 1: Search for the contact to get chatId
                        search_resp = req.post(f"{BRIDGE}/search", json={"query": contact}, timeout=10)
                        search_data = search_resp.json()
                        matches = search_data.get("matches", [])
                        if not matches:
                            return f"🧠 📱 No chat found for '{contact}', sir."
                        chat_id = matches[0]["id"]
                        chat_name = matches[0].get("name", contact)

                        # Step 2: Get messages from that chat
                        msg_resp = req.get(f"{BRIDGE}/messages/{chat_id}", timeout=15)
                        msg_data = msg_resp.json()
                        messages = msg_data.get("messages", [])

                        if not messages:
                            return f"🧠 📱 No recent messages from {chat_name}, sir."

                        lines = [f"🧠 📱 Messages from {chat_name}:"]
                        for msg in messages[-5:]:
                            sender = "You" if msg.get("fromMe") else chat_name
                            body = msg.get("body", "")
                            has_media = msg.get("hasMedia", False)
                            msg_type = msg.get("type", "chat")

                            if has_media or msg_type == "image":
                                lines.append(f"  📷 {sender}: [Image] {body or ''}")
                            elif msg_type == "sticker":
                                lines.append(f"  🎭 {sender}: [Sticker]")
                            elif msg_type == "video":
                                lines.append(f"  🎬 {sender}: [Video] {body or ''}")
                            elif msg_type == "audio" or msg_type == "ptt":
                                lines.append(f"  🎵 {sender}: [Voice Note]")
                            elif msg_type == "document":
                                lines.append(f"  📄 {sender}: [Document] {body or ''}")
                            else:
                                lines.append(f"  💬 {sender}: {body[:200]}")
                        return "\n".join(lines)

                    else:
                        # No contact specified — show recent chats with unread
                        chats_resp = req.get(f"{BRIDGE}/chats", timeout=10)
                        chats_data = chats_resp.json()
                        chats = chats_data.get("chats", [])

                        unread = [c for c in chats if c.get("unreadCount", 0) > 0]
                        if not unread:
                            return "🧠 📱 No unread messages, sir. All caught up!"

                        lines = ["🧠 📱 Unread chats:"]
                        for chat in unread[:8]:
                            name = chat.get("name", "Unknown")
                            count = chat.get("unreadCount", 0)
                            lines.append(f"  💬 {name}: {count} unread")
                        return "\n".join(lines)

                except Exception as e:
                    return f"❌ Read WhatsApp failed: {e}"

            # ── Browse: open URL ──
            elif action == "browse":
                url = decision.get("url", "")
                if url:
                    if not url.startswith("http"):
                        url = "https://" + url
                    subprocess.Popen(["xdg-open", url],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    return f"🧠 Opening: {url}"
                return "🧠 No URL provided."

            # ── Shell: execute command ──
            elif action == "shell":
                command = decision.get("command", "")
                if not command:
                    return "🧠 No command provided."
                # Safety check
                dangerous = ["rm -rf /", "rm -rf /*", ":(){ :|:& };:", "mkfs", "dd if=", "> /dev/sd"]
                if any(d in command for d in dangerous):
                    return "❌ Blocked: Dangerous command detected!"
                print(f"  🧠 Shell: {command}")
                try:
                    result = subprocess.run(
                        command, shell=True, capture_output=True,
                        text=True, timeout=30, cwd=os.path.expanduser("~")
                    )
                    output = result.stdout.strip() or result.stderr.strip() or "(no output)"
                    if len(output) > 500:
                        output = output[:497] + "…"
                    status = "✅" if result.returncode == 0 else f"⚠️ exit {result.returncode}"
                    return f"🧠 {status} $ {command}\n{output}"
                except subprocess.TimeoutExpired:
                    return f"❌ Command timed out: {command}"
                except Exception as e:
                    return f"❌ Shell error: {e}"

            # ── Launch: open application ──
            elif action == "launch":
                app = decision.get("app", "")
                if app:
                    print(f"  🧠 Launching: {app}")
                    subprocess.Popen([app], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    return f"🧠 Launched: {app}"
                return "🧠 No app specified."

            # ── Wallpaper: set desktop wallpaper ──
            elif action == "wallpaper":
                query = decision.get("query", "wallpaper")
                print(f"  🧠 Setting wallpaper: {query}")
                try:
                    subprocess.run(
                        ["python3", "src/workflows/cat_wallpaper.py", "--query", query],
                        timeout=30, cwd="/home/harsha/Downloads/mightbe_done"
                    )
                    return f"🧠 ✅ Wallpaper set: {query}"
                except Exception as e:
                    return f"❌ Wallpaper failed: {e}"

            # ── Google Calendar: list events ──
            elif action == "calendar_list":
                date = decision.get("date", None)
                print(f"  🧠 Listing calendar events for: {date or 'today'}")
                try:
                    from src.tools.google_calendar import list_events
                    result = list_events(max_results=10, date=date)
                    if result.get("success"):
                        events = result.get("events", [])
                        if not events:
                            return "🧠 📅 No events scheduled for today, sir."
                        lines = ["🧠 📅 Your schedule:"]
                        for e in events:
                            lines.append(f"  • {e['start'][-8:-3] if 'T' in str(e['start']) else e['start']} — {e['summary']}")
                        return "\n".join(lines)
                    return f"❌ Calendar: {result.get('error', 'Unknown error')}"
                except Exception as e:
                    return f"❌ Calendar error: {e}"

            # ── Google Calendar: create event ──
            elif action == "calendar_create":
                summary = decision.get("summary", "")
                start_time = decision.get("start_time", "")
                end_time = decision.get("end_time", None)
                location = decision.get("location", "")
                description = decision.get("description", "")
                if not summary or not start_time:
                    return "🧠 Need at least event title and start time."
                print(f"  🧠 Creating calendar event: {summary} at {start_time}")
                try:
                    from src.tools.google_calendar import create_event
                    result = create_event(summary, start_time, end_time, description, location)
                    if result.get("success"):
                        return f"🧠 ✅ Event '{summary}' created at {start_time}, sir."
                    return f"❌ Calendar: {result.get('error', 'Unknown error')}"
                except Exception as e:
                    return f"❌ Calendar error: {e}"

            # ── Gmail: send email ──
            elif action == "gmail_send":
                to = decision.get("to", "")
                subject = decision.get("subject", "")
                body = decision.get("body", "")
                attachment = decision.get("attachment", None)
                if not to:
                    return "🧠 No recipient email specified."
                print(f"  🧠 Sending email to: {to}")
                try:
                    from src.tools.google_gmail import send_email
                    result = send_email(to, subject, body, attachment)
                    if result.get("success"):
                        return f"🧠 ✅ Email sent to {to}, sir."
                    return f"❌ Gmail: {result.get('error', 'Unknown error')}"
                except Exception as e:
                    return f"❌ Gmail error: {e}"

            # ── Gmail: read emails ──
            elif action == "gmail_read":
                max_results = decision.get("max_results", 5)
                unread_only = decision.get("unread_only", True)
                print(f"  🧠 Reading {'unread' if unread_only else 'all'} emails...")
                try:
                    from src.tools.google_gmail import read_emails
                    result = read_emails(max_results, unread_only)
                    if result.get("success"):
                        emails = result.get("emails", [])
                        if not emails:
                            return "🧠 📧 No unread emails, sir." if unread_only else "🧠 📧 Inbox is empty, sir."
                        lines = ["🧠 📧 Your emails:"]
                        for e in emails:
                            sender = e['from'].split('<')[0].strip() if '<' in e['from'] else e['from']
                            lines.append(f"  • **{sender}** — {e['subject']}")
                            if e.get('snippet'):
                                lines.append(f"    {e['snippet'][:80]}...")
                        return "\n".join(lines)
                    return f"❌ Gmail: {result.get('error', 'Unknown error')}"
                except Exception as e:
                    return f"❌ Gmail error: {e}"

            # ── PDF: create PDF from text ──
            elif action == "create_pdf":
                text = decision.get("text", "")
                title = decision.get("title", "")
                filename = decision.get("filename", None)
                if not text:
                    return "🧠 No text content provided for the PDF."
                print(f"  🧠 Creating PDF: {title or 'document'}")
                try:
                    from src.tools.pdf_tools import create_pdf
                    result = create_pdf(text, title=title, filename=filename)
                    if result.get("success"):
                        return f"🧠 ✅ PDF created at {result['path']}, sir."
                    return f"❌ PDF: {result.get('error')}"
                except Exception as e:
                    return f"❌ PDF error: {e}"

            # ── PDF: images to PDF ──
            elif action == "images_to_pdf":
                image_paths = decision.get("image_paths", [])
                filename = decision.get("filename", None)
                if not image_paths:
                    return "🧠 No images provided."
                print(f"  🧠 Converting {len(image_paths)} image(s) to PDF")
                try:
                    from src.tools.pdf_tools import images_to_pdf
                    result = images_to_pdf(image_paths, filename=filename)
                    if result.get("success"):
                        return f"🧠 ✅ {result['message']}"
                    return f"❌ PDF: {result.get('error')}"
                except Exception as e:
                    return f"❌ PDF error: {e}"

            # ── PDF: convert PDF pages to images ──
            elif action == "pdf_to_images":
                pdf_path = decision.get("pdf_path", "")
                if not pdf_path:
                    return "🧠 No PDF path provided."
                print(f"  🧠 Converting PDF to images: {pdf_path}")
                try:
                    from src.tools.pdf_tools import pdf_to_images
                    result = pdf_to_images(pdf_path)
                    if result.get("success"):
                        return f"🧠 ✅ {result['message']}"
                    return f"❌ PDF: {result.get('error')}"
                except Exception as e:
                    return f"❌ PDF error: {e}"

            # ── PDF: extract embedded images from PDF ──
            elif action == "extract_images":
                pdf_path = decision.get("pdf_path", "")
                if not pdf_path:
                    return "🧠 No PDF path provided."
                print(f"  🧠 Extracting images from PDF: {pdf_path}")
                try:
                    from src.tools.pdf_tools import extract_images_from_pdf
                    result = extract_images_from_pdf(pdf_path)
                    if result.get("success"):
                        images = result.get("images", [])
                        if not images:
                            return "🧠 No embedded images found in this PDF, sir."
                        return f"🧠 ✅ Extracted {len(images)} image(s) to {os.path.dirname(images[0])}, sir."
                    return f"❌ PDF: {result.get('error')}"
                except Exception as e:
                    return f"❌ PDF error: {e}"

            # ── Generate Image: Gemini AI image generation ──
            elif action == "generate_image":
                prompt = decision.get("prompt", "")
                filename = decision.get("filename", None)
                if not prompt:
                    return "🧠 No image description provided."
                print(f"  🧠 Generating image: {prompt[:60]}...")
                try:
                    from src.tools.image_gen import generate_image
                    result = generate_image(prompt, filename=filename)
                    if result.get("success"):
                        path = result.get("path", "")
                        # Auto-open the generated image
                        subprocess.Popen(
                            ["xdg-open", path],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                        return f"🧠 ✅ Image generated!\n🖼️ {path}"
                    else:
                        return f"❌ Image generation failed: {result.get('error', 'Unknown error')}"
                except Exception as e:
                    return f"❌ Image generation error: {e}"

            # ── Tool: dispatch to AutomationTools registry ──
            elif action == "tool":
                tool_name = decision.get("tool_name", "")
                tool_args = decision.get("tool_args", {})
                reason = decision.get("reason", "")
                if reason:
                    print(f"  🧠 {reason}")
                result = self.tools.execute(tool_name, **tool_args)
                return self._format_tool_result(tool_name, result, "🧠",
                                                 explanation=reason)

            # ── Reply: conversational response ──
            elif action == "reply":
                message = decision.get("message", "")
                return f"🧠 {message}" if message else "🧠 (empty response)"

            # ── Done: task complete ──
            elif action == "done":
                reason = decision.get("reason", decision.get("summary", "Done."))
                return f"🧠 {reason}"

            # ── Remember: save a personal fact ──
            elif action == "remember":
                fact = decision.get("fact", "")
                if fact:
                    self._add_personal_fact(fact)
                    message = decision.get("message", f"I'll remember that: {fact}")
                    return f"🧠 ✅ {message}"
                return "🧠 Nothing to remember."

            # ── Fallback: show raw ──
            else:
                msg = decision.get("message", decision.get("reason", json.dumps(decision)))
                return f"🧠 {msg}"

        except Exception as e:
            print(f"[!] Action error: {e}")
            return f"❌ Action error: {e}"

    def _format_tool_result(self, tool_name, result, prefix="⚡", explanation=""):
        """Format a tool execution result as a clean JARVIS-style message."""
        if not result.get("success"):
            return f"❌ {tool_name}: {result.get('error', 'Unknown error')}"

        # ── Clean JARVIS-style messages for known tools ──
        if tool_name == "set_brightness":
            level = result.get("level", result.get("brightness", "?"))
            return f"🧠 ✅ Brightness set to {level}%, sir."
        elif tool_name == "set_volume":
            level = result.get("level", result.get("volume", "?"))
            return f"🧠 ✅ Volume set to {level}, sir."
        elif tool_name == "screenshot":
            path = result.get("path", result.get("file", ""))
            return f"🧠 ✅ Screenshot saved, sir." + (f"\n🖼️ {path}" if path else "")
        elif tool_name == "battery_status":
            pct = result.get("percent", result.get("level", "?"))
            charging = result.get("charging", result.get("plugged", False))
            status = "charging" if charging else "on battery"
            return f"🧠 🔋 Battery at {pct}%, {status}, sir."
        elif tool_name == "system_info":
            cpu = result.get("cpu_percent", "?")
            ram = result.get("ram_percent", result.get("memory_percent", "?"))
            return f"🧠 💻 CPU: {cpu}%, RAM: {ram}%, sir."
        elif tool_name == "youtube_search":
            title = result.get("title", result.get("query", "your selection"))
            return f"🧠 ▶️ Playing {title} on YouTube, sir."
        elif tool_name == "media_control":
            cmd = result.get("command", "done")
            action_names = {
                "pause": "Playback paused",
                "play": "Playback resumed",
                "play-pause": "Playback toggled",
                "next": "Skipped to next",
                "previous": "Back to previous",
                "mute": "Audio muted",
                "stop": "Playback stopped",
                "fullscreen": "Fullscreen toggled",
                "volume-up": "Volume up",
                "volume-down": "Volume down",
                "forward": "Skipped forward",
                "rewind": "Rewound",
            }
            msg = action_names.get(cmd, cmd.replace('-', ' ').title())
            return f"🧠 ✅ {msg}, sir."
        elif tool_name == "run_command" or tool_name == "shell":
            output = result.get("output", result.get("stdout", "Done."))
            if len(str(output)) > 300:
                output = str(output)[:297] + "…"
            return f"🧠 ✅ {output}"
        elif tool_name == "open_app" or tool_name == "launch":
            app = result.get("app", "Application")
            return f"🧠 ✅ {app} launched, sir."
        elif tool_name == "wallpaper":
            return "🧠 ✅ Wallpaper updated, sir."
        elif tool_name == "list_files":
            files = result.get("files", [])
            return f"🧠 📁 Found {len(files)} item(s), sir."
        else:
            # Generic fallback — still clean
            parts = []
            for k, v in result.items():
                if k in ("success", "action"):
                    continue
                val = str(v)
                if len(val) > 200:
                    val = val[:197] + "…"
                parts.append(f"{k}: {val}")
            detail = "\n".join(parts) if parts else "Done, sir."
            return f"🧠 ✅ {detail}"

    def _on_result(self, text):
        self._add_message("aria", text)
        self._set_state(STATE_IDLE)
        # Speak a clean JARVIS-style summary, not the raw technical output
        spoken = self._jarvis_summary(text)
        if spoken:
            threading.Thread(target=self.voice.speak, args=(spoken,), daemon=True).start()
        return False

    def _jarvis_summary(self, text: str) -> str:
        """Convert raw action result into a clean JARVIS-like spoken response.
        Strips technical content, paths, commands, tracebacks, etc."""
        import re

        if not text:
            return ""

        clean = text.strip()

        # ── If it already starts with the new JARVIS format (🧠 ✅ ..., sir.) ──
        # Extract the clean message and strip emoji, it's already good
        if clean.startswith("🧠"):
            # Remove all emoji and extra whitespace
            spoken = re.sub(r'[🧠✅❌⚡⚠️🖼️📋🎤📅📧📱📷💬🎭🔋💻▶️📁]+\s*', '', clean)
            # Remove file paths for voice
            spoken = re.sub(r'/\S+\.\S+', '', spoken)
            spoken = re.sub(r'/home/\S+', '', spoken)
            spoken = re.sub(r'http\S+', '', spoken)
            spoken = re.sub(r'\s+', ' ', spoken).strip()
            if spoken and len(spoken) > 3:
                return spoken
            return "Done, sir."

        # ── Legacy format handlers (reflex path: ⚡ tool_name\nkey: val) ──

        # Brightness
        if 'set_brightness' in text or 'brightness' in text.lower():
            match = re.search(r'level:\s*(\d+)', text)
            level = match.group(1) if match else "requested level"
            return f"Brightness set to {level} percent, sir."

        # Volume
        if 'set_volume' in text or 'volume' in text.lower():
            match = re.search(r'level:\s*(\d+)', text)
            level = match.group(1) if match else "requested level"
            return f"Volume set to {level}, sir."

        # Media control
        if 'media_control' in text:
            match = re.search(r'command:\s*(\w+)', text)
            cmd = match.group(1) if match else "done"
            names = {
                "pause": "Playback paused",
                "play": "Playback resumed",
                "next": "Skipped to next",
                "previous": "Back to previous",
                "mute": "Audio muted",
                "stop": "Playback stopped",
                "fullscreen": "Fullscreen toggled",
            }
            msg = names.get(cmd, cmd)
            return f"{msg}, sir."

        # YouTube
        if 'youtube_search' in text.lower() or 'Playing' in text:
            match = re.search(r'(?:title|query):\s*(.+?)(?:\n|$)', text)
            query = match.group(1).strip() if match else "your selection"
            return f"Playing {query} on YouTube, sir."

        # Screenshot
        if 'screenshot' in text.lower():
            return "Screenshot taken, sir."

        # Battery
        if 'battery' in text.lower():
            match = re.search(r'(?:percent|level):\s*(\d+)', text)
            pct = match.group(1) if match else "unknown"
            return f"Battery is at {pct} percent, sir."

        # WhatsApp read
        if 'read_whatsapp' in text or 'WhatsApp Messages' in text:
            return "Here are your messages, sir."

        # File operations
        if 'File sent to' in text:
            match = re.search(r'sent to (\w+)', text)
            name = match.group(1) if match else "the contact"
            return f"File sent to {name}, sir."
        elif 'Message sent to' in text:
            match = re.search(r'sent to (\w+)', text)
            name = match.group(1) if match else "the contact"
            return f"Message sent to {name}, sir."
        elif 'GIF sent to' in text:
            match = re.search(r'sent to (\w+)', text)
            name = match.group(1) if match else "the contact"
            return f"GIF sent to {name}, sir."

        # Image generation
        if 'Image generated' in text or 'image generated' in text:
            return "Image has been generated and saved, sir."

        # Wallpaper
        if 'Wallpaper' in text:
            return "Wallpaper has been updated, sir."

        # Opening URLs
        if 'Opening:' in text:
            match = re.search(r'Opening:\s*(\S+)', text)
            url = match.group(1) if match else "the page"
            domain = re.sub(r'https?://(www\.)?', '', url).split('/')[0] if '://' in url else url
            return f"Opening {domain}, sir."

        # App launch
        if 'Launched:' in text or 'launched' in text.lower():
            match = re.search(r'(?:Launched|launched):\s*(\S+)', text)
            app = match.group(1) if match else "the application"
            return f"{app} launched, sir."

        # PDF operations
        if 'PDF created' in text or 'pdf created' in text.lower():
            return "PDF has been created, sir."
        if 'Extracted' in text and 'image' in text.lower():
            return "Images extracted from the PDF, sir."

        # Calendar
        if 'calendar' in text.lower() and 'created' in text.lower():
            return "Event added to your calendar, sir."
        if 'schedule' in text.lower() or 'Your schedule' in text:
            return "Here's your schedule, sir."

        # Shell results
        if '$ ' in text and '\n' in text:
            lines = clean.split('\n')
            summary_parts = []
            for line in lines:
                line = line.strip()
                if line.startswith('$ ') or line.startswith('exit '):
                    continue
                if 'Traceback' in line or 'Error:' in line or 'File "' in line:
                    continue
                if line.startswith('/') and '/' in line[1:]:
                    continue
                if not line or line == '(no output)':
                    continue
                summary_parts.append(line)
            if summary_parts:
                clean = ' '.join(summary_parts[:2])
            else:
                return "Done, sir."

        # ── Final cleanup ──
        clean = re.sub(r'[🧠⚡❌✅🖼️📋🎤📅📧📱📷💬🎭🔋💻▶️📁]+\s*', '', clean)
        clean = re.sub(r'/home/\S+', '', clean)
        clean = re.sub(r'http\S+', '', clean)
        clean = re.sub(r'\{[^}]+\}', '', clean)
        clean = re.sub(r'python3?\s+-c\s+.*', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()

        if not clean or len(clean) < 3:
            return "Done, sir."

        # Ensure ends addressing user
        if not clean.endswith("sir.") and not clean.endswith("sir"):
            clean = clean.rstrip('.') + ", sir."

        return clean

    def _set_state(self, new_state):
        self.state = new_state
        self.state_label.set_markup(
            f'<span font="10" foreground="#00e5ff">{new_state}</span>'
        )

    # ─────────────────────────────────────────────────────────────────────
    # VOICE INPUT
    # ─────────────────────────────────────────────────────────────────────

    def _on_mic(self, widget):
        self._set_state(STATE_LISTENING)
        self._add_message("aria", "🎤 Listening…")

        def worker():
            try:
                from src.ears import Ears
                ears = Ears()
                if ears.model:
                    text = ears.listen_once(timeout=7)
                    if text:
                        GLib.idle_add(self._post_voice_result, text)
                    else:
                        GLib.idle_add(self._post_voice_result, None)
                else:
                    GLib.idle_add(self._post_voice_result, None)
            except Exception as e:
                GLib.idle_add(self._on_result, f"❌ Voice error: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _post_voice_result(self, text):
        if text:
            # Remove the "Listening..." message
            if self.messages and self.messages[-1][1] == "🎤 Listening…":
                self.messages.pop()
            self._execute_text(text)
        else:
            if self.messages and self.messages[-1][1] == "🎤 Listening…":
                self.messages.pop()
            self._add_message("aria", "⚠️ Didn't catch that. Try again or type your command.")
            self._set_state(STATE_IDLE)
        return False

    # ─────────────────────────────────────────────────────────────────────
    # BRAIN INITIALIZATION
    # ─────────────────────────────────────────────────────────────────────

    def _init_brain(self):
        """Initialize LocalBrain in background thread."""
        try:
            self.brain = LocalBrain(
                action_model=OLLAMA_MODEL,
                api_url=OLLAMA_URL
            )
            self.brain_ready = True
            GLib.idle_add(self._add_message, "aria",
                          f"🧠 Brain online — {OLLAMA_MODEL}\n"
                          f"   Tools: {len(self.brain.tools.tools_registry)} | "
                          f"Memory: {len(self.brain.memory)} behaviors")
            print(f"[✓] LocalBrain initialized with {OLLAMA_MODEL}")
        except Exception as e:
            print(f"[!] Brain init failed: {e}")
            GLib.idle_add(self._add_message, "aria",
                          f"⚠️ Brain offline — using lightweight chat fallback\n({e})")

    # ─────────────────────────────────────────────────────────────────────
    # WHATSAPP BRIDGE AUTO-START
    # ─────────────────────────────────────────────────────────────────────

    def _start_whatsapp_bridge(self):
        """Auto-start WhatsApp bridge if not already running."""
        import socket, time as _time

        def port_open(port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(("127.0.0.1", port)) == 0

        # If bridge is already running, skip
        if port_open(3001):
            print("[✓] WhatsApp bridge already running on :3001")
            GLib.idle_add(self._add_message, "aria", "📱 WhatsApp bridge connected")
            return

        # Start the bridge
        bridge_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whatsapp-bridge")
        bridge_script = os.path.join(bridge_dir, "index.js")

        if not os.path.isfile(bridge_script):
            print(f"[!] WhatsApp bridge not found at {bridge_script}")
            return

        print("[*] Starting WhatsApp bridge...")
        GLib.idle_add(self._add_message, "aria", "📱 Starting WhatsApp bridge...")

        try:
            self.bridge_proc = subprocess.Popen(
                ["node", bridge_script],
                cwd=bridge_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Wait for bridge to become ready (up to 30s)
            for i in range(30):
                _time.sleep(1)
                if port_open(3001):
                    print(f"[✓] WhatsApp bridge started on :3001 ({i+1}s)")
                    GLib.idle_add(self._add_message, "aria", "📱 WhatsApp bridge online ✓")
                    return
                # Check if process died
                if self.bridge_proc.poll() is not None:
                    print("[!] WhatsApp bridge process exited early")
                    GLib.idle_add(self._add_message, "aria",
                                  "⚠️ WhatsApp bridge failed to start")
                    return

            print("[!] WhatsApp bridge startup timed out (30s)")
            GLib.idle_add(self._add_message, "aria",
                          "⚠️ WhatsApp bridge startup timed out")

        except Exception as e:
            print(f"[!] WhatsApp bridge start failed: {e}")
            GLib.idle_add(self._add_message, "aria",
                          f"⚠️ WhatsApp bridge error: {e}")

    # ─────────────────────────────────────────────────────────────────────
    # CLEANUP ON EXIT
    # ─────────────────────────────────────────────────────────────────────

    def _on_destroy(self, widget):
        """Clean up bridge subprocess on exit."""
        if self.bridge_proc and self.bridge_proc.poll() is None:
            print("[*] Stopping WhatsApp bridge...")
            self.bridge_proc.terminate()
            try:
                self.bridge_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.bridge_proc.kill()
        Gtk.main_quit()

    # ─────────────────────────────────────────────────────────────────────
    # SERVICE STATUS LOADING
    # ─────────────────────────────────────────────────────────────────────

    def _load_services(self):
        svcs = check_services()
        GLib.idle_add(self._update_service_ui, svcs)

        # Also get system info
        try:
            info = self.tools.execute("get_system_info")
            if info.get("success"):
                d = info.get("info", {})
                text = (f"CPU: {d.get('cpu_percent', '?')}%  "
                        f"RAM: {d.get('memory_percent', '?')}%\n"
                        f"Disk: {d.get('disk_used_percent', '?')}%")
                GLib.idle_add(self._set_sys_label, text)
        except Exception:
            pass

    def _update_service_ui(self, svcs):
        self.services = svcs
        for name, dot_label in self.service_labels.items():
            if svcs.get(name, False):
                dot_label.set_markup('<span foreground="#2edc73">●</span>')
            else:
                dot_label.set_markup('<span foreground="#ea4040">●</span>')
        return False

    def _set_sys_label(self, text):
        self.sys_label.set_markup(f'<span font="8" foreground="#6a7088">{text}</span>')
        return False


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    win = ARIAWindow()
    Gtk.main()
