from openwakeword.model import Model
import sounddevice as sd
import numpy as np

# Load the default wake-word model
model = Model()

print("👂 Listening for wake word...")

while True:

    audio = sd.rec(
        1280,
        samplerate=16000,
        channels=1,
        dtype=np.int16
    )

    sd.wait()

    prediction = model.predict(audio.flatten())

    for wakeword, score in prediction.items():

        if score > 0.5:
            print(f"🟢 Wake Word Detected! ({wakeword})")
            