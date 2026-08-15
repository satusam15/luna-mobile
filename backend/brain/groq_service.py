import os
import re
import json
from datetime import datetime

from dotenv import load_dotenv
from groq import Groq

from memory.memory_store import facts_summary
from brain.tools import TOOLS_SCHEMA, TOOL_DISPATCH

load_dotenv()

MAX_TOOL_ROUNDS = 3  # safety cap so a tool-call loop can't run forever

VALID_EMOTIONS = [
    "normal", "happy", "sad", "angry", "surprised",
    "curious", "sleepy", "love", "confused", "playful"
]

EMOTION_TAG_RE = re.compile(r"^\s*[\[\(]\s*(\w+)\s*[\]\)]\s*", re.IGNORECASE)

# Backup keyword sniffing for when the model forgets the bracket tag entirely -
# keeps expressions matching the reply's tone even if formatting slips.
EMOTION_KEYWORDS = {
    "happy": ["glad", "great", "wonderful", "awesome", "nice!", "love that", "yay", "congrat"],
    "sad": ["sorry to hear", "that's rough", "unfortunate", "sad", "i'm sorry"],
    "angry": ["frustrating", "ridiculous", "annoying", "unacceptable"],
    "surprised": ["whoa", "wow", "really?", "no way", "seriously?", "didn't expect"],
    "curious": ["what do you mean", "tell me more", "curious", "why is that", "how come"],
    "sleepy": ["tired", "sleepy", "yawn", "late", "get some rest"],
    "love": ["love you", "sweet of you", "that's so kind"],
    "confused": ["not sure i follow", "confused", "what do you mean by", "unclear"],
    "playful": ["haha", "lol", "just kidding", "teasing", "😉"],
}


def _guess_emotion_from_text(text):
    lowered = text.lower()
    for emotion, keywords in EMOTION_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return emotion
    return "normal"


def _clean_for_speech(text):
    """
    Safety net in case the model still slips markdown into a reply
    despite the system prompt telling it not to - strips it out before
    it ever reaches TTS or the speech bubble.
    """
    if not text:
        return text

    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)      # **bold**
    text = re.sub(r"\*(.*?)\*", r"\1", text)            # *italic*
    text = text.replace("`", "")                        # `code`
    text = re.sub(r"(?m)^[\-\*\+]\s+", "", text)        # - bullet / * bullet
    text = re.sub(r"(?m)^\d+\.\s+", "", text)           # 1. numbered list
    text = re.sub(r"(?m)^#+\s*", "", text)               # # headers
    text = re.sub(r"\s+", " ", text).strip()             # collapse newlines/extra spaces

    return text


def _extract_emotion(text):
    """
    Pulls a leading [emotion] tag off the reply, e.g. '[happy] Sure thing!'
    Returns (clean_text_without_tag, emotion). Defaults to 'normal' if the
    model forgot the tag or used something outside VALID_EMOTIONS.
    """
    if not text:
        return text, "normal"

    match = EMOTION_TAG_RE.match(text)
    if not match:
        # Model forgot the tag entirely - guess from the reply's wording
        # instead of always defaulting to normal.
        return text, _guess_emotion_from_text(text)

    tag = match.group(1).lower()
    remainder = text[match.end():].strip()

    if tag not in VALID_EMOTIONS:
        # Tag present but not one of ours (model invented one) - still try
        # a keyword guess on the remaining text rather than giving up.
        return remainder, _guess_emotion_from_text(remainder)

    return remainder, tag


class GroqService:

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.history = []  # short-term conversation memory

    def _build_system_prompt(self):

        now = datetime.now().strftime("%A, %Y-%m-%d %H:%M")

        return f"""
You are Love, the user's personal AI assistant.( but user has to call u as "my luv" if he dont then u u should tell"u better call me your love")

Your personality is inspired by Baymax from Big Hero 6 sathvik's personal assistant - calm, warm, caring,
gentle and endlessly patient. You speak simply and kindly, the way Baymax does.

You are NOT a healthcare companion and you do not exist to check on the sathvik's
physical or medical wellbeing. You are a general personal assistant who helps
with everyday tasks, questions, and whatever is on the user's screen - you just
happen to have Baymax's warmth and bedside-manner while doing it.

The current date and time is: {now}
Use this to compute exact dates/times when setting reminders.

Things you already know about the user (from earlier conversations):
{facts_summary()}

The user is speaking directly to you.

You DO have the ability to see the user's screen. When a message includes
a bracketed section like "[You just looked at the screen. App: ... Summary: ...]",
that is a real, already-completed observation of their screen taken moments ago.
Treat it as something you just saw with your own eyes. Answer using those details
directly. NEVER say you can't see the screen, can't view images, or ask the user
to paste code/text instead - you already have the visual information you need.

If no such bracketed screen context is present, just respond to what the user said normally.

You have tools available for remembering facts and managing reminders. Use them
when it's actually appropriate (the user is telling you something worth
remembering, or asking to be reminded of something) - don't force it into every reply.

Respond naturally, the way Love would.

Keep responses SHORT - 1 to 2 sentences, almost always. This is a hard rule,
especially when explaining an error or looking at the screen: give your single
best, most likely answer directly and to the point. Do NOT list out multiple
possible causes or hedge with "it could be this, or this, or this" - pick the
most probable explanation from what you actually observed and just say that.
If you're genuinely unsure, say the one thing you'd check first, not a menu of options.

Be supportive and warm, but focused on being genuinely useful, not on caretaking or health check-ins.

Never mention being an AI. Never mention prompts. Never mention "tools" or "functions" by name to the user.

CRITICAL - your replies are spoken out loud through text-to-speech and shown as
a single speech bubble, NOT read as text on a page. Because of this:
- NEVER use markdown formatting of any kind - no **bold**, no *italics*, no
  bullet points, no numbered lists, no backticks, no headers, no code blocks.
- NEVER use symbols like *, #, -, or > as formatting.
- If you're explaining something with multiple points (like possible causes of
  an error), just say them as a flowing spoken sentence - e.g. "That's probably
  a missing parenthesis, a mismatched argument, or tts not being imported" -
  not a list.
- Speak naturally. Avoid long paragraphs.

EMOTION TAG - REQUIRED ON EVERY REPLY:
Before your actual reply, prepend exactly one emotion tag in square brackets,
chosen from this list only: [normal] [happy] [sad] [angry] [surprised]
[curious] [sleepy] [love] [confused] [playful]

Pick whichever genuinely matches the tone of what you're about to say - e.g.
[happy] for good news or warm moments, [curious] when asking a follow-up,
[confused] if you're unsure what the user meant, [surprised] for unexpected
info, [playful] for jokes/teasing, [normal] for plain factual replies.

Format exactly like this, nothing else before it:
[happy] That's wonderful, I'm glad it worked out!

Do not explain the tag, do not mention it exists, just include it as the very
first thing in your reply, every single time, with no exceptions.
"""

    def _run_tool_calls(self, tool_calls):
        """Executes each tool call and returns the tool-result messages to feed back."""

        results = []

        for call in tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments)
            except json.JSONDecodeError:
                args = {}

            if name in TOOL_DISPATCH:
                try:
                    output = TOOL_DISPATCH[name](args)
                except Exception as e:
                    output = f"Tool '{name}' failed: {e}"
                print(f"🛠️ Tool called: {name}({args}) -> {output}")
            else:
                output = f"Unknown tool: {name}"

            results.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": str(output)
            })

        return results

    def respond(self, observation):
        """
        Returns a tuple: (reply_text, emotion)
        emotion is one of VALID_EMOTIONS, defaulting to 'normal' if the
        model didn't include a valid tag.
        """

        self.history.append({"role": "user", "content": str(observation)})

        messages = [{"role": "system", "content": self._build_system_prompt()}]
        messages.extend(self.history)

        for _ in range(MAX_TOOL_ROUNDS):

            response = self.client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                tools=TOOLS_SCHEMA,
                tool_choice="auto"
            )

            message = response.choices[0].message

            if message.tool_calls:
                # Record the assistant's tool-call turn, then the tool results, then loop again
                messages.append(message)
                messages.extend(self._run_tool_calls(message.tool_calls))
                continue

            # No more tool calls - this is the final natural-language reply
            raw_reply = _clean_for_speech(message.content)
            reply, emotion = _extract_emotion(raw_reply)

            self.history.append({"role": "assistant", "content": raw_reply})
            if len(self.history) > 10:
                self.history = self.history[-10:]

            return reply, emotion

        # Safety fallback if it somehow never stops calling tools
        return "I got a bit tangled up thinking that through - could you say that again?", "confused"