import json
import os
from datetime import datetime

REMINDER_FILE = os.path.join(os.path.dirname(__file__), "reminders.json")


def _load():
    if not os.path.exists(REMINDER_FILE):
        return []
    with open(REMINDER_FILE, "r") as f:
        return json.load(f)


def _save(reminders):
    with open(REMINDER_FILE, "w") as f:
        json.dump(reminders, f, indent=2)


def set_reminder(text: str, when: str):
    """
    when must be an ISO-ish string like "2026-08-05 18:00"
    (the LLM is given the current date/time in its system prompt so it can compute this)
    """
    reminders = _load()
    reminders.append({"text": text, "when": when, "done": False})
    _save(reminders)
    return f"Reminder set: '{text}' at {when}"


def list_reminders():
    reminders = [r for r in _load() if not r["done"]]
    if not reminders:
        return "No active reminders."
    return "\n".join(f"- {r['text']} at {r['when']}" for r in reminders)


def get_due_reminders():
    """Called periodically by main.py to check what needs announcing now."""
    reminders = _load()
    now = datetime.now()
    due = []

    for r in reminders:
        if r["done"]:
            continue
        try:
            reminder_time = datetime.strptime(r["when"], "%Y-%m-%d %H:%M")
        except ValueError:
            continue

        if reminder_time <= now:
            due.append(r)
            r["done"] = True

    if due:
        _save(reminders)

    return due
