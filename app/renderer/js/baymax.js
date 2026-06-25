const baymax = document.getElementById("baymax");

const OPEN = "../assets/characters/baymax/idle_open.png";
const CLOSED = "../assets/characters/baymax/idle_closed.png";

function blink() {

    baymax.src = CLOSED;

    setTimeout(() => {
        baymax.src = OPEN;
    }, 120);

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