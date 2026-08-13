const $ = (id) => document.getElementById(id);
const feed = $("feed");
const seen = new Map();
let running = false;
let audioEl = null;

const api = async (path, opts = {}) => {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.status === 204 ? null : res.json();
};

const saveConfig = (patch) =>
  api("/api/config", { method: "POST", body: JSON.stringify(patch) });

// ---------- oppsett ----------

async function loadDevices() {
  const d = await api("/api/devices");
  $("deviceSelect").innerHTML = d.inputs
    .map((x) => `<option value="${x.index}">${x.name}</option>`)
    .join("");
  $("monitorSelect").innerHTML =
    `<option value="">Av</option>` +
    d.outputs.map((x) => `<option value="${x.index}">${x.name}</option>`).join("");
  if (d.default_input != null) $("deviceSelect").value = d.default_input;
}

async function loadConfig() {
  const c = await api("/api/config");
  $("langSelect").value = c.language;
  $("modeSelect").value = c.mode;
  $("engineSelect").value = c.stt_engine;
  $("modelSelect").value = c.stt_model;
  $("modelSelect").hidden = c.stt_engine !== "local";
  $("targetSelect").value = c.target_language;
  $("targetSelect").hidden = c.mode !== "translate";
  if (c.device != null) $("deviceSelect").value = c.device;
}

// ---------- rendering ----------

const esc = (s) =>
  (s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function bodyHtml(seg) {
  if (seg.status === "pending")
    return `<div class="text pending"><span class="spin"></span>i kø …</div>`;
  if (seg.status === "processing")
    return `<div class="text pending"><span class="spin on"></span>transkriberer …</div>`;
  if (seg.status === "retrying")
    return `<div class="text pending warn">prøver igjen (${seg.attempts}/3) …</div>`;
  if (seg.status === "dropped")
    return `<div class="text pending warn">køen var full – lyden er lagret
            <button class="retry" data-retry="${seg.id}">prøv igjen</button></div>`;
  if (seg.status === "error")
    return `<div class="text pending warn">${esc(seg.text)}
            <button class="retry" data-retry="${seg.id}">prøv igjen</button></div>`;
  if (seg.status === "empty") return `<div class="text pending">(ingen tale registrert)</div>`;
  let html = `<div class="text">${esc(seg.text)}</div>`;
  if (seg.translation) html += `<div class="translation">${esc(seg.translation)}</div>`;
  return html;
}

function cardHtml(seg) {
  const time = (seg.started_at || "").slice(11, 19);
  const lang = (seg.language || "··").slice(0, 2).toUpperCase();
  return `
    <div class="card-head">
      <button class="play" data-id="${seg.id}">▶</button>
      <span class="lang">${lang}</span>
      <span class="time">${time}</span>
      <span class="dur">${Number(seg.duration).toFixed(1)}s</span>
      <button class="del" data-del="${seg.id}">×</button>
    </div>
    ${bodyHtml(seg)}`;
}

function upsert(seg) {
  let el = seen.get(seg.id);
  if (!el) {
    el = document.createElement("article");
    el.className = "card";
    el.dataset.id = seg.id;
    feed.prepend(el);
    seen.set(seg.id, el);
  }
  el.innerHTML = cardHtml(seg);
  el.dataset.text = `${seg.text || ""} ${seg.translation || ""}`.toLowerCase();
  $("empty").hidden = true;
  applyFilter();
}

function applyFilter() {
  const q = $("filterInput").value.trim().toLowerCase();
  let visible = 0;
  seen.forEach((el) => {
    const hit = !q || (el.dataset.text || "").includes(q);
    el.hidden = !hit;
    if (hit) visible++;
  });
  $("empty").hidden = visible > 0;
}

// ---------- avspilling ----------

feed.addEventListener("click", async (e) => {
  const play = e.target.closest(".play");
  if (play) {
    if (audioEl) audioEl.pause();
    audioEl = new Audio(`/api/segments/${play.dataset.id}/audio`);
    audioEl.play().catch(() => {});
    return;
  }
  const del = e.target.closest(".del");
  if (del) {
    const id = Number(del.dataset.del);
    await api(`/api/segments/${id}`, { method: "DELETE" });
    seen.get(id)?.remove();
    seen.delete(id);
    applyFilter();
    return;
  }
  const retry = e.target.closest(".retry");
  if (retry) {
    await api(`/api/segments/${retry.dataset.retry}/retry`, { method: "POST" });
  }
});

// ---------- websocket ----------

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onmessage = (msg) => {
    const { event, data } = JSON.parse(msg.data);
    if (event === "level") {
      const pct = Math.max(0, Math.min(100, ((data.db + 60) / 60) * 100));
      $("meterFill").style.width = `${pct}%`;
      const dot = $("statusDot");
      dot.className = "dot" + (data.active ? " rx" : data.running ? " on" : "");
      setRunning(data.running);
    } else if (event === "segment_new" || event === "segment_update") {
      upsert(data);
    } else if (event === "queue") {
      setQueue(data.depth);
    }
  };
  ws.onclose = () => setTimeout(connect, 2000);
}

function setQueue(depth) {
  const badge = $("queueBadge");
  badge.hidden = !depth;
  badge.textContent = `${depth} i kø`;
  badge.classList.toggle("busy", depth > 5);
}

// ---------- kontroller ----------

function setRunning(state) {
  running = state;
  const btn = $("toggleBtn");
  btn.textContent = state ? "Stopp" : "Start";
  btn.classList.toggle("running", state);
}

$("toggleBtn").onclick = async () => {
  try {
    if (running) {
      await api("/api/stop", { method: "POST" });
    } else {
      await api("/api/start", {
        method: "POST",
        body: JSON.stringify({ device: Number($("deviceSelect").value) }),
      });
    }
  } catch (err) {
    alert(`Kunne ikke ${running ? "stoppe" : "starte"}: ${err.message}`);
  }
};

$("deviceSelect").onchange = (e) => saveConfig({ device: Number(e.target.value) });
$("langSelect").onchange = (e) => saveConfig({ language: e.target.value });
$("engineSelect").onchange = (e) => {
  $("modelSelect").hidden = e.target.value !== "local";
  saveConfig({ stt_engine: e.target.value });
};
$("modelSelect").onchange = (e) => saveConfig({ stt_model: e.target.value });
$("targetSelect").onchange = (e) => saveConfig({ target_language: e.target.value });

$("modeSelect").onchange = (e) => {
  $("targetSelect").hidden = e.target.value !== "translate";
  saveConfig({ mode: e.target.value });
};

$("filterInput").oninput = () => {
  applyFilter();
  const q = $("filterInput").value.trim();
  $("exportLink").href = `/api/export?fmt=txt${q ? `&q=${encodeURIComponent(q)}` : ""}`;
};

// ---------- oppstart ----------

(async () => {
  await loadDevices();
  await loadConfig();
  const segments = await api("/api/segments?limit=200");
  segments.reverse().forEach(upsert);
  $("empty").hidden = segments.length > 0;
  const status = await api("/api/status");
  setRunning(status.running);
  setQueue(status.queue);
  connect();
})();
