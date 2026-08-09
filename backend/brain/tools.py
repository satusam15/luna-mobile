from memory.memory_store import remember
from planner.reminder_store import set_reminder, list_reminders

# Groq function-calling schema (OpenAI-compatible format)
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save a fact about the user for later, so Luna can recall it in future conversations. Use this when the user tells you something worth remembering long-term (preferences, names, ongoing situations) - not for one-off, throwaway details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": "The fact to remember, written clearly and in third person, e.g. 'User's college is MSRIT' or 'User prefers short answers'."
                    }
                },
                "required": ["fact"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Set a reminder for the user at a specific date and time. Compute the exact date/time yourself using the current date/time given in your system prompt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "What to remind the user about."
                    },
                    "when": {
                        "type": "string",
                        "description": "Exact date and time in the format YYYY-MM-DD HH:MM (24-hour clock)."
                    }
                },
                "required": ["text", "when"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "List the user's currently active (not yet triggered) reminders.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

# Maps a tool name to the real Python function that does the work
TOOL_DISPATCH = {
    "remember": lambda args: remember(args["fact"]),
    "set_reminder": lambda args: set_reminder(args["text"], args["when"]),
    "list_reminders": lambda args: list_reminders(),
}
