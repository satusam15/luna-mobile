import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
import time

SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = 5
CHUNK_SIZE = 1024

# Detection Settings
CALIBRATION_DURATION = 0.6     # Seconds spent measuring room noise, done ONCE at startup
NOISE_MARGIN = 250              # How much louder than ambient noise counts as "speech"
MIN_THRESHOLD = 150              # Floor so a dead-silent room doesn't make this hyper-sensitive
SILENCE_DURATION = 1.6           # Seconds of quiet after speech before we consider you done
MAX_WAIT_TIME = 20.0              # Seconds it'll wait for you to start talking before giving up
MIN_SPEECH_DURATION = 0.3        # Ignore short blips/coughs as if they weren't speech


class Microphone:

    def __init__(self):
        # Calibrate once when Baymax starts up — not on every listen() call
        self.threshold = self._calibrate()

    def _calibrate(self):
        """Measure ambient noise once to set an adaptive threshold for the whole session."""
        print("🔧 Calibrating mic to room noise...")

        samples = sd.rec(
            int(CALIBRATION_DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            device=DEVICE
        )
        sd.wait()

        ambient_rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
        threshold = max(MIN_THRESHOLD, ambient_rms + NOISE_MARGIN)

        print(f"🎚️ Ambient noise: {ambient_rms:.1f} -> threshold set to {threshold:.1f}")

        return threshold

    def recalibrate(self):
        """Call this manually later if the room noise changes significantly."""
        self.threshold = self._calibrate()

    def listen(self):
        threshold = self.threshold

        print("🎤 Listening... (take your time)")

        audio_frames = []

        max_silent_samples = int(SILENCE_DURATION * SAMPLE_RATE)
        max_wait_samples = int(MAX_WAIT_TIME * SAMPLE_RATE)
        min_speech_samples = int(MIN_SPEECH_DURATION * SAMPLE_RATE)

        total_samples_recorded = 0
        silent_samples_accumulated = 0
        speech_samples_accumulated = 0
        has_spoken = False

        def callback(indata, frames, time_info, status):
            nonlocal total_samples_recorded, silent_samples_accumulated
            nonlocal speech_samples_accumulated, has_spoken

            audio_frames.append(indata.copy())
            total_samples_recorded += frames

            rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))

            if rms >= threshold:
                speech_samples_accumulated += frames
                silent_samples_accumulated = 0

                if speech_samples_accumulated >= min_speech_samples:
                    has_spoken = True
            else:
                if has_spoken:
                    silent_samples_accumulated += frames
                    if silent_samples_accumulated >= max_silent_samples:
                        raise sd.CallbackStop
                else:
                    speech_samples_accumulated = 0

                    if total_samples_recorded >= max_wait_samples:
                        print("⏳ Timed out waiting for speech.")
                        raise sd.CallbackStop

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            device=DEVICE,
            blocksize=CHUNK_SIZE,
            callback=callback
        )

        with stream:
            while stream.active:
                time.sleep(0.1)

        print("✅ Recording Finished.")

        if not audio_frames:
            return None

        recording = np.concatenate(audio_frames, axis=0)

        write("speech.wav", SAMPLE_RATE, recording)

        return "speech.wav"