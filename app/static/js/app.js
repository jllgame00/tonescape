"use strict";

const $ = (id) => document.getElementById(id);
const form = $("search-form");
let searchController;
let analysisController;
let searchVersion = 0;
let analysisVersion = 0;
let toastTimer;
let lastTracks = [];

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function status(message = "", state = "") {
  $("status").textContent = message;
  $("status").className = `status ${state ? `is-${state}` : ""}`;
}

async function api(path, params, signal) {
  const response = await fetch(`${path}?${new URLSearchParams(params)}`, { signal, headers: { Accept: "application/json" } });
  let data;
  try { data = await response.json(); } catch { throw new Error("The service returned an unexpected response. Please try again."); }
  if (!response.ok) throw new Error(data.error?.message || "The service is unavailable. Please try again.");
  return data;
}

function safeArtwork(url) {
  try {
    const value = new URL(url);
    return value.protocol === "https:" && ["lastfm.freetls.fastly.net", "lastfm-img2.akamaized.net", "userserve-ak.last.fm"].includes(value.hostname) ? value.href : null;
  } catch { return null; }
}

function imageFor(url, alt, onError) {
  if (!safeArtwork(url)) return null;
  const image = node("img");
  image.src = url;
  image.alt = alt;
  image.loading = "lazy";
  image.referrerPolicy = "no-referrer";
  image.addEventListener("error", () => { image.remove(); if (onError) onError(); }, { once: true });
  return image;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = $("search-input").value.trim();
  if (!query) { status("Enter a song or artist name to begin.", "error"); return; }
  const version = ++searchVersion;
  ++analysisVersion;
  searchController?.abort();
  analysisController?.abort();
  searchController = new AbortController();
  $("search-submit").disabled = true;
  $("search-form").setAttribute("aria-busy", "true");
  $("analysis-result").hidden = true;
  $("analysis-result").removeAttribute("aria-busy");
  document.body.classList.remove("has-result");
  $("search-section").hidden = true;
  $("search-section").removeAttribute("aria-busy");
  lastTracks = [];
  status("Searching the Last.fm catalogue…", "loading");
  try {
    const data = await api("/api/search", { q: query, mode: new FormData(form).get("mode") }, searchController.signal);
    if (version !== searchVersion) return;
    lastTracks = data.tracks;
    renderTracks(data.tracks);
    if (!data.tracks.length) status("No tracks found. Try another title, or select Artists to find an artist’s top tracks.");
    else status(`${data.tracks.length} tracks found. Select one to discover its colors.`);
  } catch (error) {
    if (error.name !== "AbortError" && version === searchVersion) status(error instanceof TypeError ? "Could not connect to TONESCAPE. Check your connection and try again." : error.message, "error");
  } finally {
    if (version === searchVersion) {
      $("search-submit").disabled = false;
      $("search-form").removeAttribute("aria-busy");
    }
  }
});

function renderTracks(tracks) {
  const list = $("search-results");
  list.replaceChildren();
  $("result-count").textContent = `${String(tracks.length).padStart(2, "0")} TRACKS`;
  for (const [index, track] of tracks.entries()) {
    const button = node("button", "track-card");
    button.type = "button";
    button.setAttribute("aria-label", `Analyze ${track.title} by ${track.artist}`);
    button.setAttribute("aria-pressed", "false");
    const art = node("span", "track-card-art", String(index + 1).padStart(2, "0"));
    const image = imageFor(track.artwork, "");
    if (image) art.replaceChildren(image);
    const info = node("span", "track-card-info");
    info.append(node("strong", "", track.title), node("small", "", track.artist));
    const arrow = node("span", "card-arrow", "↗");
    arrow.setAttribute("aria-hidden", "true");
    button.append(art, info, arrow);
    button.addEventListener("click", () => selectTrack(track, button));
    list.append(button);
  }
  $("search-section").hidden = !tracks.length;
}

async function selectTrack(track, button) {
  const version = ++analysisVersion;
  analysisController?.abort();
  analysisController = new AbortController();
  document.querySelectorAll(".track-card").forEach((card) => card.setAttribute("aria-pressed", String(card === button)));
  $("analysis-result").hidden = true;
  $("search-section").setAttribute("aria-busy", "true");
  status(`Interpreting the mood tags for ${track.title}…`, "loading");
  try {
    const data = await api("/api/analyze", { artist: track.artist, track: track.title }, analysisController.signal);
    if (version !== analysisVersion) return;
    renderAnalysis(data);
    $("search-section").hidden = true;
    $("analysis-result").hidden = false;
    document.body.classList.add("has-result");
    status();
    $("track-title").focus({ preventScroll: true });
    $("analysis-result").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    if (error.name !== "AbortError" && version === analysisVersion) status(error instanceof TypeError ? "The connection was interrupted. Select the track to retry." : error.message, "error");
  } finally {
    if (version === analysisVersion) $("search-section").removeAttribute("aria-busy");
  }
}

function renderAnalysis(data) {
  const { track, analysis } = data;
  $("track-title").textContent = track.title;
  $("track-artist").textContent = track.artist;
  $("track-album").textContent = track.album || "";
  $("source-label").textContent = { track: "Track tags", artist: "Artist tag fallback", neutral: "Neutral fallback" }[data.source];
  $("keywords").replaceChildren(...analysis.keywords.map((word) => node("span", "keyword", word)));
  $("top-tags").replaceChildren(...data.tags.map((tag) => node("span", "tag", tag.name)));
  if (!data.tags.length) $("top-tags").append(node("span", "muted", "No community tags available"));
  const artwork = $("artwork");
  artwork.querySelectorAll("img").forEach((image) => image.remove());
  const image = imageFor(track.artwork, `${track.album || track.title} album artwork`);
  if (image) artwork.append(image);
  const lastfm = $("lastfm-link");
  lastfm.hidden = true;
  lastfm.removeAttribute("href");
  try {
    const url = new URL(track.url);
    if (url.protocol === "https:" && ["www.last.fm", "last.fm"].includes(url.hostname)) {
      lastfm.href = url.href;
      lastfm.hidden = false;
    }
  } catch { /* Metadata link is optional. */ }
  const colors = analysis.palette;
  document.documentElement.style.setProperty("--mood-primary", colors[0].hex);
  document.documentElement.style.setProperty("--mood-secondary", colors[1].hex);
  document.documentElement.style.setProperty("--mood-bg", colors[4].hex);
  document.documentElement.style.setProperty("--result-gradient", analysis.gradient);
  $("palette").replaceChildren(...colors.map((color, index) => {
    const swatch = node("button", "swatch");
    swatch.type = "button";
    swatch.style.backgroundColor = color.hex;
    swatch.style.color = color.text;
    swatch.setAttribute("aria-label", `Copy ${color.label} ${color.hex}`);
    const top = node("span", "swatch-top");
    top.append(node("span", "", String(index + 1).padStart(2, "0")), node("span", "", "↗"));
    const bottom = node("span", "swatch-bottom");
    bottom.append(node("span", "swatch-label", color.label), node("span", "swatch-hex", color.hex));
    swatch.append(top, bottom);
    swatch.addEventListener("click", () => copyColor(color.hex));
    return swatch;
  }));
  $("axes").replaceChildren(...Object.entries(analysis.axes).map(([name, value]) => {
    const axis = node("div", "axis");
    const label = name[0].toUpperCase() + name.slice(1);
    const header = node("div", "axis-label");
    header.append(node("span", "", label), node("strong", "", Math.round(value)));
    const bar = node("div", "axis-track");
    bar.setAttribute("role", "meter");
    bar.setAttribute("aria-label", label);
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", "100");
    bar.setAttribute("aria-valuenow", String(value));
    const fill = node("div", "axis-fill");
    fill.style.width = `${value}%`;
    bar.append(fill);
    axis.append(header, bar);
    return axis;
  }));
  $("confidence-value").textContent = `${analysis.confidence} / 100`;
  $("confidence-notice").textContent = analysis.notice || `Interpreted ${analysis.coverage}% of eligible tag weight. Confidence describes tag coverage, not scientific accuracy.`;
  $("warnings").textContent = data.warnings.join(" ");
  $("color-explanation").textContent = analysis.explanation;
  $("contributions").replaceChildren(...analysis.contributions.map((item) => {
    const row = node("div", "contribution");
    const heading = node("div", "contribution-heading");
    heading.append(node("span", "", item.tag), node("span", "", `${item.share}%`));
    row.append(heading, node("small", "", `Matched ${item.matched} · count ${item.count} · ${item.match_quality < 1 ? "family match" : "direct match"}`));
    row.append(node("small", "", Object.entries(item.contribution).map(([key, value]) => `${key[0].toUpperCase()} ${value.toFixed(1)}`).join(" / ") + " axis points"));
    return row;
  }));
  $("analysis-result").querySelector("details").open = false;
}

async function copyColor(hex) {
  try {
    if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
    await navigator.clipboard.writeText(hex);
    toast(`${hex} copied to clipboard`);
  } catch {
    // Visible, selectable fallback when the browser blocks clipboard access.
    toast(`Clipboard unavailable. Copy this value: ${hex}`);
  }
}

function toast(message) {
  clearTimeout(toastTimer);
  $("toast").textContent = message;
  $("toast").hidden = false;
  toastTimer = setTimeout(() => { $("toast").hidden = true; }, 4200);
}

$("back-to-results").addEventListener("click", () => {
  ++analysisVersion;
  analysisController?.abort();
  $("analysis-result").hidden = true;
  $("search-section").hidden = !lastTracks.length;
  document.body.classList.remove("has-result");
  status();
  const selected = document.querySelector('.track-card[aria-pressed="true"]');
  (selected || $("search-input")).focus();
});

fetch("/health", { headers: { Accept: "application/json" } }).then((response) => response.json()).then((data) => {
  if (data.lastfm_configured === false) {
    $("setup-message").textContent = "Live search is waiting for a Last.fm API key. Service owner: set LASTFM_API_KEY in .env locally or in Render Environment, then restart. Your key stays on the server.";
    $("setup-message").hidden = false;
  }
}).catch(() => { /* Search provides actionable network errors. */ });
