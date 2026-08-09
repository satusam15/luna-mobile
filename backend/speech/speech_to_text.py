import os

from dotenv import load_dotenv
from groq import Groq
from google import genai

load_dotenv()

# Each Groq model here is billed against its own separate quota.
GROQ_STT_MODEL_CHAIN = [
    "whisper-large-v3-turbo",
    "whisper-large-v3",
]

TRANSCRIBE_PROMPT = "Transcribe this audio exactly as spoken. Return ONLY the transcription text, nothing else - no notes, no quotes."


class SpeechToText:

    def __init__(self):
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        gemini_key = os.getenv("GEMINI_API_KEY")
        self.gemini_client = genai.Client(api_key=gemini_key) if gemini_key else None

    def _transcribe_groq(self, audio_path, model):
        with open(audio_path, "rb") as audio_file:
            transcription = self.groq_client.audio.transcriptions.create(
                file=(audio_path, audio_file.read()),
                model=model,
                language="en"
            )
        return transcription.text

    def _transcribe_gemini(self, audio_path):
        if not self.gemini_client:
            raise RuntimeError("No GEMINI_API_KEY set.")

        uploaded_file = self.gemini_client.files.upload(file=audio_path)

        response = self.gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[TRANSCRIBE_PROMPT, uploaded_file]
        )

        return response.text.strip()

    def transcribe(self, audio_path):

        last_error = None

        for model in GROQ_STT_MODEL_CHAIN:
            try:
                return self._transcribe_groq(audio_path, model)
            except Exception as e:
                last_error = e
                print(f"⚠️ STT model {model} unavailable ({e}), switching model...")

        try:
            return self._transcribe_gemini(audio_path)
        except Exception as e:
            print(f"⚠️ Gemini STT fallback also failed ({e})")

        print(f"⚠️ All STT layers failed: {last_error}")
        return ""