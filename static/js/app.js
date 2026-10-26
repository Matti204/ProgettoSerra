"use strict";

const $ = (id) => document.getElementById(id);
let state = null;
let online = false;
let busy = false;
let polling = false;
let revision = 0;
let authNeeded = false;
let toastTimer;
// Memoria della scheda: nessun token in HTML, URL, cookie o localStorage.
let token = "";

async function api(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 6000);
  const headers = {"X-Greenhouse-Request": "1", ...options.headers};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body) headers["Content-Type"] = "application/json";
  try {
    const response = await fetch(path, {...options, headers, signal: controller.signal, cache: "no-store", credentials: "omit"});
    const body = await response.json();
    if (response.status === 401) {
      authNeeded = true;
      $("change-token").hidden = false;
      if (!$("auth-dialog").open) $("auth-dialog").showModal();
    }
    if (!response.ok) {
      const error = new Error(body.error || "Il comando non è stato completato.");
      error.status = response.status;
      throw error;
    }
    return body;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Il server non risponde. Verifica la connessione.");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function toast(message, error = false) {
  clearTimeout(toastTimer);
  $("toast").textContent = message;
  $("toast").classList.toggle("error", error);
  $("toast").hidden = false;
  toastTimer = setTimeout(() => { $("toast").hidden = true; }, 4200);
}

function controls() {
  const disabled = busy || !online || !state || Boolean(state.lamp.error) || !state.system.healthy;
  for (const id of ["mode-manual", "mode-auto", "on-time", "off-time", "save-schedule"]) $(id).disabled = disabled;
  $("lamp-toggle").disabled = disabled || state.lamp.mode !== "manual" || state.lamp.on === null;
}

function connection(connected) {
  online = connected;
  $("lamp-card").classList.toggle("is-offline", !connected);
  $("connection").classList.toggle("offline", !connected);
  $("connection-text").textContent = connected ? "Connesso" : "Non connesso";
  if (!connected) {
    $("lamp-card").classList.remove("is-on");
    $("lamp-state").textContent = "Non disponibile";
    $("lamp-badge").textContent = "Offline";
    $("lamp-description").textContent = "Stato attuale non confermato";
    $("lamp-help").textContent = "Riconnessione automatica in corso. I comandi sono disabilitati.";
    for (const id of ["temperature", "humidity"]) {
      $(id + "-value").textContent = "Non disponibile";
      $(id + "-value").classList.add("unavailable");
      $(id + "-tag").textContent = "Offline";
      $(id + "-note").textContent = "Nessuna lettura aggiornata";
    }
  }
  controls();
}

function drawSchedule(schedule) {
  const minutes = (value) => { const [h, m] = value.split(":").map(Number); return h * 60 + m; };
  const on = minutes(schedule.on_time) / 14.4;
  const off = minutes(schedule.off_time) / 14.4;
  const active = "#a9bc8a", inactive = "#edf0e7";
  const stops = schedule.overnight
    ? `${active} 0%, ${active} ${off}%, ${inactive} ${off}%, ${inactive} ${on}%, ${active} ${on}%, ${active} 100%`
    : `${inactive} 0%, ${inactive} ${on}%, ${active} ${on}%, ${active} ${off}%, ${inactive} ${off}%, ${inactive} 100%`;
  $("daylight-track").style.background = `linear-gradient(to right, ${stops})`;
  const duration = (minutes(schedule.off_time) - minutes(schedule.on_time) + 1440) % 1440;
  const hours = Math.floor(duration / 60), mins = duration % 60;
  $("schedule-duration").textContent = `${hours} h${mins ? ` ${mins} min` : ""} di luce al giorno · ${state.system.timezone}`;
}

function render(data, syncForm = false) {
  state = data;
  connection(true);
  const {lamp, sensors, system} = data;
  const mock = system.hardware_mode === "mock";
  $("environment-notice").classList.toggle("production", !mock);
  $("environment-text").textContent = mock
    ? "Modalità simulazione attiva. Lampada virtuale e letture dimostrative; nessun hardware collegato."
    : "Hardware reale attivo. Lo stato mostra il comando del relè, senza conferma fisica della lampada.";
  $("environment-tag").textContent = mock ? "SIMULAZIONE" : "RASPBERRY PI";
  $("lamp-card").classList.toggle("is-on", lamp.on === true && !lamp.error);
  $("lamp-state").textContent = lamp.on === null ? "Sconosciuta" : lamp.on ? "Accesa" : "Spenta";
  $("lamp-badge").textContent = lamp.error ? "Errore" : lamp.on === null ? "Sconosciuta" : lamp.on ? "Luce attiva" : "Luce spenta";
  $("lamp-description").textContent = mock ? "Lampada virtuale · simulazione" : "Stato logico del comando relè";
  $("toggle-label").textContent = lamp.mode === "auto" ? "Automatico" : lamp.on ? "Spegni" : "Accendi";
  $("mode-manual").setAttribute("aria-pressed", String(lamp.mode === "manual"));
  $("mode-auto").setAttribute("aria-pressed", String(lamp.mode === "auto"));
  $("lamp-help").textContent = lamp.mode === "auto"
    ? `Gestita ogni giorno dalle ${lamp.schedule.on_time} alle ${lamp.schedule.off_time}${lamp.schedule.overnight ? " del giorno successivo" : ""}.`
    : "Sei tu a decidere. Al riavvio la lampada in manuale resta spenta.";
  for (const sensor of sensors) {
    const value = $(sensor.id + "-value");
    if (!value) continue;
    const unavailable = sensor.value === null;
    value.replaceChildren();
    value.classList.toggle("unavailable", unavailable);
    if (unavailable) value.textContent = "Non disponibile";
    else {
      value.append(document.createTextNode(new Intl.NumberFormat("it-IT", {maximumFractionDigits: 1}).format(sensor.value)));
      const unit = document.createElement("span"); unit.textContent = sensor.unit; value.append(unit);
    }
    $(sensor.id + "-tag").textContent = sensor.status === "simulated" ? "Simulato" : unavailable ? "Assente" : "Collegato";
    $(sensor.id + "-note").textContent = sensor.status === "simulated" ? "Dato dimostrativo, non misurato" : unavailable ? "Nessun sensore configurato" : "Lettura dal sensore";
  }
  if (syncForm || !$("schedule-form").dataset.dirty) {
    $("on-time").value = lamp.schedule.on_time;
    $("off-time").value = lamp.schedule.off_time;
  }
  drawSchedule(lamp.schedule);
  $("schedule-summary").textContent = lamp.mode === "auto"
    ? `Attiva ogni giorno${lamp.schedule.overnight ? ", con passaggio alla mezzanotte" : ""}. Funziona anche a browser chiuso.`
    : "Orari salvati. Seleziona la modalità automatica per applicarli.";
  $("system-hardware").textContent = mock ? "Simulazione" : "GPIO reale";
  $("system-scheduler").textContent = system.scheduler_healthy === true ? "In esecuzione" : system.scheduler_healthy === null ? "Test" : "Non disponibile";
  $("system-network").textContent = system.network_mode === "local" ? "Solo locale" : "Rete locale · protetta";
  const uptime = system.uptime_seconds;
  $("system-uptime").textContent = uptime < 60 ? "Meno di un minuto" : uptime < 3600 ? `${Math.floor(uptime / 60)} min` : `${Math.floor(uptime / 3600)} h ${Math.floor(uptime % 3600 / 60)} min`;
  const current = new Date(system.server_time);
  $("system-clock").textContent = current.toLocaleTimeString("it-IT", {timeZone: system.timezone, hour: "2-digit", minute: "2-digit"});
  $("date-label").textContent = current.toLocaleDateString("it-IT", {timeZone: system.timezone, day: "numeric", month: "long", year: "numeric"});
  $("system-note").textContent = system.healthy ? "Il sistema funziona anche con questa pagina chiusa." : "Il sistema richiede attenzione. Controlla il messaggio di errore.";
  $("device-relay").textContent = mock ? "Controller virtuale · nessun GPIO utilizzato" : `BCM ${system.relay.pin} · ${system.relay.active_high ? "Active-high" : "Active-low"}`;
  $("device-relay-status").textContent = lamp.error ? "Errore" : mock ? "Virtuale" : "Configurato";
  $("device-sensors").textContent = mock ? "2 letture dimostrative · simulazione" : "Nessun sensore configurato";
  $("last-update").textContent = `Aggiornato alle ${current.toLocaleTimeString("it-IT", {timeZone: system.timezone})}`;
  $("error-banner").hidden = system.healthy;
  $("error-banner").textContent = lamp.error || (system.healthy ? "" : "Programmazione non disponibile. Riavvia il servizio.");
  $("change-token").hidden = system.network_mode !== "lan";
  controls();
}

async function refresh() {
  if (busy || polling || authNeeded) return;
  polling = true;
  const currentRevision = revision;
  try {
    const data = await api("/api/status");
    if (currentRevision === revision) render(data);
  } catch (error) {
    if (currentRevision === revision) {
      connection(false);
      $("error-banner").textContent = error.status === 401 ? "Accedi per visualizzare la serra." : "Connessione al server interrotta. Riprovo automaticamente…";
      $("error-banner").hidden = false;
    }
  } finally { polling = false; }
}

async function command(path, method, body, message, syncForm = false) {
  if (busy || !online) return;
  busy = true; revision++; controls();
  try {
    render(await api(path, {method, body: JSON.stringify(body)}), syncForm);
    if (syncForm) delete $("schedule-form").dataset.dirty;
    toast(message);
    if (syncForm) {
      $("schedule-feedback").textContent = "Orari salvati correttamente.";
      $("schedule-feedback").classList.remove("error");
    }
  } catch (error) {
    toast(error.message, true);
    if (syncForm) {
      $("schedule-feedback").textContent = error.message;
      $("schedule-feedback").classList.add("error");
    }
    // Dopo un timeout l'esito del comando è incerto: rileggere sempre il server.
    try { render(await api("/api/status")); } catch { connection(false); }
  } finally { busy = false; controls(); }
}

$("lamp-toggle").addEventListener("click", () => command("/api/lamp", "POST", {on: !state.lamp.on}, state.lamp.on ? "Lampada spenta." : "Lampada accesa."));
$("mode-manual").addEventListener("click", () => {
  if (state?.lamp.mode !== "manual") command("/api/settings", "PUT", {mode: "manual"}, "Modalità manuale attiva. Lampada spenta.");
});
$("mode-auto").addEventListener("click", () => {
  if (state?.lamp.mode !== "auto") command("/api/settings", "PUT", {mode: "auto"}, "Programmazione automatica attiva.");
});
$("schedule-form").addEventListener("input", () => { $("schedule-form").dataset.dirty = "true"; $("schedule-feedback").textContent = "Modifiche da salvare."; });
$("schedule-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const on = $("on-time").value, off = $("off-time").value;
  if (on === off) {
    $("schedule-feedback").textContent = "Scegli orari di accensione e spegnimento diversi.";
    $("schedule-feedback").classList.add("error");
    return;
  }
  command("/api/settings", "PUT", {on_time: on, off_time: off}, "Programmazione salvata.", true);
});
$("auth-dialog").addEventListener("cancel", (event) => event.preventDefault());
$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  token = $("api-token").value;
  const submit = $("auth-form").querySelector("button"); submit.disabled = true;
  try {
    const data = await api("/api/status");
    authNeeded = false; $("api-token").value = ""; $("auth-feedback").textContent = "";
    $("auth-dialog").close(); render(data);
  } catch (error) {
    token = ""; $("auth-feedback").textContent = error.message;
    $("auth-feedback").classList.add("error"); connection(false);
  } finally { submit.disabled = false; }
});
$("change-token").addEventListener("click", () => { $("auth-dialog").showModal(); });
document.querySelectorAll(".nav-link").forEach((link) => link.addEventListener("click", () => {
  document.querySelectorAll(".nav-link").forEach((item) => item.classList.toggle("active", item === link));
}));
window.addEventListener("online", refresh);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
refresh();
setInterval(refresh, 3000);
