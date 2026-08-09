import sounddevice as sd
import numpy as np

devices = [5, 27, 58]

for device in devices:

    print("\n========================")
    print(f"Testing device {device}")
    print("========================")

    print("Speak NOW!")

    audio = sd.rec(
        16000,
        samplerate=16000,
        channels=1,
        dtype=np.int16,
        device=device
    )

    sd.wait()

    print("Min :", np.min(audio))
    print("Max :", np.max(audio))