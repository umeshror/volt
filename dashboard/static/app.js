/**
 * VOLT Dashboard — app.js
 * Handles WebSocket, Chart.js, device polling, OTA upload, and crash log.
 */

"use strict";

const WS_URL      = `ws://${location.host}/ws`;
const API_DEVICES = "/api/devices";
const POLL_MS     = 5000;
const MAX_LOG     = 200;
const MAX_POINTS  = 60;

// ── State ──────────────────────────────────────────────────────────── //
let ws = null;
let selectedDevice = null;
let sensorChart = null;
const mqttEntries = [];

// ── DOM refs ───────────────────────────────────────────────────────── //
const wsIndicator  = document.getElementById("ws-indicator");
const wsLabel      = document.getElementById("ws-label");
const deviceList   = document.getElementById("device-list");
const otaSelect    = document.getElementById("ota-device");
const otaPushBtn   = document.getElementById("ota-push-btn");
const otaFileInput = document.getElementById("ota-file");
const otaFileName  = document.getElementById("ota-file-name");
const otaStatus    = document.getElementById("ota-status");
const mqttLog      = document.getElementById("mqtt-log");
const mqttFilter   = document.getElementById("mqtt-filter");
const crashLog     = document.getElementById("crash-log");
const refreshCrash = document.getElementById("refresh-crashes");

// ── WebSocket ──────────────────────────────────────────────────────── //
function connectWS() {
  ws = new WebSocket(WS_URL);

  ws.addEventListener("open", () => {
    wsIndicator.className = "status-dot status-online";
    wsLabel.textContent = "Connected";
  });

  ws.addEventListener("close", () => {
    wsIndicator.className = "status-dot status-offline";
    wsLabel.textContent = "Reconnecting…";
    setTimeout(connectWS, 3000);
  });

  ws.addEventListener("message", ({ data }) => {
    try {
      const msg = JSON.parse(data);
      handleEvent(msg);
    } catch (_) {}
  });
}

function handleEvent(msg) {
  const { type } = msg;
  if (type === "sensor") updateChart(msg);
  if (type === "mqtt")   addMqttEntry(msg.topic, msg.payload);
  if (type === "health") updateHealth(msg);
  if (type === "device") refreshDevices();
}

// ── Chart ──────────────────────────────────────────────────────────── //
function initChart() {
  const ctx = document.getElementById("sensor-chart").getContext("2d");
  sensorChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Temperature (°C)",
          data: [],
          borderColor: "#3B82F6",
          backgroundColor: "rgba(59,130,246,0.1)",
          tension: 0.4,
          fill: true,
          pointRadius: 2,
        },
        {
          label: "Humidity (%)",
          data: [],
          borderColor: "#22C55E",
          backgroundColor: "rgba(34,197,94,0.1)",
          tension: 0.4,
          fill: true,
          pointRadius: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      plugins: {
        legend: { labels: { color: "#94A3B8", font: { size: 12 } } },
      },
      scales: {
        x: { ticks: { color: "#475569", maxTicksLimit: 8 }, grid: { color: "#1E293B" } },
        y: { ticks: { color: "#475569" }, grid: { color: "#1E293B" } },
      },
    },
  });
}

function updateChart({ timestamp, temp, humidity }) {
  const label = new Date(timestamp * 1000).toLocaleTimeString();
  const ds = sensorChart.data;

  ds.labels.push(label);
  ds.datasets[0].data.push(temp ?? null);
  ds.datasets[1].data.push(humidity ?? null);

  if (ds.labels.length > MAX_POINTS) {
    ds.labels.shift();
    ds.datasets.forEach(d => d.data.shift());
  }

  sensorChart.update("none");
}

// ── Device polling ─────────────────────────────────────────────────── //
async function refreshDevices() {
  try {
    const res = await fetch(API_DEVICES);
    const devices = await res.json();
    renderDevices(devices);
    populateOtaSelect(devices);
  } catch (_) {}
}

function renderDevices(devices) {
  if (!devices.length) {
    deviceList.innerHTML = `<p class="placeholder">No devices discovered yet.</p>`;
    return;
  }

  deviceList.innerHTML = devices.map(d => `
    <div class="device-item ${selectedDevice === d.id ? "selected" : ""}"
         id="dev-${d.id}"
         data-id="${d.id}"
         onclick="selectDevice('${d.id}', '${d.ip}')">
      <div>
        <div class="device-name">${d.id}</div>
        <div class="device-ip">${d.ip || "—"}</div>
      </div>
      <span class="device-badge ${d.online ? "badge-online" : "badge-offline"}">
        ${d.online ? "Online" : "Offline"}
      </span>
    </div>
  `).join("");
}

function selectDevice(id, ip) {
  selectedDevice = id;
  renderDevices; // re-render updates selection
  fetchHealth(ip);
  fetchCrashLog(ip);
}

function populateOtaSelect(devices) {
  otaSelect.innerHTML = `<option value="">— Select device —</option>` +
    devices.map(d => `<option value="${d.id}">${d.id} (${d.ip})</option>`).join("");
}

// ── Health panel ───────────────────────────────────────────────────── //
function updateHealth({ uptime, free_ram, rssi, ip }) {
  document.getElementById("h-uptime").textContent = uptime ? `${Math.floor(uptime / 60)}m ${uptime % 60}s` : "—";
  document.getElementById("h-ram").textContent    = free_ram ? `${(free_ram / 1024).toFixed(1)} KB` : "—";
  document.getElementById("h-rssi").textContent   = rssi ? `${rssi} dBm` : "—";
  document.getElementById("h-ip").textContent     = ip || "—";
}

async function fetchHealth(ip) {
  try {
    const res = await fetch(`http://${ip}/health`);
    const data = await res.json();
    updateHealth(data);
  } catch (_) {}
}

// ── MQTT log ───────────────────────────────────────────────────────── //
function addMqttEntry(topic, payload) {
  const filter = mqttFilter.value.trim();
  if (filter && !topic.includes(filter)) return;

  const time = new Date().toLocaleTimeString();
  const entry = document.createElement("div");
  entry.className = "log-entry";
  entry.dataset.topic = topic;
  entry.innerHTML =
    `<span class="log-time">${time}</span> ` +
    `<span class="log-topic">${topic}</span> ` +
    `<span class="log-payload">${JSON.stringify(payload)}</span>`;

  mqttLog.appendChild(entry);
  mqttEntries.push(entry);

  if (mqttEntries.length > MAX_LOG) {
    const old = mqttEntries.shift();
    old.remove();
  }
  mqttLog.scrollTop = mqttLog.scrollHeight;
}

mqttFilter.addEventListener("input", () => {
  const filter = mqttFilter.value.trim();
  document.querySelectorAll("#mqtt-log .log-entry").forEach(el => {
    el.style.display = (!filter || el.dataset.topic.includes(filter)) ? "" : "none";
  });
});

// ── Crash log ──────────────────────────────────────────────────────── //
refreshCrash.addEventListener("click", () => {
  if (selectedDevice) {
    const ip = document.querySelector(`[data-id="${selectedDevice}"] .device-ip`)?.textContent;
    if (ip && ip !== "—") fetchCrashLog(ip);
  }
});

async function fetchCrashLog(ip) {
  try {
    const res = await fetch(`http://${ip}/crashes`);
    const entries = await res.json();
    renderCrashLog(entries);
  } catch (_) {
    crashLog.textContent = "Could not reach device.";
  }
}

function renderCrashLog(entries) {
  if (!entries?.length) {
    crashLog.textContent = "No crashes recorded 🎉";
    return;
  }
  crashLog.innerHTML = entries.map(e =>
    `<div class="log-entry">[${new Date(e.timestamp * 1000).toLocaleString()}] ` +
    `${e.exception}: ${e.message}</div>`
  ).join("");
}

// ── OTA upload ─────────────────────────────────────────────────────── //
otaFileInput.addEventListener("change", () => {
  const file = otaFileInput.files[0];
  otaFileName.textContent = file ? file.name : "Choose firmware file…";
  updateOtaBtn();
});

otaSelect.addEventListener("change", updateOtaBtn);

function updateOtaBtn() {
  otaPushBtn.disabled = !(otaFileInput.files[0] && otaSelect.value);
}

otaPushBtn.addEventListener("click", async () => {
  const deviceId = otaSelect.value;
  const file = otaFileInput.files[0];
  if (!deviceId || !file) return;

  otaStatus.textContent = "Pushing…";
  otaPushBtn.disabled = true;

  const form = new FormData();
  form.append("file", file);

  try {
    const res = await fetch(`/api/ota/${deviceId}`, { method: "POST", body: form });
    const data = await res.json();
    otaStatus.textContent = data.error ? `✗ ${data.error}` : "✓ OTA complete — device rebooting";
  } catch (e) {
    otaStatus.textContent = `✗ ${e.message}`;
  } finally {
    otaPushBtn.disabled = false;
  }
});

// ── Init ───────────────────────────────────────────────────────────── //
initChart();
connectWS();
refreshDevices();
setInterval(refreshDevices, POLL_MS);
