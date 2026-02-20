import pyttsx3
import threading

class Mouth:
    def __init__(self):
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 160) # Slightly faster than default
            self.engine.setProperty('volume', 1.0)
            
            # Select a female voice if available (often clearer)
            voices = self.engine.getProperty('voices')
            for voice in voices:
                if "female" in voice.name.lower():
                    self.engine.setProperty('voice', voice.id)
                    break
        except Exception as e:
            print(f"Error initializing TTS: {e}")
            self.engine = None

    def speak(self, text):
        if not self.engine:
            print(f"[Mouth] (Text-only): {text}")
            return

        print(f"[Mouth]: {text}")
        # Run in a separate thread to avoid blocking the main loop
        threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()

    def _speak_thread(self, text):
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except RuntimeError:
            # Engine loop might be already running
            pass

if __name__ == "__main__":
    m = Mouth()
    m.speak("System online. Voice module active.")
