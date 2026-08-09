from speech.microphone import Microphone
from speech.speech_to_text import SpeechToText
from brain.groq_service import GroqService

mic = Microphone()
stt = SpeechToText()
groq = GroqService()

audio = mic.listen()

text = stt.transcribe(audio)

print("\n========== YOU ==========")
print(text)

reply = groq.respond(text)

print("\n========== BAYMAX ==========")
print(reply)