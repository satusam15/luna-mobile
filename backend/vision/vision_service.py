import os
import json
import base64
import time

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

PROMPT = """
You are Baymax's visual perception system.

Analyze this desktop screenshot.

Return ONLY valid JSON.

Format:

{
    "application": "",
    "activity": "",
    "visible_error": false,
    "needs_attention": false,
    "summary": ""
}

Rules:

- Do not explain.
- Do not solve problems.
- Only observe.
- Output ONLY JSON.
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

    def describe(self, image_path, retries=2):

        image_b64 = self._encode_image(image_path)
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
                                        "url": f"data:image/png;base64,{image_b64}"
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