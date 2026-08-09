from speech.microphone import Microphone
from speech.speech_to_text import SpeechToText
from speech.text_to_speech import TextToSpeech
from brain.groq_service import GroqService


mic = Microphone()
stt = SpeechToText()
tts = TextToSpeech()
groq = GroqService()

print("🤖 Baymax is awake.")

while True:

    audio = mic.listen()

    user = stt.transcribe(audio).strip()

    if not user:
        continue

    print(f"\n🧑 You : {user}")

    if "goodbye baymax" in user.lower():
        tts.speak("Goodbye. Take care.")
        break

    reply = groq.respond(user)

    print(f"\n🤖 Baymax : {reply}")

    tts.speak(reply)