import os
import json
import base64
import time

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

PROMPT = """
You are Luna's eyes - the user just showed you something through their camera
(a notebook page, textbook, whiteboard, screen, object, or scene) and asked
about it.

Look closely and describe what you see in enough detail that someone who
can't see the image could still help with it. This means:

- If there's a math problem, equation, code snippet, or diagram: transcribe
  it as accurately as you can, exactly as written (symbols, numbers, variable
  names, indentation for code).
- If there's handwritten or printed text: transcribe the relevant text.
- If it's a general scene/object (not text-based): describe what's there and
  anything notable about it.
- Note anything that looks like an error, a mistake, or something the user
  might need help with.

Return ONLY valid JSON in this format:

{
    "summary": ""
}

The "summary" field should contain everything above as one clear, thorough
description - this is the only thing that gets passed along, so don't leave
out details that might matter for answering the user's question.

Do not add commentary outside the JSON. Output ONLY the JSON object.
"""


class VisionService:

    def __init__(self):

        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        # Groq's multimodal lineup changes often - check console.groq.com/docs/models
        # if this model name ever stops working.
        self.model = "qwen/qwen3.6-27b"

    def _encode_image(self, image_path):

        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _mime_for(self, image_path):
        ext = image_path.rsplit(".", 1)[-1].lower()
        return {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
        }.get(ext, "image/jpeg")

    def describe(self, image_path, retries=2):

        image_b64 = self._encode_image(image_path)
        mime = self._mime_for(image_path)
        last_error = None

        for attempt in range(retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime};base64,{image_b64}"
                                    }
                                }
                            ]
                        }
                    ],
                    reasoning_format="hidden",  # keep the answer in .content, not split into a reasoning field
                    reasoning_effort="none"     # skip deep reasoning, we just need a quick observation
                )

                if not response.choices[0].message.content:
                    raise ValueError("Vision model returned empty content")

                clean = response.choices[0].message.content.strip()

                if clean.startswith("```json"):
                    clean = clean.replace("```json", "", 1)
                if clean.startswith("```"):
                    clean = clean.replace("```", "", 1)
                if clean.endswith("```"):
                    clean = clean[:-3]

                return json.loads(clean.strip())

            except Exception as e:
                last_error = e
                if attempt < retries:
                    wait = 1.5 * (attempt + 1)
                    print(f"⚠️ Vision attempt {attempt + 1} failed, retrying in {wait:.1f}s...")
                    time.sleep(wait)

        raise last_error