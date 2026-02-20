"""
ARIA JARVIS Voice Engine
Voice cloning using Coqui XTTS-v2 with JARVIS reference audio.
Gives ARIA a JARVIS-like voice for all spoken responses.
"""

import os
import threading
import subprocess
import tempfile
import time

# Paths
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCE_WAV = os.path.join(PROJECT_DIR, "models", "jarvis_reference.wav")
XTTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"


class VoiceEngine:
    """JARVIS voice TTS using XTTS-v2 voice cloning."""

    def __init__(self):
        self._tts = None
        self._lock = threading.Lock()
        self._ready = False
        self._loading = False
        self._speaking = False
        # Play queue — only latest response matters
        self._current_proc = None

    def _load_model(self):
        """Lazy-load XTTS-v2 onto GPU."""
        if self._ready or self._loading:
            return
        self._loading = True
        try:
            # Patch torch.load for Coqui TTS compatibility (torch 2.10+ defaults to weights_only=True)
            import torch
            _orig_load = torch.load
            def _patched_load(*args, **kwargs):
                kwargs.setdefault('weights_only', False)
                return _orig_load(*args, **kwargs)
            torch.load = _patched_load

            # Set torchaudio backend to soundfile (torchcodec not installed)
            try:
                import torchaudio
                torchaudio.set_audio_backend("soundfile")
            except Exception:
                pass

            from TTS.api import TTS
            print("[*] Loading XTTS-v2 for JARVIS voice...")
            t0 = time.time()
            self._tts = TTS(XTTS_MODEL).to("cuda")
            dt = time.time() - t0
            print(f"[✓] XTTS-v2 loaded in {dt:.1f}s")
            self._ready = True
        except Exception as e:
            print(f"[!] Failed to load XTTS-v2: {e}")
            import traceback
            traceback.print_exc()
            self._ready = False
        finally:
            self._loading = False

    def init_async(self):
        """Start loading in background thread."""
        threading.Thread(target=self._load_model, daemon=True).start()

    @property
    def ready(self):
        return self._ready

    def speak(self, text: str):
        """Generate speech from text using JARVIS voice and play it.
        Runs TTS synchronously, plays audio in background."""
        if not text or not text.strip():
            return

        # Clean text — remove emojis and special chars that TTS can't handle
        import re
        clean = re.sub(r'[^\w\s.,!?;:\'-]', '', text).strip()
        if not clean:
            return

        # Limit to 2-3 sentences for concise responses
        sentences = re.split(r'(?<=[.!?])\s+', clean)
        clean = ' '.join(sentences[:3])

        if not self._ready:
            # Fallback to pyttsx3 if XTTS not loaded
            self._speak_fallback(clean)
            return

        try:
            with self._lock:
                # Stop any currently playing audio
                self._stop_current()

                # Generate WAV to temp file
                tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False,
                                                  dir=tempfile.gettempdir())
                tmp_path = tmp.name
                tmp.close()

                self._tts.tts_to_file(
                    text=clean,
                    file_path=tmp_path,
                    speaker_wav=REFERENCE_WAV,
                    language="en"
                )

                # Play in background
                self._play_audio(tmp_path)

        except Exception as e:
            print(f"[!] JARVIS voice error: {e}")
            self._speak_fallback(clean)

    def _play_audio(self, wav_path: str):
        """Play WAV file using aplay (non-blocking)."""
        try:
            self._current_proc = subprocess.Popen(
                ["aplay", "-q", wav_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # Clean up temp file after playback in a thread
            def cleanup():
                if self._current_proc:
                    self._current_proc.wait()
                try:
                    os.unlink(wav_path)
                except:
                    pass
            threading.Thread(target=cleanup, daemon=True).start()
        except Exception as e:
            print(f"[!] Audio playback error: {e}")
            try:
                os.unlink(wav_path)
            except:
                pass

    def _stop_current(self):
        """Stop currently playing audio."""
        if self._current_proc and self._current_proc.poll() is None:
            try:
                self._current_proc.terminate()
                self._current_proc.wait(timeout=1)
            except:
                pass
            self._current_proc = None

    def _speak_fallback(self, text: str):
        """Fallback TTS using espeak (fast, robotic but works)."""
        try:
            subprocess.Popen(
                ["espeak", "-v", "en+m3", "-s", "160", "-p", "30", text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass  # No audio output available

    def stop(self):
        """Stop all audio."""
        self._stop_current()


# Quick test
if __name__ == "__main__":
    v = VoiceEngine()
    print("Loading XTTS-v2...")
    v._load_model()
    if v.ready:
        print("Speaking...")
        v.speak("Hello sir. All systems are fully operational. How may I assist you today?")
        # Wait for playback
        import time
        time.sleep(10)
    else:
        print("Failed to load — using fallback")
        v._speak_fallback("Hello, I am ARIA")
