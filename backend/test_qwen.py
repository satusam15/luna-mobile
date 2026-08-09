import ollama
import json

response = ollama.chat(
    model="qwen2.5vl:3b",
    messages=[
        {
            "role": "user",
            "content": """
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
""",
            "images": ["screenshot.png"]
        }
    ]
)

print("========== RAW RESPONSE ==========")
print(response["message"]["content"])

print("\n========== PARSED JSON ==========")

result = json.loads(response["message"]["content"])

print(result)