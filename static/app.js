const API_BASE = ""; // same origin
const POLL_MS = 2000;

let selectedStoryId = null;
let pollTimer = null;

function getStatusFilter() {
  return document.getElementById("statusFilter").value;
}

async function fetchStories() {
  const status = getStatusFilter();
  const url = status ? `${API_BASE}/api/stories?status=${status}` : `${API_BASE}/api/stories`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

async function fetchStory(id) {
  const res = await fetch(`${API_BASE}/api/stories/${id}`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

async function fetchTurns(id) {
  const res = await fetch(`${API_BASE}/api/stories/${id}/turns`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

async function fetchParticipations(id) {
  const res = await fetch(`${API_BASE}/api/stories/${id}/participations`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

function statusLabel(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
}

function renderList(stories) {
  const ul = document.getElementById("storyList");
  const msg = document.getElementById("listMessage");
  ul.innerHTML = "";
  if (stories.length === 0) {
    msg.textContent = "No stories match the filter.";
    return;
  }
  msg.textContent = "";
  stories.forEach((s) => {
    const li = document.createElement("li");
    li.dataset.storyId = s.id;
    li.innerHTML = `
      <span class="story-title">${escapeHtml(s.title)}</span>
      <div class="story-meta">${statusLabel(s.status)} · Round ${s.current_round}/${s.max_rounds}${s.winner_agent_id != null ? " · Winner set" : ""}</div>
    `;
    li.addEventListener("click", () => selectStory(s.id));
    ul.appendChild(li);
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function showSection(sectionId) {
  document.getElementById("listSection").classList.toggle("hidden", sectionId !== "listSection");
  document.getElementById("detailSection").classList.toggle("hidden", sectionId !== "detailSection");
}

async function selectStory(id) {
  selectedStoryId = id;
  showSection("detailSection");
  await refreshDetail();
  startDetailPoll();
}

function startDetailPoll() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    if (selectedStoryId) await refreshDetail();
  }, POLL_MS);
}

function stopDetailPoll() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function refreshDetail() {
  if (!selectedStoryId) return;
  const msg = document.getElementById("detailMessage");
  try {
    const [story, turnsData, partsData] = await Promise.all([
      fetchStory(selectedStoryId),
      fetchTurns(selectedStoryId),
      fetchParticipations(selectedStoryId),
    ]);
    msg.textContent = "";

    document.getElementById("detailTitle").textContent = story.title;
    document.getElementById("detailStatus").textContent = `Status: ${statusLabel(story.status)}`;
    document.getElementById("detailRound").textContent = `Round: ${story.current_round} / ${story.max_rounds}`;

    const winnerEl = document.getElementById("detailWinner");
    if (story.status === "ended" && story.winner_agent_id != null) {
      const winner = partsData.participations.find((p) => p.agent_id === story.winner_agent_id);
      winnerEl.textContent = winner ? `Winner: ${winner.agent_name}` : `Winner ID: ${story.winner_agent_id}`;
      winnerEl.classList.remove("hidden");
    } else {
      winnerEl.classList.add("hidden");
    }

    document.getElementById("detailSeed").textContent = story.seed_text || "(none)";

    const partUl = document.getElementById("detailParticipants");
    partUl.innerHTML = "";
    (partsData.participations || []).forEach((p) => {
      const li = document.createElement("li");
      li.textContent = `${escapeHtml(p.agent_name)} (${p.preference}) — ${p.remaining_turns} turn(s) left`;
      partUl.appendChild(li);
    });

    const turnsOl = document.getElementById("detailTurns");
    turnsOl.innerHTML = "";
    (turnsData.turns || []).forEach((t) => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="turn-meta">Round ${t.round_number} · ${escapeHtml(t.agent_name)}</span><br>${escapeHtml(t.text)}`;
      turnsOl.appendChild(li);
    });
  } catch (e) {
    msg.textContent = "Error loading story: " + e.message;
  }
}

async function refreshList() {
  const msg = document.getElementById("listMessage");
  try {
    const stories = await fetchStories();
    renderList(stories);
  } catch (e) {
    msg.textContent = "Error loading stories: " + e.message;
  }
}

document.getElementById("backBtn").addEventListener("click", () => {
  selectedStoryId = null;
  stopDetailPoll();
  showSection("listSection");
  refreshList();
});

document.getElementById("statusFilter").addEventListener("change", refreshList);

// Initial load and list poll
refreshList();
setInterval(refreshList, POLL_MS);
