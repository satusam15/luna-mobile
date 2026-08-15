// ===================================================================
// Luna frontend — cute face (eyes + eyebrows + mouth) + WS
// ===================================================================

const canvas = document.getElementById("face");
const ctx = canvas.getContext("2d");
const overlay = document.getElementById("start-overlay");

function resize() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}
resize();
window.addEventListener("resize", resize);

let pipelineState = "idle";
let emotion = "normal";
let audioPlaying = false;

// Safety net only - reverts emotion/state if audio never arrives for some
// reason (error, empty reply, etc). Real reversion happens on audio 'ended'.
const EMOTION_SAFETY_MS = 6000;
let emotionSafetyTimer = null;

let blinkTimer = 0;
let nextBlinkAt = 2000 + Math.random() * 3000;
let talkPhase = 0;

function setPipelineState(s) {
  // Ignore a premature "idle" from the backend while audio is still
  // actually playing on this device - the backend sends "idle" right
  // after handing off audio bytes, before playback has even started.
  if (audioPlaying && s === "idle") return;
  pipelineState = s;
}

function setEmotion(e) {
  emotion = e;

  if (emotionSafetyTimer) clearTimeout(emotionSafetyTimer);
  if (e !== "normal") {
    emotionSafetyTimer = setTimeout(() => {
      emotion = "normal";
    }, EMOTION_SAFETY_MS);
  }
}

function revertToIdleNow() {
  audioPlaying = false;
  pipelineState = "idle";
  emotion = "normal";
  if (emotionSafetyTimer) clearTimeout(emotionSafetyTimer);
}

// -------------------------------------------------------------
// Per-emotion look: eye squint, eyebrow angle/position, mouth type
// -------------------------------------------------------------
function getLook(em) {
  switch (em) {
    case "happy":
      return { squint: 0.4, browAngle: -0.25, browLift: -0.12, mouth: "smile-big" };
    case "sad":
      return { squint: 0.1, browAngle: 0.35, browLift: 0.05, mouth: "frown" };
    case "angry":
      return { squint: 0.25, browAngle: 0.5, browLift: -0.02, mouth: "flat-tight" };
    case "surprised":
      return { squint: -0.2, browAngle: -0.05, browLift: -0.22, mouth: "o" };
    case "curious":
      return { squint: 0.05, browAngle: -0.15, browLift: -0.15, mouth: "smirk", asymmetric: true };
    case "sleepy":
      return { squint: 0.78, browAngle: 0.1, browLift: 0.08, mouth: "small-o" };
    case "love":
      return { squint: 0.15, browAngle: -0.15, browLift: -0.08, mouth: "smile-soft" };
    case "confused":
      return { squint: 0.08, browAngle: -0.3, browLift: -0.05, mouth: "wavy", asymmetric: true };
    case "playful":
      return { squint: 0.25, browAngle: -0.3, browLift: -0.18, mouth: "smirk", wink: true };
    default:
      return { squint: 0.1, browAngle: -0.05, browLift: -0.05, mouth: "smile-soft" };
  }
}

const EYE_COLOR = "#eafcff";
const BROW_COLOR = "#eafcff";
const MOUTH_COLOR = "#eafcff";
const GLOW = "#7fe8ff";

function draw(dt, tNow) {
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const cx = w / 2, cy = h / 2;
  const baseSize = Math.min(w, h) * 0.2;
  const spacing = baseSize * 1.65;

  const idleBob = pipelineState === "idle" ? Math.sin(tNow / 900) * 5 : 0;

  blinkTimer += dt;
  let blinkScale = 1;
  if (emotion !== "sleepy") {
    if (blinkTimer > nextBlinkAt) {
      const t = blinkTimer - nextBlinkAt;
      if (t < 100) blinkScale = 1 - t / 100;
      else if (t < 200) blinkScale = (t - 100) / 100;
      else {
        blinkTimer = 0;
        nextBlinkAt = 2000 + Math.random() * 3000;
      }
    }
  }

  const look = getLook(emotion);

  let stateColor = EYE_COLOR;
  let driftX = 0, driftY = 0;
  let pulse = 1;

  if (pipelineState === "listening") {
    stateColor = "#8dffb0";
    pulse = 1 + Math.sin(tNow / 250) * 0.04;
  } else if (pipelineState === "thinking") {
    stateColor = "#ffe08d";
    driftX = Math.sin(tNow / 450) * (baseSize * 0.15);
  } else if (pipelineState === "looking") {
    stateColor = "#c58dff";
    driftX = Math.sin(tNow / 300) * (baseSize * 0.25);
    driftY = Math.cos(tNow / 300) * (baseSize * 0.06);
  } else if (pipelineState === "speaking") {
    talkPhase += dt / 70;
  }

  ctx.shadowColor = GLOW;
  ctx.shadowBlur = 28;

  [-1, 1].forEach((side) => {
    const asym = look.asymmetric && side === 1 ? 0.2 : 0;
    const isWinkEye = look.wink && side === 1;

    const ex = cx + side * spacing + driftX;
    const ey = cy - baseSize * 0.2 + driftY + idleBob;

    const ew = baseSize * pulse;
    let eh = baseSize * pulse * 1.2;

    let totalSquint = Math.min(0.95, look.squint + asym);
    if (isWinkEye) {
      const winkCycle = (tNow / 2200) % 1;
      if (winkCycle < 0.18) totalSquint = 0.95;
    }
    eh *= (1 - totalSquint) * Math.max(0.05, blinkScale);

    ctx.fillStyle = stateColor;
    roundRect(ctx, ex - ew / 2, ey - eh / 2, ew, eh, Math.min(ew, eh) * 0.4);
    ctx.fill();

    const bx = ex;
    const by = ey - eh / 2 - baseSize * (0.5 + look.browLift);
    const bw = ew * 0.8;
    const angle = look.browAngle * side * -1;

    ctx.save();
    ctx.translate(bx, by);
    ctx.rotate(angle);
    ctx.strokeStyle = BROW_COLOR;
    ctx.lineWidth = baseSize * 0.09;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(-bw / 2, 0);
    ctx.quadraticCurveTo(0, -bw * 0.14, bw / 2, 0);
    ctx.stroke();
    ctx.restore();
  });

  drawMouth(ctx, cx, cy + baseSize * 1.05 + idleBob, baseSize, look.mouth, talkPhase, pipelineState);

  ctx.shadowBlur = 0;
}

function drawMouth(c, mx, my, size, type, talkPhase, pipelineState) {
  c.save();
  c.translate(mx, my);
  c.strokeStyle = MOUTH_COLOR;
  c.fillStyle = MOUTH_COLOR;
  c.lineWidth = size * 0.1;
  c.lineCap = "round";

  const talking = pipelineState === "speaking";
  const talkAmp = talking ? (0.3 + 0.4 * Math.abs(Math.sin(talkPhase))) : 0;

  switch (type) {
    case "smile-big":
      c.beginPath();
      c.moveTo(-size * 0.4, 0);
      c.quadraticCurveTo(0, size * (0.55 + talkAmp * 0.5), size * 0.4, 0);
      c.stroke();
      break;
    case "smile-soft":
      c.beginPath();
      c.moveTo(-size * 0.3, 0);
      c.quadraticCurveTo(0, size * (0.3 + talkAmp * 0.4), size * 0.3, 0);
      c.stroke();
      break;
    case "frown":
      c.beginPath();
      c.moveTo(-size * 0.3, size * 0.15);
      c.quadraticCurveTo(0, -size * 0.15, size * 0.3, size * 0.15);
      c.stroke();
      break;
    case "flat-tight":
      c.beginPath();
      c.moveTo(-size * 0.25, 0);
      c.lineTo(size * 0.25, 0);
      c.stroke();
      break;
    case "o":
    case "small-o": {
      const r = type === "o" ? size * (0.16 + talkAmp * 0.15) : size * 0.09;
      c.beginPath();
      c.ellipse(0, 0, r * 0.75, r, 0, 0, Math.PI * 2);
      c.fill();
      break;
    }
    case "smirk":
      c.beginPath();
      c.moveTo(-size * 0.28, size * 0.05);
      c.quadraticCurveTo(0, size * 0.1, size * 0.15, -size * 0.12);
      c.stroke();
      break;
    case "wavy":
      c.beginPath();
      c.moveTo(-size * 0.3, 0);
      c.quadraticCurveTo(-size * 0.15, size * 0.15, 0, 0);
      c.quadraticCurveTo(size * 0.15, -size * 0.15, size * 0.3, 0);
      c.stroke();
      break;
    default:
      c.beginPath();
      c.moveTo(-size * 0.25, 0);
      c.quadraticCurveTo(0, size * 0.2, size * 0.25, 0);
      c.stroke();
  }

  c.restore();
}

function roundRect(c, x, y, w, h, r) {
  r = Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2);
  c.beginPath();
  c.moveTo(x + r, y);
  c.arcTo(x + w, y, x + w, y + h, r);
  c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r);
  c.arcTo(x, y, x + w, y, r);
  c.closePath();
}

let lastT = performance.now();
function loop(t) {
  const dt = t - lastT;
  lastT = t;
  draw(dt, t);
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

// -------------------------------------------------------------
// WebSocket
// -------------------------------------------------------------
const WS_URL = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";
let ws = null;

function connectWS() {
  ws = new WebSocket(WS_URL);

  ws.onmessage = async (event) => {
    const msg = JSON.parse(event.data);

    if (msg.type === "state") {
      setPipelineState(msg.state);
    } else if (msg.type === "speech") {
      if (msg.emotion) setEmotion(msg.emotion);
      console.log("Luna:", msg.text, "(" + msg.emotion + ")");
    } else if (msg.type === "audio") {
      playAudio(msg.data, msg.format);
    }
  };

  ws.onclose = () => {
    setTimeout(connectWS, 1500);
  };
}

function playAudio(b64data, format) {
  // Reuse one persistent <audio> element instead of creating a new one each
  // time - mobile browsers only allow programmatic playback on an element
  // that was "unlocked" by a real tap, and a fresh Audio() object each turn
  // loses that unlock. See unlockAudioPlayback() below.
  audioPlayer.src = `data:audio/${format};base64,${b64data}`;

  audioPlayer.play().catch((e) => {
    console.warn("Audio play blocked:", e);
    revertToIdleNow();
  });
}

const audioPlayer = new Audio();
audioPlayer.addEventListener("playing", () => {
  audioPlaying = true;
  pipelineState = "speaking";
});
audioPlayer.addEventListener("ended", () => {
  revertToIdleNow();
});
audioPlayer.addEventListener("error", () => {
  revertToIdleNow();
});

// Must be called synchronously inside a real user tap/click handler - this
// "unlocks" audioPlayer so later programmatic .play() calls (triggered by
// WebSocket messages, not directly by a tap) are allowed on iOS/Android.
function unlockAudioPlayback() {
  audioPlayer.muted = true;
  audioPlayer.play().then(() => {
    audioPlayer.pause();
    audioPlayer.currentTime = 0;
    audioPlayer.muted = false;
  }).catch(() => {
    audioPlayer.muted = false;
  });
}

// -------------------------------------------------------------
// Mic capture with noise-calibrated silence-based turn detection
// -------------------------------------------------------------
let mediaStream = null;
let audioCtx = null;
let analyser = null;
let recorder = null;
let recordedChunks = [];
let speaking = false;
let silenceStart = null;

const SILENCE_MS = 1000;
const MIN_VOICED_MS = 400; // discard the clip entirely if less than this was actual speech
let voicedMs = 0;
let noiseFloor = 0.01;
let speechThreshold = 0.025; // recalculated after calibration

let camStream = null;
let camVideoEl = null;

async function initMedia() {
  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });

  try {
    camStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
    camVideoEl = document.createElement("video");
    camVideoEl.srcObject = camStream;
    camVideoEl.play();
  } catch (e) {
    console.warn("Camera unavailable:", e);
  }

  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const source = audioCtx.createMediaStreamSource(mediaStream);
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 512;
  source.connect(analyser);

  await calibrateNoiseFloor();

  startListenLoop();
  monitorMic();
}

// Samples ambient room noise for ~1s right after permissions are granted,
// so the "stop listening" threshold adapts to this specific room/device
// instead of using one fixed number for everyone.
function calibrateNoiseFloor() {
  return new Promise((resolve) => {
    const data = new Uint8Array(analyser.fftSize);
    const samples = [];
    const start = performance.now();

    function sample() {
      analyser.getByteTimeDomainData(data);
      let sumSquares = 0;
      for (let i = 0; i < data.length; i++) {
        const v = (data[i] - 128) / 128;
        sumSquares += v * v;
      }
      samples.push(Math.sqrt(sumSquares / data.length));

      if (performance.now() - start < 900) {
        requestAnimationFrame(sample);
      } else {
        const avg = samples.reduce((a, b) => a + b, 0) / samples.length;
        noiseFloor = avg;
        // Threshold sits comfortably above the measured noise floor so
        // steady background hum/hiss doesn't keep "speaking" true forever.
        speechThreshold = Math.max(0.02, avg * 2.5 + 0.012);
        resolve();
      }
    }
    sample();
  });
}

function monitorMic() {
  const data = new Uint8Array(analyser.fftSize);
  let lastTick = performance.now();

  function tick() {
    const now = performance.now();
    const frameDt = now - lastTick;
    lastTick = now;

    analyser.getByteTimeDomainData(data);
    let sumSquares = 0;
    for (let i = 0; i < data.length; i++) {
      const v = (data[i] - 128) / 128;
      sumSquares += v * v;
    }
    const rms = Math.sqrt(sumSquares / data.length);

    if (rms > speechThreshold) {
      speaking = true;
      silenceStart = null;
      voicedMs += frameDt;
      if (pipelineState === "idle") setPipelineState("listening");
    } else if (speaking) {
      if (silenceStart === null) silenceStart = performance.now();
      if (performance.now() - silenceStart > SILENCE_MS) {
        speaking = false;
        silenceStart = null;
        stopAndSendTurn();
      }
    }

    requestAnimationFrame(tick);
  }
  tick();
}

function startListenLoop() {
  recordedChunks = [];
  voicedMs = 0;
  recorder = new MediaRecorder(mediaStream, { mimeType: pickMime() });
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) recordedChunks.push(e.data);
  };
  recorder.start();
}

function pickMime() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  for (const c of candidates) {
    if (MediaRecorder.isTypeSupported(c)) return c;
  }
  return "";
}

async function stopAndSendTurn() {
  if (!recorder || recorder.state === "inactive") return;

  const stopped = new Promise((resolve) => {
    recorder.onstop = resolve;
  });
  recorder.stop();
  await stopped;

  // Not enough real speech in this clip - almost certainly a noise blip
  // that would just cause the STT model to hallucinate a phrase. Discard
  // it and go straight back to listening instead of sending it.
  if (voicedMs < MIN_VOICED_MS) {
    voicedMs = 0;
    setPipelineState("idle");
    startListenLoop();
    return;
  }
  voicedMs = 0;

  const blob = new Blob(recordedChunks, { type: recorder.mimeType });
  const format = recorder.mimeType.includes("mp4") ? "mp4" : "webm";
  const base64 = await blobToBase64(blob);

  const payload = { type: "audio", data: base64, format };

  const frame = await maybeCaptureFrame();
  if (frame) payload.image = frame;

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  }

  startListenLoop();
}

async function maybeCaptureFrame() {
  if (!camVideoEl || camVideoEl.readyState < 2) return null;

  const c = document.createElement("canvas");
  c.width = camVideoEl.videoWidth;
  c.height = camVideoEl.videoHeight;
  const cctx = c.getContext("2d");
  cctx.drawImage(camVideoEl, 0, 0);

  return new Promise((resolve) => {
    c.toBlob(async (blob) => {
      if (!blob) return resolve(null);
      resolve(await blobToBase64(blob));
    }, "image/jpeg", 0.8);
  });
}

function blobToBase64(blob) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result.split(",")[1]);
    reader.readAsDataURL(blob);
  });
}

// -------------------------------------------------------------
// Wake lock — keep screen on
// -------------------------------------------------------------
let wakeLock = null;
async function requestWakeLock() {
  try {
    wakeLock = await navigator.wakeLock.request("screen");
    document.addEventListener("visibilitychange", async () => {
      if (wakeLock !== null && document.visibilityState === "visible") {
        wakeLock = await navigator.wakeLock.request("screen");
      }
    });
  } catch (e) {
    console.warn("Wake lock unavailable:", e);
  }
}

// -------------------------------------------------------------
// Start
// -------------------------------------------------------------
overlay.addEventListener("click", async () => {
  overlay.style.display = "none";
  unlockAudioPlayback();
  try {
    await initMedia();
    await requestWakeLock();
    connectWS();
    if (document.documentElement.requestFullscreen) {
      await document.documentElement.requestFullscreen().catch(() => {});
    }
    if (screen.orientation && screen.orientation.lock) {
      screen.orientation.lock("landscape").catch(() => {
        // Unsupported/denied - the CSS rotate fallback in index.html
        // handles this case visually instead.
      });
    }
  } catch (e) {
    console.error("Failed to start Luna:", e);
    overlay.style.display = "flex";
    overlay.textContent = permissionErrorMessage(e);
  }
});

function permissionErrorMessage(e) {
  if (e.name === "NotAllowedError" || e.name === "SecurityError") {
    return "mic/camera blocked — tap the 🔒 icon next to the address bar, allow mic + camera, then reload";
  }
  if (e.name === "NotFoundError") {
    return "no microphone/camera found on this device — tap to retry";
  }
  if (e.name === "NotReadableError") {
    return "mic/camera already in use by another app — close it and tap to retry";
  }
  return "couldn't start — tap to retry (" + (e.message || e.name || "unknown error") + ")";
}