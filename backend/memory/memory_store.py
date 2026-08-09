import json
import os

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "facts.json")


def _load():
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)


def _save(facts):
    with open(MEMORY_FILE, "w") as f:
        json.dump(facts, f, indent=2)


def remember(fact: str):
    facts = _load()
    facts.append(fact)
    _save(facts)
    return f"Got it, I'll remember: {fact}"


def get_all_facts():
    return _load()


def facts_summary():
    facts = _load()
    if not facts:
        return "No stored facts yet."
    return "\n".join(f"- {f}" for f in facts)
