"""
Luna backend — FastAPI + WebSocket.

Replaces the old local-desktop main.py (which recorded from a physical mic,
played audio through local speakers, and screenshotted the desktop).

New flow: any device opens the frontend page served by this same app,
connects over WebSocket, and sends either:
  - {"type": "audio", "data": "<base64 wav/webm bytes>"}   -> full turn (STT -> brain -> TTS)
  - {"type": "vision", "image": "<base64 jpg/png>", "text": "<optional question>"}

Server replies with:
  - {"type": "state", "state": "listening|thinking|looking|speaking|idle"}
  - {"type": "speech", "text": "<reply text>"}
  - {"type": "audio", "data": "<base64 audio bytes>", "format": "wav|mp3"}

No local mic/speaker/screenshot code here anymore — that all lives in the
browser now (see frontend/app.js).
"""

import os
import json
import base64
import tempfile
import mimetypes

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from brain.groq_service import GroqService
from speech.speech_to_text import SpeechToText
from speech.text_to_speech import TextToSpeech
from vision.vision_service import VisionService
from planner.reminder_store import get_due_reminders

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Shared services (one Luna, one shared memory/session for now)
# ----------------------------
groq = GroqService()
stt = SpeechToText()
tts = TextToSpeech()
vision_service = VisionService()

VISION_TRIGGERS = [
    "screen", "look at", "what's this", "what is this",
    "see this", "camera", "what am i looking at",
    "check this", "help me with this", "what do you see",
    "solve this", "solve it", "explain this", "read this",
    "what does this say", "what's the answer", "answer this",
    "look at my", "look here", "can you see"
]

# Whisper (and most STT models) hallucinate plausible-sounding phrases when
# fed near-silent or noise-only audio instead of returning nothing. These
# are the most common hallucinated outputs across Whisper-family models -
# if a transcription is short AND matches one of these almost verbatim,
# treat it as no real speech rather than replying to it.
HALLUCINATION_PHRASES = {
    "thank you.", "thank you", "thanks for watching.", "thanks for watching",
    "thank you for watching.", "thank you for watching", "bye.", "bye",
    "please subscribe.", "please subscribe", "thank you so much.",
    "thank you so much", "you", "the", "okay.", "okay", "i'm sorry.",
    "i'm sorry", ".", "..", "...",
}


def is_likely_hallucination(text: str) -> bool:
    cleaned = text.strip().lower()
    return cleaned in HALLUCINATION_PHRASES


def needs_vision(text: str) -> bool:
    lowered = text.lower()
    return any(trigger in lowered for trigger in VISION_TRIGGERS)


# ----------------------------
# Connected clients (broadcast state/speech to whoever's connected)
# ----------------------------
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def send(self, ws: WebSocket, payload: dict):
        await ws.send_text(json.dumps(payload))

    async def broadcast(self, payload: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


def _save_temp_audio(b64_data: str, suffix=".wav") -> str:
    raw = base64.b64decode(b64_data)
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
    return path


def _save_temp_image(b64_data: str, mime: str = "image/jpeg") -> str:
    ext = mimetypes.guess_extension(mime) or ".jpg"
    raw = base64.b64decode(b64_data)
    fd, path = tempfile.mkstemp(suffix=ext)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
    return path


async def handle_audio_turn(ws: WebSocket, b64_audio: str, audio_format: str):
    """Full turn: STT -> (vision if triggered) -> brain -> TTS -> send back."""

    await manager.send(ws, {"type": "state", "state": "thinking"})

    audio_path = _save_temp_audio(b64_audio, suffix=f".{audio_format}")
    try:
        user_text = stt.transcribe(audio_path).strip()
    finally:
        os.remove(audio_path)

    if not user_text or is_likely_hallucination(user_text):
        await manager.send(ws, {"type": "state", "state": "idle"})
        return

    print(f"\n🧑 You: {user_text}")

    context = user_text

    if needs_vision(user_text):
        await manager.send(ws, {"type": "state", "state": "looking"})
        await manager.send(ws, {"type": "request_camera_frame"})
        # Frontend should respond with a "vision" message containing the frame;
        # for a simple synchronous flow, the frontend can instead attach the
        # frame directly on the audio message (see index's combined send).
        # Fallback: just answer without vision if no frame arrives.

    await manager.send(ws, {"type": "state", "state": "thinking"})
    reply, emotion = groq.respond(context)

    print(f"\n🤖 Luna [{emotion}]: {reply}")

    await manager.send(ws, {"type": "speech", "text": reply, "emotion": emotion})
    await manager.send(ws, {"type": "state", "state": "speaking"})

    audio_out_path = tts.generate(reply)
    with open(audio_out_path, "rb") as f:
        audio_bytes = f.read()
    os.remove(audio_out_path)

    ext = audio_out_path.rsplit(".", 1)[-1]
    await manager.send(ws, {
        "type": "audio",
        "data": base64.b64encode(audio_bytes).decode("utf-8"),
        "format": ext
    })

    await manager.send(ws, {"type": "state", "state": "idle"})


async def handle_audio_turn_with_image(ws: WebSocket, b64_audio: str, audio_format: str, b64_image: str):
    """Same as handle_audio_turn, but an image was already captured client-side
    and sent alongside the audio (used when the frontend proactively attaches
    a camera frame for vision-trigger phrases)."""

    await manager.send(ws, {"type": "state", "state": "thinking"})

    audio_path = _save_temp_audio(b64_audio, suffix=f".{audio_format}")
    try:
        user_text = stt.transcribe(audio_path).strip()
    finally:
        os.remove(audio_path)

    if not user_text or is_likely_hallucination(user_text):
        await manager.send(ws, {"type": "state", "state": "idle"})
        return

    print(f"\n🧑 You: {user_text}")

    context = user_text

    if needs_vision(user_text) and b64_image:
        await manager.send(ws, {"type": "state", "state": "looking"})
        image_path = _save_temp_image(b64_image)
        try:
            observation = vision_service.describe(image_path)
            context = (
                f"[You just looked through the camera. "
                f"Summary: {observation.get('summary')}.] "
                f"The user asked: {user_text}"
            )
        except Exception as e:
            print("⚠️ Vision failed:", e)
        finally:
            os.remove(image_path)

    await manager.send(ws, {"type": "state", "state": "thinking"})
    reply, emotion = groq.respond(context)

    print(f"\n🤖 Luna [{emotion}]: {reply}")

    await manager.send(ws, {"type": "speech", "text": reply, "emotion": emotion})
    await manager.send(ws, {"type": "state", "state": "speaking"})

    audio_out_path = tts.generate(reply)
    with open(audio_out_path, "rb") as f:
        audio_bytes = f.read()
    os.remove(audio_out_path)

    ext = audio_out_path.rsplit(".", 1)[-1]
    await manager.send(ws, {
        "type": "audio",
        "data": base64.b64encode(audio_bytes).decode("utf-8"),
        "format": ext
    })

    await manager.send(ws, {"type": "state", "state": "idle"})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    await manager.send(ws, {"type": "state", "state": "idle"})

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "audio":
                image = msg.get("image")  # optional pre-attached camera frame
                if image:
                    await handle_audio_turn_with_image(
                        ws, msg["data"], msg.get("format", "webm"), image
                    )
                else:
                    await handle_audio_turn(ws, msg["data"], msg.get("format", "webm"))

            elif msg_type == "ping":
                await manager.send(ws, {"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(ws)


@app.get("/api/health")
def health():
    return {"message": "Luna backend running"}


# ----------------------------
# Serve the frontend (single URL: open it, become Luna)
# ----------------------------
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))