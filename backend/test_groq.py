from brain.groq_service import GroqService

groq = GroqService()

mock_json = {
    "application": "Visual Studio Code",
    "activity": "Debugging a WebSocket issue",
    "visible_error": True,
    "needs_attention": True,
    "summary": "The user is debugging a JavaScript WebSocket connection."
}

reply = groq.respond(mock_json)

print(reply)