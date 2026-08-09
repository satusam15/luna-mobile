const baymax = document.getElementById("baymax");
const speechBubble = document.getElementById("speech-bubble");
const eyesContainer = document.getElementById("eyes");
const eyeLeft = document.querySelector(".eye-left");
const eyeRight = document.querySelector(".eye-right");

let speechTimeout = null;

// Blinking is a pure CSS animation on the eye layer, not a second full-body
// image - so proportions can never mismatch, no matter what the body art looks like.
function blink() {

    eyeLeft.classList.add("blink");
    eyeRight.classList.add("blink");

    setTimeout(() => {
        eyeLeft.classList.remove("blink");
        eyeRight.classList.remove("blink");
    }, 180);

}

function startBlinking() {

    const randomTime = Math.random() * 4000 + 3000;
    // Between 3 and 7 seconds

    setTimeout(() => {

        blink();

        startBlinking();

    }, randomTime);

}

startBlinking();

// Swaps the eye layer's color/animation to reflect what the backend is doing.
// Called from the websocket handler below whenever a "state" message arrives.
function setState(state) {

    eyesContainer.classList.remove(
        "state-listening",
        "state-thinking",
        "state-looking",
        "state-speaking",
        "state-interrupted"
    );

    if (state && state !== "idle") {
        eyesContainer.classList.add("state-" + state);
    }

}

// ----------------------------
// Connect to Baymax Brain
// ----------------------------
function showSpeech(text){

    speechBubble.innerText = text;

    speechBubble.classList.add("show");

    baymax.classList.add("talking");

    clearTimeout(speechTimeout);

    speechTimeout = setTimeout(() => {

        speechBubble.classList.remove("show");

        baymax.classList.remove("talking");

    },5000);

}

const socket = new WebSocket("ws://localhost:8765");

socket.onopen = () => {

    console.log("🟢 Connected to Baymax Brain");

};

socket.onmessage = (event) => {

    let data;

    try {
        data = JSON.parse(event.data);
    } catch (e) {
        // Fallback for any plain-text message that isn't JSON
        showSpeech(event.data);
        return;
    }

    if (data.type === "state") {
        console.log("👁️", data.state);
        setState(data.state);
    } else if (data.type === "speech") {
        console.log("💬", data.text);
        showSpeech(data.text);
    }

};

socket.onclose = () => {

    console.log("🔴 Connection Closed");

};

socket.onerror = (error) => {

    console.log(error);

};