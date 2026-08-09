import asyncio
import json
import threading
import time

from speech.microphone import Microphone
from speech.speech_to_text import SpeechToText
from speech.text_to_speech import TextToSpeech
from brain.groq_service import GroqService
from vision.vision_service import VisionService
from screenshot.screenshot_service import ScreenshotService
from communication.websocket_server import WebSocketServer
from planner.reminder_store import get_due_reminders

# ----------------------------
# Keywords that mean "look at my screen before answering"
# ----------------------------
VISION_TRIGGERS = [
    "screen", "look at", "what's this", "what is this",
    "see this", "error", "what am i doing", "what am i looking at",
    "check this", "help me with this"
]

EXIT_PHRASES = ["goodbye baymax", "bye baymax"]


def needs_vision(text: str) -> bool:
    lowered = text.lower()
    return any(trigger in lowered for trigger in VISION_TRIGGERS)


def save_state(text: str):
    with open("state/message.json", "w") as file:
        json.dump({"text": text}, file, indent=4)


# ----------------------------
# Services
# ----------------------------
mic = Microphone()
stt = SpeechToText()
tts = TextToSpeech()
groq = GroqService()
vision_service = VisionService()
screenshot_service = ScreenshotService()
websocket_server = WebSocketServer()

# ----------------------------
# WebSocket server (background event loop so Electron can connect)
# ----------------------------
loop = asyncio.new_event_loop()

threading.Thread(
    target=loop.run_forever,
    daemon=True
).start()

asyncio.run_coroutine_threadsafe(
    websocket_server.start(),
    loop
)


def send_to_frontend(text: str):
    """Sends a spoken reply for the speech bubble."""
    asyncio.run_coroutine_threadsafe(
        websocket_server.send(json.dumps({"type": "speech", "text": text})),
        loop
    )


def send_state(state: str):
    """Broadcasts the current pipeline stage so the character's eyes can react.
    Valid states: idle, listening, thinking, looking, speaking, interrupted
    """
    asyncio.run_coroutine_threadsafe(
        websocket_server.send(json.dumps({"type": "state", "state": state})),
        loop
    )


def reminder_checker_loop():
    """Runs in the background, checking every 30s for due reminders and announcing them."""
    while True:
        for reminder in get_due_reminders():
            announcement = f"Just a reminder: {reminder['text']}"
            print(f"\n⏰ {announcement}")
            send_state("speaking")
            send_to_frontend(announcement)
            tts.speak(announcement)
            send_state("idle")
        time.sleep(30)


# ----------------------------
# Main voice loop
# ----------------------------
threading.Thread(target=reminder_checker_loop, daemon=True).start()

print("🤖 Baymax is awake.")

while True:

    send_state("listening")
    audio = mic.listen()

    if not audio:
        send_state("idle")
        continue

    send_state("thinking")
    user_text = stt.transcribe(audio).strip()

    if not user_text:
        send_state("idle")
        continue

    print(f"\n🧑 You: {user_text}")

    if any(phrase in user_text.lower() for phrase in EXIT_PHRASES):
        farewell = "Goodbye. Take care."
        send_state("speaking")
        tts.speak(farewell)
        send_to_frontend(farewell)
        send_state("idle")
        break

    # ------------------------------------
    # Decide whether Baymax needs to look at the screen first
    # ------------------------------------
    if needs_vision(user_text):

        send_state("looking")
        print("\n📸 Capturing screen...")
        screenshot_service.capture()

        print("👀 Baymax is looking...")
        try:
            observation = vision_service.describe("screenshot.png")

            print("\n========== VISION ==========")
            print(observation)
            print("=============================\n")

            context = (
                f"[You just looked at the screen. "
                f"App: {observation.get('application')}. "
                f"Activity: {observation.get('activity')}. "
                f"Summary: {observation.get('summary')}.] "
                f"The user asked: {user_text}"
            )

        except Exception as e:
            print("⚠️ Vision failed:", e)
            context = user_text  # fall back to answering without vision

        send_state("thinking")
        reply = groq.respond(context)

    else:
        send_state("thinking")
        reply = groq.respond(user_text)

    print(f"\n🤖 Baymax: {reply}")

    save_state(reply)
    send_state("speaking")
    send_to_frontend(reply)
    interrupted = tts.speak(reply, interrupt_threshold=mic.threshold)

    if interrupted:
        send_state("interrupted")
        time.sleep(0.3)

    send_state("idle")