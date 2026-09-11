/* Commscribe - klientlogikk.
   Ingen rammeverk: appen har én skjerm, og alt kan holdes i en Map. */

const $ = (id) => document.getElementById(id);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// Skallet gir oss nøkkelen i URL-en. Vi tar den ut av adresselinja med en gang
// slik at den ikke blir liggende synlig eller havner i en historikkoppføring.
const TOKEN = new URLSearchParams(location.search).get("token") || "";
if (TOKEN) history.replaceState(null, "", location.pathname);

const state = {
  running: false,
  segments: new Map(),      // id -> rad fra serveren
  cards: new Map(),         // id -> DOM-node
  config: {},
  models: [],
  filter: "all",
  query: "",
  playing: null,
};

/* ---------- server ---------- */

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(TOKEN ? { "X-Commscribe-Token": TOKEN } : {}),
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* ikke JSON */ }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

const post = (path, body) =>
  api(path, { method: "POST", body: JSON.stringify(body ?? {}) });

// Innstillingene lagres til disk ved hvert kall, så vi samler opp raske
// endringer (typisk når en glidebryter dras) i stedet for å skrive per piksel.
let patchTimer = null;
let pendingPatch = {};
function saveConfig(patch, immediate = false) {
  Object.assign(state.config, patch);
  Object.assign(pendingPatch, patch);
  clearTimeout(patchTimer);
  const flush = () => {
    const body = pendingPatch;
    pendingPatch = {};
    if (Object.keys(body).length) post("/api/config", body).catch(err => toast("error", err.message));
  };
  if (immediate) flush();
  else patchTimer = setTimeout(flush, 350);
}

/* ---------- hjelpere ---------- */

const esc = (s) => (s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const clock = (iso) => (iso || "").slice(11, 19);
const dayOf = (iso) => (iso || "").slice(0, 10);

function dayLabel(day) {
  const today = new Date();
  const iso = (d) => d.toISOString().slice(0, 10);
  const yesterday = new Date(today.getTime() - 864e5);
  if (day === iso(today)) return t("day.today");
  if (day === iso(yesterday)) return t("day.yesterday");
  const [y, m, d] = day.split("-");
  return `${d}.${m}.${y}`;
}

function toast(level, message, ms = 5000) {
  const el = document.createElement("div");
  el.className = `toast ${level}`;
  el.textContent = message;
  $("toasts").append(el);
  setTimeout(() => {
    el.classList.add("out");
    setTimeout(() => el.remove(), 250);
  }, ms);
}

/* ---------- kort ---------- */

const STATE_VIEW = {
  pending:    () => `<div class="state"><span class="spin"></span>${t("card.pending")}</div>`,
  processing: () => `<div class="state"><span class="spin on"></span>${t("card.processing")}</div>`,
  retrying:   (s) => `<div class="state warn"><span class="spin on"></span>${t("card.retrying", { n: s.attempts })}</div>`,
  dropped:    (s) => `<div class="state warn">${t("card.dropped")}
                      <button class="retry" data-retry="${s.id}">${t("card.transcribe")}</button></div>`,
  error:      (s) => `<div class="state err">${esc(s.text) || t("card.error")}
                      <button class="retry" data-retry="${s.id}">${t("card.retry")}</button></div>`,
  empty:      (s) => `<div class="state">${t("card.empty")}
                      <button class="retry" data-retry="${s.id}">${t("card.retry")}</button></div>`,
};

function waveHtml(raw) {
  let peaks = [];
  try { peaks = JSON.parse(raw || "[]"); } catch { peaks = []; }
  if (!peaks.length) return "";
  return `<div class="wave" aria-hidden="true">${peaks
    .map((p) => `<i style="height:${Math.max(8, Math.round(p * 100))}%"></i>`)
    .join("")}</div>`;
}

function bodyHtml(seg) {
  const view = STATE_VIEW[seg.status];
  if (view) return view(seg);
  let html = `<div class="text" data-edit="${seg.id}" contenteditable="plaintext-only"
    spellcheck="false" role="textbox" aria-label="${t("card.edit")}">${esc(seg.text)}</div>`;
  if (seg.translation) html += `<div class="translation">${esc(seg.translation)}</div>`;
  if (seg.note) html += `<div class="note">${esc(seg.note)}</div>`;
  return html;
}

function cardHtml(seg) {
  const lang = (seg.language || "").slice(0, 2).toUpperCase();
  return `
    <button class="play" data-play="${seg.id}" aria-label="${t("card.play")}">
      <span class="ring"></span>
      <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
        <path d="M8 5v14l11-7z"/></svg>
    </button>
    <div class="card-head">
      <span class="time">${clock(seg.started_at)}</span>
      <span class="dur">${Number(seg.duration).toFixed(1)}s</span>
      ${lang ? `<span class="tag">${lang}</span>` : ""}
      ${seg.origin ? `<span class="origin" title="${esc(seg.origin)}">${esc(seg.origin)}</span>` : ""}
      ${waveHtml(seg.waveform)}
      <div class="card-actions">
        <button class="act star ${seg.starred ? "on" : ""}" data-star="${seg.id}"
                title="${t("card.star")}" aria-label="${t("card.star")}">
          <svg viewBox="0 0 24 24" width="14" height="14"
               fill="${seg.starred ? "currentColor" : "none"}" stroke="currentColor"
               stroke-width="1.7"><path d="m12 3.6 2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8L3.6 9.7l5.8-.8z"/></svg>
        </button>
        <button class="act" data-copy="${seg.id}" title="${t("card.copy")}" aria-label="${t("card.copy")}">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor"
               stroke-width="1.7"><rect x="9" y="9" width="11" height="11" rx="2"/>
            <path d="M5 15V5a2 2 0 0 1 2-2h8"/></svg>
        </button>
        <button class="act danger" data-del="${seg.id}" title="${t("card.delete")}" aria-label="${t("card.delete")}">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor"
               stroke-width="1.7"><path d="M4 7h16M10 11v6M14 11v6"/>
            <path d="M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>
        </button>
      </div>
    </div>
    <div class="card-body">${bodyHtml(seg)}</div>`;
}

function upsert(seg, { prepend = true } = {}) {
  state.segments.set(seg.id, seg);
  let el = state.cards.get(seg.id);

  // Ikke tegn kortet på nytt mens brukeren står og retter teksten i det.
  if (el?.contains(document.activeElement) &&
      document.activeElement.hasAttribute("data-edit")) return;

  if (!el) {
    el = document.createElement("article");
    el.className = "card";
    el.dataset.id = seg.id;
    state.cards.set(seg.id, el);
    if (prepend) placeCard(el, seg);
  }
  el.innerHTML = cardHtml(seg);
  el.classList.toggle("starred", !!seg.starred);
  el.classList.toggle("problem", ["error", "dropped"].includes(seg.status));
  if (!bulkLoading) applyFilter();
}

// Ved oppstart legges hundrevis av kort inn på rad. Å filtrere hele lista for
// hvert enkelt av dem ville vært kvadratisk arbeid uten synlig gevinst.
let bulkLoading = false;

// Setter kortet på rett plass: nyeste dag øverst, nyeste transmisjon øverst i
// dagen. Vi kan ikke bare legge nye kort på toppen - ved oppstart kommer de i
// vilkårlig rekkefølge, og et gjenopptatt segment kan være eldre enn det siste.
function placeCard(el, seg) {
  const feed = $("feed");
  const day = dayOf(seg.started_at);
  let sep = $(`sep-${day}`);

  if (!sep) {
    sep = document.createElement("div");
    sep.className = "day-sep";
    sep.id = `sep-${day}`;
    sep.dataset.day = day;
    sep.textContent = dayLabel(day);
    const older = $$(".day-sep", feed).find((s) => s.dataset.day < day);
    feed.insertBefore(sep, older || null);
  }

  let node = sep.nextElementSibling;
  while (node?.classList.contains("card") &&
         (state.segments.get(Number(node.dataset.id))?.started_at || "") > seg.started_at) {
    node = node.nextElementSibling;
  }
  feed.insertBefore(el, node || null);
}

function matches(seg) {
  if (state.query) {
    const hay = `${seg.text || ""} ${seg.translation || ""} ${seg.note || ""}`.toLowerCase();
    if (!hay.includes(state.query)) return false;
  }
  if (state.filter === "starred") return !!seg.starred;
  if (state.filter === "translated") return !!seg.translation;
  if (state.filter === "problem") return ["error", "dropped", "empty"].includes(seg.status);
  return true;
}

function applyFilter() {
  let visible = 0;
  for (const [id, el] of state.cards) {
    const seg = state.segments.get(id);
    const hit = seg && matches(seg);
    el.hidden = !hit;
    if (hit) visible++;
  }
  // Skjul datoskiller som ikke lenger har kort under seg.
  $$(".day-sep").forEach((sep) => {
    let node = sep.nextElementSibling, any = false;
    while (node && node.classList.contains("card")) {
      if (!node.hidden) { any = true; break; }
      node = node.nextElementSibling;
    }
    sep.hidden = !any;
  });

  const total = state.segments.size;
  $("empty").hidden = visible > 0;
  $("resultCount").textContent =
    !total ? "" : visible === total ? t("filter.count_all", { n: total })
                                    : t("filter.count_some", { shown: visible, total });

  const capture = !document.body.classList.contains("no-capture");
  if (!visible && total) {
    $("emptyTitle").textContent = t("empty.no_hits");
    $("emptyHint").hidden = false;
    $("emptyHint").textContent = t("empty.no_hits_hint");
    $("emptyUploadHint").hidden = true;
  } else if (!total) {
    $("emptyTitle").textContent = capture ? t("empty.title") : t("empty.title_uploads");
    $("emptyHint").hidden = !capture;
    $("emptyHint").innerHTML = t("empty.hint");
    $("emptyUploadHint").hidden = false;
    $("emptyUploadHint").textContent = capture ? t("empty.upload_hint")
                                               : t("empty.upload_hint_server");
  }
}

/* ---------- handlinger på kort ---------- */

$("feed").addEventListener("click", async (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;

  if (btn.dataset.play) return playSegment(Number(btn.dataset.play), btn);

  if (btn.dataset.del) {
    const id = Number(btn.dataset.del);
    try {
      await api(`/api/segments/${id}`, { method: "DELETE" });
      removeCard(id);
    } catch (err) { toast("error", err.message); }
    return;
  }

  if (btn.dataset.star) {
    const id = Number(btn.dataset.star);
    const seg = state.segments.get(id);
    try { upsert(await api(`/api/segments/${id}`,
      { method: "PATCH", body: JSON.stringify({ starred: !seg.starred }) })); }
    catch (err) { toast("error", err.message); }
    return;
  }

  if (btn.dataset.copy) {
    const seg = state.segments.get(Number(btn.dataset.copy));
    const text = [seg.text, seg.translation].filter(Boolean).join("\n");
    navigator.clipboard.writeText(text)
      .then(() => toast("ok", t("toast.copied")))
      .catch(() => toast("warn", t("toast.clipboard")));
    return;
  }

  if (btn.dataset.retry) {
    try { await post(`/api/segments/${btn.dataset.retry}/retry`); }
    catch (err) { toast("error", err.message); }
  }
});

// Retting av transkripsjon: lagre når feltet forlates.
$("feed").addEventListener("focusout", async (e) => {
  const box = e.target.closest("[data-edit]");
  if (!box) return;
  const id = Number(box.dataset.edit);
  const seg = state.segments.get(id);
  const text = box.textContent.trim();
  if (!seg || text === (seg.text || "").trim()) return;
  try {
    upsert(await api(`/api/segments/${id}`,
      { method: "PATCH", body: JSON.stringify({ text }) }));
    toast("ok", t("toast.saved"));
  } catch (err) {
    toast("error", err.message);
    box.textContent = seg.text || "";
  }
}, true);

$("feed").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target.hasAttribute("data-edit")) {
    e.preventDefault();
    e.target.blur();
  }
  if (e.key === "Escape" && e.target.hasAttribute("data-edit")) {
    e.target.textContent = state.segments.get(Number(e.target.dataset.edit))?.text || "";
    e.target.blur();
  }
});

function removeCard(id) {
  state.cards.get(id)?.remove();
  state.cards.delete(id);
  state.segments.delete(id);
  applyFilter();
}

/* ---------- avspilling ---------- */

function playSegment(id, btn) {
  if (state.playing?.id === id) return stopPlayback();
  stopPlayback();

  const audio = new Audio(`/api/segments/${id}/audio${TOKEN ? `?token=${TOKEN}` : ""}`);
  state.playing = { id, audio, btn };
  btn.classList.add("playing");
  btn.querySelector("svg").innerHTML = '<rect x="7" y="6" width="4" height="12"/><rect x="13" y="6" width="4" height="12"/>';

  audio.ontimeupdate = () => {
    if (audio.duration) btn.style.setProperty("--p", (audio.currentTime / audio.duration) * 100);
  };
  audio.onended = stopPlayback;
  audio.onerror = () => { toast("warn", t("toast.playback")); stopPlayback(); };
  audio.play().catch(() => stopPlayback());
}

function stopPlayback() {
  const p = state.playing;
  if (!p) return;
  p.audio.pause();
  p.btn.classList.remove("playing");
  p.btn.style.removeProperty("--p");
  const svg = p.btn.querySelector("svg");
  if (svg) svg.innerHTML = '<path d="M8 5v14l11-7z"/>';
  state.playing = null;
}

/* ---------- live-tilkobling ---------- */

let ws = null;
let wsRetry = 0;

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws${TOKEN ? `?token=${TOKEN}` : ""}`);

  ws.onopen = () => {
    wsRetry = 0;
    // Serveren leser fra socketen for å oppdage brudd; et hjerteslag holder
    // mellomledd fra å stenge en stille forbindelse.
    clearInterval(ws._beat);
    ws._beat = setInterval(() => ws.readyState === 1 && ws.send("ping"), 25000);
  };

  ws.onmessage = (msg) => {
    const { event, data } = JSON.parse(msg.data);
    if (event === "level") return onLevel(data);
    if (event === "segment_new" || event === "segment_update") return upsert(data);
    if (event === "segment_deleted") return removeCard(data.id);
    if (event === "cleared") return resetFeed();
    if (event === "queue") return setQueue(data.depth);
    if (event === "status") return setRunning(data.running);
    if (event === "notice") return toast(data.level === "warn" ? "warn" : data.level, data.message);
    if (event === "model") return onModelProgress(data);
    if (event === "config") { state.config = { ...state.config, ...data }; fillConfig(); }
  };

  ws.onclose = () => {
    clearInterval(ws._beat);
    // Vent gradvis lenger, men aldri mer enn fem sekunder - backenden er lokal
    // og kommer normalt rett tilbake.
    setTimeout(connect, Math.min(5000, 500 * ++wsRetry));
  };
  ws.onerror = () => ws.close();
}

let lastActive = false;
function onLevel(d) {
  // -60 dB til 0 dB på skalaen.
  const pct = Math.max(0, Math.min(100, ((d.db + 60) / 60) * 100));
  $("meterFill").style.width = `${pct}%`;
  $("setupMeterFill").style.width = `${pct}%`;

  const peakPct = Math.max(0, Math.min(100, ((d.peak + 60) / 60) * 100));
  const peak = $("meterPeak");
  peak.style.left = `${peakPct}%`;
  peak.classList.toggle("on", d.peak > -60);

  $("levelRead").textContent = d.db <= -119 ? "−∞" : d.db.toFixed(0);
  $("meter").classList.toggle("clip", !!d.clipping);

  $("statusDot").className = "dot" + (d.active ? " rx" : d.running ? " on" : "");
  $("statusText").textContent = d.active ? t("bar.status_rx")
                              : d.running ? t("bar.status_listening") : t("bar.status_off");
  if (d.active !== lastActive) {
    $("recIndicator").hidden = !d.active;
    lastActive = d.active;
  }
  setRunning(d.running);
}

function setQueue(depth) {
  const badge = $("queueBadge");
  badge.hidden = !depth;
  badge.textContent = depth === 1 ? t("bar.queue_one") : t("bar.queue_many", { n: depth });
  badge.dataset.depth = depth;
  badge.classList.toggle("busy", depth > 5);
}

function setRunning(on) {
  if (state.running === on) return;
  state.running = on;
  $("toggleBtn").classList.toggle("on", on);
  $("toggleLabel").textContent = on ? t("bar.stop") : t("bar.start");
  if (!on) { $("recIndicator").hidden = true; lastActive = false; }
}

function resetFeed() {
  state.cards.clear();
  state.segments.clear();
  $("feed").innerHTML = "";
  applyFilter();
}

/* ---------- verktoylinje ---------- */

$("toggleBtn").onclick = async () => {
  const btn = $("toggleBtn");
  btn.disabled = true;
  try {
    if (state.running) await post("/api/stop");
    else await post("/api/start", { device: Number($("deviceSelect").value) });
  } catch (err) {
    toast("error", t(state.running ? "toast.stop_failed" : "toast.start_failed",
                     { err: err.message }));
  } finally {
    btn.disabled = false;
  }
};

/* ---------- opplasting ---------- */

// Egen hjelper: api() setter JSON som innholdstype, og et skjema med fil må
// få nettleseren til å sette multipart-grensa selv.
async function uploadFile(file) {
  const fd = new FormData();
  fd.append("file", file, file.name);
  if (file.lastModified) fd.append("started_at", new Date(file.lastModified).toISOString());
  const res = await fetch("/api/upload", {
    method: "POST",
    body: fd,
    headers: TOKEN ? { "X-Commscribe-Token": TOKEN } : {},
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* ikke JSON */ }
    throw new Error(detail);
  }
  return res.json();
}

async function uploadFiles(files) {
  const list = [...files].filter((f) => f.size > 0);
  if (!list.length) return;
  const btn = $("uploadBtn");
  btn.disabled = true;
  let ok = 0;
  for (const file of list) {
    toast("info", t("toast.uploading", { name: file.name }), 2500);
    try {
      const seg = await uploadFile(file);
      upsert(seg);
      ok += 1;
    } catch (err) {
      toast("error", `${file.name}: ${err.message}`, 8000);
    }
  }
  btn.disabled = false;
  if (ok) toast("ok", ok === 1 ? t("toast.queued_one") : t("toast.queued_many", { n: ok }));
}

$("uploadBtn").onclick = () => $("uploadInput").click();
$("uploadInput").onchange = (e) => {
  uploadFiles(e.target.files);
  e.target.value = "";
};

// Dra og slipp hvor som helst i vinduet. Telleren trengs fordi dragenter og
// dragleave fyres for hvert barn musa passerer over.
let dragDepth = 0;
document.addEventListener("dragenter", (e) => {
  if (![...(e.dataTransfer?.types || [])].includes("Files")) return;
  dragDepth += 1;
  $("dropOverlay").hidden = false;
});
document.addEventListener("dragleave", () => {
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) $("dropOverlay").hidden = true;
});
document.addEventListener("dragover", (e) => e.preventDefault());
document.addEventListener("drop", (e) => {
  e.preventDefault();
  dragDepth = 0;
  $("dropOverlay").hidden = true;
  if (e.dataTransfer?.files?.length) uploadFiles(e.dataTransfer.files);
});

$("filterInput").oninput = (e) => {
  state.query = e.target.value.trim().toLowerCase();
  applyFilter();
};

$$(".chip").forEach((chip) => {
  chip.onclick = () => {
    $$(".chip").forEach((c) => c.classList.toggle("is-on", c === chip));
    state.filter = chip.dataset.filter;
    applyFilter();
  };
});

// Eksport-menyen
const exportMenu = $("exportMenu");
$("exportBtn").onclick = (e) => {
  e.stopPropagation();
  const open = exportMenu.hidden;
  exportMenu.hidden = !open;
  $("exportBtn").setAttribute("aria-expanded", String(open));
};
document.addEventListener("click", () => {
  exportMenu.hidden = true;
  $("exportBtn").setAttribute("aria-expanded", "false");
});
exportMenu.onclick = (e) => {
  const btn = e.target.closest("[data-fmt]");
  if (!btn) return;
  const params = new URLSearchParams({ fmt: btn.dataset.fmt });
  if (state.query) params.set("q", state.query);
  if (state.filter === "starred") params.set("starred", "true");
  if (TOKEN) params.set("token", TOKEN);
  // Nettleseren laster ned via <a download>; i skallet fanges dette av Electron.
  const a = document.createElement("a");
  a.href = `/api/export?${params}`;
  a.download = "";
  a.click();
  toast("ok", t("export.done"));
};

/* ---------- innstillinger ---------- */

const drawer = $("drawer");
function openDrawer(tab) {
  drawer.hidden = false;
  $("scrim").hidden = false;
  if (tab) selectTab(tab);
  loadModels();
}
function closeDrawer() {
  drawer.hidden = true;
  $("scrim").hidden = true;
}
$("settingsBtn").onclick = () => (drawer.hidden ? openDrawer() : closeDrawer());
$("drawerClose").onclick = closeDrawer;
$("scrim").onclick = closeDrawer;

function selectTab(name) {
  $$(".tab").forEach((t) => t.classList.toggle("is-on", t.dataset.tab === name));
  $$(".panel").forEach((p) => p.classList.toggle("is-on", p.dataset.panel === name));
}
$$(".tab").forEach((t) => (t.onclick = () => selectTab(t.dataset.tab)));

// Kobler en glidebryter til en innstilling, med formatert visning ved siden av.
function bindRange(id, key, format, { integer = false } = {}) {
  const input = $(id);
  const out = $(input.getAttribute("aria-describedby") || `${id}Out`) ||
              input.parentElement.querySelector("output");
  const render = (v) => (out.textContent = format(v));
  input.oninput = () => {
    const v = integer ? parseInt(input.value, 10) : parseFloat(input.value);
    render(v);
    saveConfig({ [key]: v });
    if (key === "threshold_db") drawThreshold(v);
  };
  return { input, render };
}

const nb = (n, d = 1) => n.toFixed(d).replace(".", ",");

const ranges = {
  threshold_db: bindRange("thresholdDb", "threshold_db", (v) => `${v} dB`, { integer: true }),
  min_duration: bindRange("minDuration", "min_duration", (v) => `${nb(v)} s`),
  hangover_ms:  bindRange("hangoverMs", "hangover_ms", (v) => `${v} ms`, { integer: true }),
  preroll_ms:   bindRange("prerollMs", "preroll_ms", (v) => `${v} ms`, { integer: true }),
  cpu_threads:  bindRange("cpuThreads", "cpu_threads", (v) => `${v}`, { integer: true }),
  beam_size:    bindRange("beamSize", "beam_size", (v) => `${v}`, { integer: true }),
  monitor_gain: bindRange("monitorGain", "monitor_gain", (v) => `${nb(v)}×`),
};

function drawThreshold(db) {
  $("meterThreshold").style.left = `${Math.max(0, Math.min(100, ((db + 60) / 60) * 100))}%`;
}

$("deviceSelect").onchange = (e) => {
  const opt = e.target.selectedOptions[0];
  saveConfig({ device: Number(e.target.value), device_name: opt?.textContent || "" }, true);
  $("sbDevice").textContent = opt?.textContent || "–";
  if (state.running) toast("info", t("toast.device_change"));
};

$("monitorEnabled").onchange = (e) => {
  $("monitorRow").hidden = !e.target.checked;
  saveConfig({ monitor_enabled: e.target.checked }, true);
};
$("monitorSelect").onchange = (e) =>
  saveConfig({ monitor_device: e.target.value === "" ? null : Number(e.target.value) }, true);

$("engineSelect").onchange = (e) => {
  saveConfig({ stt_engine: e.target.value }, true);
  updateEngineHints();
};
$("langSelect").onchange = (e) => saveConfig({ language: e.target.value }, true);
$("modeSelect").onchange = (e) => {
  $("targetRow").hidden = e.target.value !== "translate";
  saveConfig({ mode: e.target.value }, true);
  updateEngineHints();
};
$("targetSelect").onchange = (e) => {
  saveConfig({ target_language: e.target.value }, true);
  updateEngineHints();
};
$("themeSelect").onchange = (e) => {
  saveConfig({ theme: e.target.value }, true);
  applyTheme(e.target.value);
};
$("autostartCapture").onchange = (e) =>
  saveConfig({ autostart_capture: e.target.checked }, true);
$("retentionSelect").onchange = (e) =>
  saveConfig({ retention_days: Number(e.target.value) }, true);
$("providerSelect").onchange = (e) => {
  saveConfig({ api_provider: e.target.value }, true);
  renderKeyStatus();
  updateEngineHints();
};
$("apiModelInput").onchange = (e) => saveConfig({ api_model: e.target.value.trim() }, true);
$("ollamaUrlInput").onchange = (e) => saveConfig({ ollama_url: e.target.value.trim() }, true);
$("ollamaModelInput").onchange = (e) =>
  saveConfig({ ollama_model: e.target.value.trim() }, true);

function updateEngineHints() {
  const local = state.config.stt_engine === "local";
  const ollama = state.config.api_provider === "ollama";
  $("engineHint").textContent = local ? t("text.engine_hint_local")
    : ollama ? t("text.engine_hint_ollama") : t("text.engine_hint_cloud");

  // Whisper kan bare oversette til engelsk selv. Alt annet må gjennom
  // språkmodellen, og det krever nøkkel uansett hvilken STT-motor du bruker.
  const target = state.config.target_language;
  $("translateHint").textContent = target === "en" ? t("text.translate_hint_en")
    : ollama ? t("text.translate_hint_ollama") : t("text.translate_hint_cloud");
}

/* nokler */
$("saveKeyBtn").onclick = async () => {
  const provider = $("providerSelect").value;
  const key = $("apiKeyInput").value.trim();
  try {
    state.config.api_keys = await post("/api/keys", { provider, key });
    $("apiKeyInput").value = "";
    renderKeyStatus();
    toast("ok", key ? t("toast.key_saved") : t("toast.key_removed"));
  } catch (err) { toast("error", err.message); }
};

$("testKeyBtn").onclick = async () => {
  const btn = $("testKeyBtn");
  btn.disabled = true;
  btn.textContent = t("toast.testing");
  try {
    const res = await post("/api/keys/test", { provider: $("providerSelect").value });
    toast(res.ok ? "ok" : "error", res.detail);
  } catch (err) {
    toast("error", err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = t("cloud.test");
  }
};

function renderKeyStatus() {
  const provider = $("providerSelect").value;
  const ollama = provider === "ollama";
  $("keyFields").hidden = ollama;
  $("ollamaFields").hidden = !ollama;
  $("cloudHint").textContent = ollama ? t("cloud.hint_ollama") : t("cloud.hint");
  if (ollama) return;
  const has = state.config.api_keys?.[provider];
  $("keyStatus").textContent = has ? t("cloud.key_saved") : t("cloud.key_none");
}

/* ---------- språk ---------- */

// Bytte av språk uten omlasting: skallet ga oss øktnøkkelen i URL-en én gang,
// og en reload ville mistet den. Alt som viser tekst tegnes derfor på nytt.
async function setLanguage(code) {
  if (code === I18N.current) return;
  saveConfig({ ui_language: code }, true);
  await I18N.load(code);
  rerenderAll();
  window.commscribe?.setLanguage?.(code);
}

function fillLanguageSelects() {
  const items = I18N.available.map((c) => [c, I18N.name(c)]);
  fillSelect($("uiLanguageSelect"), items, I18N.current);
  fillSelect($("setupLanguage"), items, I18N.current);
}
$("uiLanguageSelect").onchange = (e) => setLanguage(e.target.value);
$("setupLanguage").onchange = (e) => setLanguage(e.target.value);

function speechItems(codes) {
  return codes.map((c) => [c, t(`speech.${c}`)]);
}

function rerenderAll() {
  I18N.apply();
  fillLanguageSelects();
  fillSelect($("langSelect"), speechItems(state.config.languages), state.config.language);
  fillSelect($("targetSelect"),
    speechItems(state.config.languages.filter((v) => v !== "auto")),
    state.config.target_language);
  fillConfig();
  renderModels();
  renderModelDisk();
  $("toggleLabel").textContent = state.running ? t("bar.stop") : t("bar.start");
  $("statusText").textContent = state.running ? t("bar.status_listening") : t("bar.status_off");
  const depth = Number($("queueBadge").dataset.depth || 0);
  if (depth) $("queueBadge").textContent =
    depth === 1 ? t("bar.queue_one") : t("bar.queue_many", { n: depth });
  $$(".day-sep").forEach((sep) => (sep.textContent = dayLabel(sep.dataset.day)));
  bulkLoading = true;
  for (const seg of state.segments.values()) upsert(seg);
  bulkLoading = false;
  applyFilter();
  if (lastStats) renderStats(lastStats);
}

/* ---------- hva installasjonen kan ---------- */

// Uten lydinngang (containeren paa NOMAD, eller en maskin uten PortAudio)
// skjules alt som handler om aa lytte, og opplasting blir hovedinngangen.
function applyCapabilities() {
  const caps = state.config.capabilities || {};
  const capture = caps.capture !== false;
  document.body.classList.toggle("no-capture", !capture);

  $("toggleBtn").hidden = !capture;
  $$(".meter-wrap").forEach((el) => (el.hidden = !capture));
  $$(".tab").find((t) => t.dataset.tab === "audio").hidden = !capture;
  $("autostartCapture").closest(".field").hidden = !capture;
  $("setupCapture").hidden = !capture;
  $("setupUpload").hidden = capture;
  $("setupReadyCapture").hidden = !capture;
  $("setupReadyUpload").hidden = capture;

  if (!capture) {
    $("sbDevice").textContent = caps.container ? t("status.server") : t("status.no_input");
    if ($$(".tab").find((t) => t.classList.contains("is-on"))?.dataset.tab === "audio") {
      selectTab("stt");
    }
  }
  const accept = (caps.upload_accept || []).join(",");
  $("uploadInput").accept = accept ? `audio/*,video/*,${accept}` : "audio/*,video/*";
}

/* data */
$("clearBtn").onclick = async () => {
  if (!confirm(t("about.confirm_clear"))) return;
  try {
    const res = await post("/api/segments/clear");
    resetFeed();
    toast("ok", t("toast.cleared", { n: res.removed }));
  } catch (err) { toast("error", err.message); }
};

$("openDataBtn").onclick = () => {
  if (window.commscribe?.openPath) window.commscribe.openPath(state.config.data_dir);
  else toast("info", state.config.data_dir);
};

/* ---------- modeller ---------- */

async function loadModels() {
  try {
    const res = await api("/api/models");
    state.models = res.models;
    state.modelDisk = { mb: res.models_mb.toFixed(0), path: res.path };
    renderModels();
    renderModelDisk();
  } catch (err) { toast("error", err.message); }
}

function renderModelDisk() {
  if (state.modelDisk) $("modelDisk").textContent = t("models.disk", state.modelDisk);
}

// Notatet til en modell på brukerens språk, med backendens engelske som reserve.
function modelNote(m) {
  const key = `models.notes.${m.id.split("/").pop()}`;
  const text = t(key);
  return text === key ? m.note : text;
}

function modelHtml(m, selected) {
  const badge = m.status === "downloading"
    ? `<span class="badge dl">${m.progress}%</span>`
    : m.installed ? `<span class="badge ok">${t("models.ready")}</span>`
    : `<span class="badge no">${t("models.not_downloaded")}</span>`;
  return `
    <div class="model ${selected ? "is-on" : ""}" data-model="${m.id}">
      <div class="model-name">${esc(m.label)} ${badge}</div>
      <div class="model-size">${m.size_mb >= 1000
        ? `${(m.size_mb / 1000).toFixed(1)} GB` : `${m.size_mb} MB`}</div>
      <div class="model-note">${esc(modelNote(m))}</div>
      ${m.status === "downloading"
        ? `<div class="model-bar"><i style="width:${m.progress}%"></i></div>` : ""}
    </div>`;
}

function renderModels() {
  const html = state.models.map((m) => modelHtml(m, m.id === state.config.stt_model)).join("");
  $("modelList").innerHTML = html;
  $("setupModels").innerHTML = html;
}

async function chooseModel(id) {
  saveConfig({ stt_model: id }, true);
  renderModels();
  const model = state.models.find((m) => m.id === id);
  if (model && !model.installed && model.status !== "downloading") {
    const [org, name] = id.split("/");
    try {
      await post(`/api/models/${org}/${name}/download`);
      toast("info", t("toast.downloading", { label: model.label }));
    } catch (err) { toast("error", err.message); }
  }
}

document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-model]");
  if (el) chooseModel(el.dataset.model);
});

function onModelProgress(data) {
  const m = state.models.find((x) => x.id === data.id);
  if (!m) return;
  Object.assign(m, data, { installed: data.status === "installed" || m.installed });
  if (data.status === "installed") toast("ok", t("toast.model_ready", { label: m.label }));
  if (data.status === "error") toast("error", t("toast.download_failed", { err: data.error }));
  renderModels();
}

/* ---------- tema ---------- */

const mediaDark = matchMedia("(prefers-color-scheme: dark)");
function applyTheme(theme) {
  const resolved = theme === "system" ? (mediaDark.matches ? "dark" : "light") : theme;
  document.documentElement.dataset.theme = resolved;
}
mediaDark.addEventListener("change", () => {
  if (state.config.theme === "system") applyTheme("system");
});

/* ---------- forstegangsoppsett ---------- */

function setupStep(n) {
  $$(".setup-page").forEach((p) => p.classList.toggle("is-on", p.dataset.page === String(n)));
  $$(".step").forEach((s) => {
    const i = Number(s.dataset.step);
    s.classList.toggle("is-on", i === n);
    s.classList.toggle("done", i < n);
  });
}

$$("[data-next]").forEach((b) => (b.onclick = () => setupStep(Number(b.dataset.next))));

$("setupDevice").onchange = (e) => {
  const opt = e.target.selectedOptions[0];
  saveConfig({ device: Number(e.target.value), device_name: opt?.textContent || "" }, true);
  $("deviceSelect").value = e.target.value;
};

function finishSetup() {
  $("setupScrim").hidden = true;
  saveConfig({ onboarded: true }, true);
}
$("setupSkip").onclick = finishSetup;
$("setupDone").onclick = finishSetup;

/* ---------- tastatur ---------- */

document.addEventListener("keydown", (e) => {
  const typing = /^(INPUT|TEXTAREA)$/.test(e.target.tagName) || e.target.isContentEditable;

  if (e.key === "Escape") {
    if (!$("exportMenu").hidden) return (exportMenu.hidden = true);
    if (!drawer.hidden) return closeDrawer();
    if (state.playing) return stopPlayback();
  }
  if (typing) return;

  if (e.code === "Space" && !document.body.classList.contains("no-capture")) {
    e.preventDefault(); $("toggleBtn").click();
  }
  if (e.key === "/") { e.preventDefault(); $("filterInput").focus(); }
  if (e.key === "," && (e.metaKey || e.ctrlKey)) { e.preventDefault(); openDrawer(); }
});

// Menyvalg fra skallet (Fil → Innstillinger osv.).
window.commscribe?.onMenu?.((action) => {
  if (action === "settings") openDrawer();
  if (action === "toggle") $("toggleBtn").click();
  if (action === "search") $("filterInput").focus();
});

/* ---------- utfylling ---------- */

function fillSelect(el, items, value) {
  el.innerHTML = items.map(([v, label]) =>
    `<option value="${esc(v)}">${esc(label)}</option>`).join("");
  if (value != null) el.value = value;
}

function fillConfig() {
  const c = state.config;
  $("engineSelect").value = c.stt_engine;
  $("langSelect").value = c.language;
  $("modeSelect").value = c.mode;
  $("targetSelect").value = c.target_language;
  $("targetRow").hidden = c.mode !== "translate";
  $("themeSelect").value = c.theme;
  $("autostartCapture").checked = !!c.autostart_capture;
  $("retentionSelect").value = String(c.retention_days);
  $("providerSelect").value = c.api_provider;
  $("apiModelInput").value = c.api_model;
  $("ollamaUrlInput").value = c.ollama_url || "";
  $("ollamaModelInput").value = c.ollama_model || "";
  $("monitorEnabled").checked = !!c.monitor_enabled;
  $("monitorRow").hidden = !c.monitor_enabled;
  if (c.monitor_device != null) $("monitorSelect").value = String(c.monitor_device);

  for (const [key, r] of Object.entries(ranges)) {
    r.input.value = c[key];
    r.render(c[key]);
  }
  drawThreshold(c.threshold_db);
  applyTheme(c.theme);
  updateEngineHints();
  renderKeyStatus();

  $("dataPath").textContent = c.data_dir || "";
  $("versionOut").textContent = c.version || "";
  $("sbVersion").textContent = `v${c.version || ""}`;
  $("sbEngine").textContent = c.stt_engine === "local"
    ? t("status.local", { model: (c.stt_model || "").split("/").pop() })
    : t("status.cloud", { provider: c.api_provider, model: c.api_model });
  applyCapabilities();
}

let lastStats = null;
function renderStats(stats) {
  lastStats = stats;
  $("sbStats").textContent = t("status.stats", { total: stats.total, today: stats.today });
}

async function loadDevices() {
  const d = await api("/api/devices");
  // Uten lydinngang er feilen forventet og allerede forklart i grensesnittet.
  if (d.error && !document.body.classList.contains("no-capture")) toast("error", d.error);


  const inputs = d.inputs.map((x) => [String(x.index), x.name]);
  fillSelect($("deviceSelect"), inputs);
  fillSelect($("setupDevice"), inputs);
  fillSelect($("monitorSelect"),
    [["", "Av"], ...d.outputs.map((x) => [String(x.index), x.name])]);

  // Enhetsindeksene kan ha flyttet seg siden sist. Navnet er den stabile
  // identiteten, så vi leter etter det først.
  const c = state.config;
  const byName = d.inputs.find((x) => x.name === c.device_name);
  const chosen = byName?.index ?? (d.inputs.some((x) => x.index === c.device)
    ? c.device : d.default_input);
  if (chosen != null && inputs.length) {
    $("deviceSelect").value = String(chosen);
    $("setupDevice").value = String(chosen);
  }
  if (!document.body.classList.contains("no-capture")) {
    $("sbDevice").textContent =
      $("deviceSelect").selectedOptions[0]?.textContent || t("status.no_device");
  }
}

/* ---------- oppstart ---------- */

(async () => {
  try {
    state.config = await api("/api/config");
    await I18N.load(state.config.ui_language);
    I18N.apply();
    fillLanguageSelects();
    fillSelect($("langSelect"), speechItems(state.config.languages), state.config.language);
    fillSelect($("targetSelect"),
      speechItems(state.config.languages.filter((v) => v !== "auto")),
      state.config.target_language);
    fillConfig();
    await loadDevices();

    const segments = await api("/api/segments?limit=300");
    bulkLoading = true;
    segments.forEach((s) => upsert(s));
    bulkLoading = false;
    applyFilter();

    const status = await api("/api/status");
    setRunning(status.running);
    setQueue(status.queue);
    renderStats(status.stats);

    await loadModels();
    if (!state.config.onboarded) $("setupScrim").hidden = false;

    connect();
    document.body.classList.remove("loading");

    // Statuslinja oppdateres sjelden - tallene endrer seg langsomt.
    setInterval(async () => {
      try {
        const s = await api("/api/status");
        renderStats(s.stats);
      } catch { /* backenden starter kanskje på nytt */ }
    }, 10000);
  } catch (err) {
    document.body.classList.remove("loading");
    toast("error", t("toast.no_contact", { err: err.message }), 15000);

  }
})();
