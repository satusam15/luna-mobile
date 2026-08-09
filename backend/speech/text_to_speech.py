import os
import time
import wave
import asyncio

import requests
import pygame
import numpy as np
import sounddevice as sd
import edge_tts

from dotenv import load_dotenv
from google import genai
from google.genai import types
from speech.microphone import DEVICE

load_dotenv()

MAX_INPUT_CHARS = 200  # Orpheus hard limit

INTERRUPT_SAMPLE_RATE = 16000
INTERRUPT_MIN_SPEECH_MS = 250


class TextToSpeech:

    def __init__(self):

        self.fish_api_key = os.getenv("FISH_API_KEY")
        self.fish_model = "s2.1-pro-free"  # genuinely free, no hard cap, Fair Use Policy
        self.fish_reference_id = os.getenv("FISH_VOICE_ID")  # optional - pick a voice from fish.audio's library later

        self.api_key = os.getenv("GROQ_API_KEY")
        self.groq_model = "canopylabs/orpheus-v1-english"
        self.groq_voice = "hannah"  # female - try autumn/diana/hannah (female) or austin/daniel/troy (male)

        self.edge_voice = "en-US-JennyNeural"  # cloud-based (Microsoft), not local - fast

        gemini_key = os.getenv("GEMINI_API_KEY")
        self.gemini_client = genai.Client(api_key=gemini_key) if gemini_key else None
        self.gemini_tts_model = "gemini-2.5-flash-preview-tts"
        self.gemini_voice = "Kore"  # female Gemini voice - others: Aoede, Leda, Zephyr

        pygame.mixer.init()

    # ---------------- Layer 2: Fish Audio (free, no cap, but slower) ----------------
    def _generate_fish(self, text):

        if not self.fish_api_key:
            raise RuntimeError("No FISH_API_KEY set.")

        body = {
            "text": text,
            "format": "mp3"
        }

        if self.fish_reference_id:
            body["reference_id"] = self.fish_reference_id

        response = requests.post(
            "https://api.fish.audio/v1/tts",
            headers={
                "Authorization": f"Bearer {self.fish_api_key}",
                "Content-Type": "application/json",
                "model": self.fish_model
            },
            json=body
        )

        if response.status_code != 200:
            raise RuntimeError(f"Fish Audio TTS {response.status_code}: {response.text}")

        with open("baymax_voice_fish.mp3", "wb") as f:
            f.write(response.content)

        return "baymax_voice_fish.mp3"

    # ---------------- Layer 1: Groq / Orpheus (primary - fastest) ----------------
    def _generate_groq(self, text):

        clipped = text
        if len(clipped) > MAX_INPUT_CHARS:
            clipped = clipped[:MAX_INPUT_CHARS - 1].rsplit(" ", 1)[0] + "."

        response = requests.post(
            "https://api.groq.com/openai/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.groq_model,
                "voice": self.groq_voice,
                "input": clipped,
                "response_format": "wav"
            }
        )

        if response.status_code != 200:
            raise RuntimeError(f"Groq TTS {response.status_code}: {response.text}")

        with open("baymax_voice.wav", "wb") as f:
            f.write(response.content)

        return "baymax_voice.wav"

    # ---------------- Layer 3: edge-tts (cloud, separate service) ----------------
    def _generate_edge(self, text):

        async def _run():
            communicate = edge_tts.Communicate(text=text, voice=self.edge_voice)
            await communicate.save("baymax_voice_edge.mp3")

        asyncio.run(_run())
        return "baymax_voice_edge.mp3"

    # ---------------- Layer 4: Gemini TTS (separate provider entirely) ----------------
    def _generate_gemini(self, text):

        if not self.gemini_client:
            raise RuntimeError("No GEMINI_API_KEY set.")

        response = self.gemini_client.models.generate_content(
            model=self.gemini_tts_model,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=self.gemini_voice
                        )
                    )
                )
            )
        )

        pcm_data = response.candidates[0].content.parts[0].inline_data.data

        # Gemini returns raw 24kHz 16-bit mono PCM - wrap it into a playable wav file
        path = "baymax_voice_gemini.wav"
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(pcm_data)

        return path

    def generate(self, text):
        """
        Tries each TTS layer in order - all cloud-based, no local models.
        Each is a separate provider/service with its own quota.
        Groq goes first: it's noticeably faster than Fish Audio in practice,
        even though Fish Audio is free with no hard cap.
        """

        try:
            return self._generate_groq(text)
        except Exception as e:
            print(f"⚠️ Groq TTS unavailable ({e}), switching to Fish Audio...")

        try:
            return self._generate_fish(text)
        except Exception as e:
            print(f"⚠️ Fish Audio TTS unavailable ({e}), switching to edge-tts...")

        try:
            return self._generate_edge(text)
        except Exception as e:
            print(f"⚠️ edge-tts unavailable ({e}), switching to Gemini TTS...")

        return self._generate_gemini(text)

    def speak(self, text, interrupt_threshold=None):

        audio_path = self.generate(text)

        pygame.mixer.music.load(audio_path)
        pygame.mixer.music.play()

        if interrupt_threshold is not None:
            interrupted = self._play_with_interrupt_watch(interrupt_threshold)
        else:
            interrupted = False
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)

        pygame.mixer.music.unload()
        os.remove(audio_path)

        return interrupted

    def _play_with_interrupt_watch(self, threshold):

        interrupted = False
        speech_ms_accumulated = 0

        def callback(indata, frames, time_info, status):
            nonlocal interrupted, speech_ms_accumulated

            rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))

            if rms >= threshold:
                speech_ms_accumulated += (frames / INTERRUPT_SAMPLE_RATE) * 1000
                if speech_ms_accumulated >= INTERRUPT_MIN_SPEECH_MS:
                    interrupted = True
                    pygame.mixer.music.stop()
                    raise sd.CallbackStop
            else:
                speech_ms_accumulated = 0

        try:
            with sd.InputStream(
                samplerate=INTERRUPT_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                device=DEVICE,
                callback=callback
            ):
                while pygame.mixer.music.get_busy() and not interrupted:
                    time.sleep(0.05)
        except sd.CallbackStop:
            pass

        if interrupted:
            print("🛑 Interrupted - listening now...")

        return interrupted