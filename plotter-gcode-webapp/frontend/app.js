const API_URL = "http://localhost:8000/generate";

const tabs = document.querySelectorAll(".tab");
const uploadTab = document.getElementById("upload-tab");
const drawTab = document.getElementById("draw-tab");
const fileInput = document.getElementById("fileInput");
const imagePreview = document.getElementById("imagePreview");
const generateBtn = document.getElementById("generateBtn");
const simulateBtn = document.getElementById("simulateBtn");
const clearCanvasBtn = document.getElementById("clearCanvasBtn");
const statusBox = document.getElementById("status");
const metaBox = document.getElementById("metaBox");

const canvas = document.getElementById("drawCanvas");
const ctx = canvas.getContext("2d");

const simCanvas = document.getElementById("simCanvas");
const simCtx = simCanvas.getContext("2d");
const simPlayBtn = document.getElementById("simPlayBtn");
const simPauseBtn = document.getElementById("simPauseBtn");
const simResetBtn = document.getElementById("simResetBtn");
const simSpeed = document.getElementById("simSpeed");
const simInfo = document.getElementById("simInfo");

let currentMode = "upload";
let isDrawing = false;
let lastPoint = null;
let lastGcodeText = "";

let simSegments = [];
let simIndex = 0;
let simPlaying = false;
let simScale = 1;
let simOffsetX = 20;
let simOffsetY = 20;
let simBounds = { minX: 0, minY: 0, maxX: 100, maxY: 100 };

function setStatus(text) {
  statusBox.textContent = text;
}

function activateTab(mode) {
  currentMode = mode;
  tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === mode));
  uploadTab.classList.toggle("active", mode === "upload");
  drawTab.classList.toggle("active", mode === "draw");
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => activateTab(tab.dataset.tab));
});

function initCanvas() {
  ctx.fillStyle = "white";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = "black";
  ctx.lineWidth = 4;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
}

function initSimCanvas() {
  simCtx.fillStyle = "white";
  simCtx.fillRect(0, 0, simCanvas.width, simCanvas.height);
  simCtx.strokeStyle = "#222";
  simCtx.lineWidth = 1;
}

function getCanvasPoint(event) {
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  return {
    x: (event.clientX - rect.left) * scaleX,
    y: (event.clientY - rect.top) * scaleY,
  };
}

canvas.addEventListener("pointerdown", (event) => {
  if (currentMode !== "draw") return;
  isDrawing = true;
  lastPoint = getCanvasPoint(event);
});

canvas.addEventListener("pointermove", (event) => {
  if (!isDrawing || currentMode !== "draw") return;
  const point = getCanvasPoint(event);
  ctx.beginPath();
  ctx.moveTo(lastPoint.x, lastPoint.y);
  ctx.lineTo(point.x, point.y);
  ctx.stroke();
  lastPoint = point;
});

["pointerup", "pointerleave", "pointercancel"].forEach((eventName) => {
  canvas.addEventListener(eventName, () => {
    isDrawing = false;
    lastPoint = null;
  });
});

clearCanvasBtn.addEventListener("click", () => {
  initCanvas();
  setStatus("Canvas wyczyszczony.");
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  if (!file) return;
  const url = URL.createObjectURL(file);
  imagePreview.src = url;
  imagePreview.style.display = "block";
});

function getFormValue(id) {
  return document.getElementById(id).value;
}

function getCheckboxValue(id) {
  return document.getElementById(id).checked;
}

async function canvasToBlob() {
  return await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}

async function getInputFile() {
  if (currentMode === "upload") {
    return fileInput.files?.[0] || null;
  }
  const blob = await canvasToBlob();
  return new File([blob], "drawing.png", { type: "image/png" });
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function parseGcodeToSegments(gcodeText) {
  const lines = gcodeText.split(/\r?\n/);
  let x = 0;
  let y = 0;
  let penDown = false;
  const segments = [];

  for (const rawLine of lines) {
    const line = rawLine.trim().toUpperCase();
    if (!line || line.startsWith(";")) continue;

    if (line.startsWith("M3") || (line.startsWith("M280") && line.includes("S90"))) {
      penDown = true;
      continue;
    }
    if (line.startsWith("M5") || (line.startsWith("M280") && line.includes("S50"))) {
      penDown = false;
      continue;
    }

    if (line.startsWith("G0") || line.startsWith("G1")) {
      const xMatch = line.match(/X(-?\d+(?:\.\d+)?)/);
      const yMatch = line.match(/Y(-?\d+(?:\.\d+)?)/);
      const newX = xMatch ? parseFloat(xMatch[1]) : x;
      const newY = yMatch ? parseFloat(yMatch[1]) : y;
      const draw = line.startsWith("G1") && penDown;

      segments.push({ x1: x, y1: y, x2: newX, y2: newY, draw });
      x = newX;
      y = newY;
    }
  }

  return segments.filter((seg) => !(seg.x1 === seg.x2 && seg.y1 === seg.y2));
}

function computeBounds(segments) {
  if (!segments.length) {
    return { minX: 0, minY: 0, maxX: 100, maxY: 100 };
  }

  const xs = [];
  const ys = [];
  for (const s of segments) {
    xs.push(s.x1, s.x2);
    ys.push(s.y1, s.y2);
  }

  return {
    minX: Math.min(...xs),
    minY: Math.min(...ys),
    maxX: Math.max(...xs),
    maxY: Math.max(...ys),
  };
}

function setupSimulationView() {
  simBounds = computeBounds(simSegments);
  const width = Math.max(1, simBounds.maxX - simBounds.minX);
  const height = Math.max(1, simBounds.maxY - simBounds.minY);
  const padding = 30;

  simScale = Math.min(
    (simCanvas.width - padding * 2) / width,
    (simCanvas.height - padding * 2) / height
  );

  simOffsetX = padding - simBounds.minX * simScale;
  simOffsetY = padding - simBounds.minY * simScale;
}

function transformPoint(x, y) {
  return {
    x: x * simScale + simOffsetX,
    y: simCanvas.height - (y * simScale + simOffsetY),
  };
}

function drawSimulationFrame() {
  initSimCanvas();

  simCtx.strokeStyle = "#dddddd";
  simCtx.lineWidth = 1;
  for (let i = 0; i < simIndex; i++) {
    const s = simSegments[i];
    const p1 = transformPoint(s.x1, s.y1);
    const p2 = transformPoint(s.x2, s.y2);
    simCtx.beginPath();
    simCtx.moveTo(p1.x, p1.y);
    simCtx.lineTo(p2.x, p2.y);
    simCtx.stroke();
  }

  simCtx.strokeStyle = "#111111";
  simCtx.lineWidth = 2;
  for (let i = 0; i < simIndex; i++) {
    const s = simSegments[i];
    if (!s.draw) continue;
    const p1 = transformPoint(s.x1, s.y1);
    const p2 = transformPoint(s.x2, s.y2);
    simCtx.beginPath();
    simCtx.moveTo(p1.x, p1.y);
    simCtx.lineTo(p2.x, p2.y);
    simCtx.stroke();
  }

  if (simIndex < simSegments.length) {
    const s = simSegments[simIndex];
    const p = transformPoint(s.x2, s.y2);
    simCtx.fillStyle = "#e53935";
    simCtx.beginPath();
    simCtx.arc(p.x, p.y, 4, 0, Math.PI * 2);
    simCtx.fill();
  }

  const drawn = simSegments.slice(0, simIndex).filter((s) => s.draw).length;
  simInfo.textContent = `Segmenty: ${simSegments.length}, narysowane: ${drawn}, pozycja: ${Math.min(simIndex, simSegments.length)}/${simSegments.length}`;
}

function resetSimulation() {
  simIndex = 0;
  simPlaying = false;
  drawSimulationFrame();
}

function stepSimulation() {
  if (!simPlaying) return;

  const speed = Number(simSpeed.value);
  simIndex = Math.min(simSegments.length, simIndex + speed);
  drawSimulationFrame();

  if (simIndex >= simSegments.length) {
    simPlaying = false;
    return;
  }

  requestAnimationFrame(stepSimulation);
}

function loadSimulation(gcodeText) {
  simSegments = parseGcodeToSegments(gcodeText);
  setupSimulationView();
  resetSimulation();
}

simPlayBtn.addEventListener("click", () => {
  if (!simSegments.length) {
    simInfo.textContent = "Najpierw wygeneruj G-code.";
    return;
  }

  if (simIndex >= simSegments.length) {
    simIndex = 0;
  }

  simPlaying = true;
  requestAnimationFrame(stepSimulation);
});

simPauseBtn.addEventListener("click", () => {
  simPlaying = false;
});

simResetBtn.addEventListener("click", () => {
  resetSimulation();
});

simulateBtn.addEventListener("click", () => {
  if (!lastGcodeText) {
    setStatus("Najpierw wygeneruj G-code.");
    return;
  }

  loadSimulation(lastGcodeText);
  setStatus("Załadowano G-code do symulatora.");
});

async function generateGcode() {
  try {
    setStatus("Generowanie G-code...");
    metaBox.textContent = "";

    const inputFile = await getInputFile();
    if (!inputFile) {
      setStatus("Wybierz plik albo narysuj coś na canvasie.");
      return;
    }

    const formData = new FormData();
    formData.append("file", inputFile);
    formData.append("output_width_mm", getFormValue("outputWidthMm"));
    formData.append("feed_rate", getFormValue("feedRate"));
    formData.append("threshold", getFormValue("threshold"));
    formData.append("min_component_area", getFormValue("minComponentArea"));
    formData.append("potrace_turdsize", getFormValue("potraceTurdsize"));
    formData.append("rdp_epsilon_px", getFormValue("rdpEpsilon"));
    formData.append("min_path_length_px", getFormValue("minPathLength"));
    formData.append("pen_up_cmd", getFormValue("penUpCmd"));
    formData.append("pen_down_cmd", getFormValue("penDownCmd"));
    formData.append("use_adaptive_threshold", String(getCheckboxValue("adaptiveThreshold")));
    formData.append("flip_y", String(getCheckboxValue("flipY")));

    const response = await fetch(API_URL, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      let message = "Błąd generowania G-code.";
      try {
        const data = await response.json();
        message = data.detail || message;
      } catch {
        // ignore JSON parse failure
      }
      throw new Error(message);
    }

    const metaHeader = response.headers.get("X-Plotter-Meta");
    if (metaHeader) {
      try {
        const meta = JSON.parse(metaHeader);
        metaBox.textContent = JSON.stringify(meta, null, 2);
      } catch {
        metaBox.textContent = metaHeader;
      }
    }

    const blob = await response.blob();
    lastGcodeText = await blob.text();

    downloadBlob(
      new Blob([lastGcodeText], { type: "text/plain" }),
      "output.gcode"
    );

    loadSimulation(lastGcodeText);
    setStatus("Gotowe. Plik output.gcode został pobrany i załadowany do symulatora.");
  } catch (error) {
    setStatus(error.message || "Wystąpił błąd.");
  }
}

generateBtn.addEventListener("click", generateGcode);
initCanvas();
initSimCanvas();
