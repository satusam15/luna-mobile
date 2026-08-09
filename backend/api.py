from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from state.message_state import latest_message

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from state.message_state import latest_message


@app.get("/")
def home():
    return {
        "message": "CompanionAI Backend Running"
    }


@app.get("/message")
def get_message():

    import json

    with open("state/message.json", "r") as file:
        return json.load(file)