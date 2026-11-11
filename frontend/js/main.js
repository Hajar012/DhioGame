import { ApiError, api } from "./api.js";
import { clearSession, loadSession, saveSession } from "./session.js";

const $ = (id) => document.getElementById(id);

const dom = {
  homeView: $("home-view"),
  lobbyView: $("lobby-view"),
  createForm: $("create-form"),
  createNickname: $("create-nickname"),
  createMode: $("create-mode"),
  createViewing: $("create-viewing"),
  createDrawing: $("create-drawing"),
  joinForm: $("join-form"),
  joinCode: $("join-code"),
  joinNickname: $("join-nickname"),
  roomCode: $("room-code"),
  copyCodeBtn: $("copy-code-btn"),
  connectionStatus: $("connection-status"),
  connectionLabel: $("connection-label"),
  leaveBtn: $("leave-btn"),
  playersList: $("players-list"),
  playersSummary: $("players-summary"),
  readyCount: $("ready-count"),
  readyBtn: $("ready-btn"),
  settingsMode: $("settings-mode"),
  settingsViewing: $("settings-viewing"),
  settingsDrawing: $("settings-drawing"),
  settingsNote: $("settings-note"),
  settingsSummary: $("settings-summary"),
  uploadForm: $("upload-form"),
  imageInput: $("image-input"),
  uploadBtn: $("upload-btn"),
  uploadProgress: $("upload-progress"),
  imagesList: $("images-list"),
  imagesSummary: $("images-summary"),
  imagesHint: $("images-hint"),
  imagesComplete: $("images-complete"),
  toast: $("toast"),
};

const MODE_LABELS = {
  same_image: "Same image",
  random_assignment: "Random assignment",
};
const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const EXPIRED_SOCKET_CODES = new Set([4401, 4404, 4410]);

let session = null;
let roomState = null;
let socket = null;
let heartbeatTimer = null;
let reconnectTimer = null;
let reconnectAttempts = 0;
let toastTimer = null;
let imagesSignature = "";
let imagesRequestId = 0;
let imageObjectUrls = [];

function init() {
  bindEvents();
  prefillJoinCodeFromUrl();

  const saved = loadSession();
  if (saved) {
    session = saved;
    restoreSession();
  }
}

function bindEvents() {
  dom.createForm.addEventListener("submit", handleCreateRoom);
  dom.joinForm.addEventListener("submit", handleJoinRoom);
  dom.readyBtn.addEventListener("click", toggleReady);
  dom.copyCodeBtn.addEventListener("click", copyRoomCode);
  dom.leaveBtn.addEventListener("click", () => leaveRoom());
  dom.settingsMode.addEventListener("change", handleSettingsChange);
  dom.settingsViewing.addEventListener("change", handleSettingsChange);
  dom.settingsDrawing.addEventListener("change", handleSettingsChange);
  dom.uploadForm.addEventListener("submit", handleUpload);

  dom.imagesList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-delete-image]");
    if (!button) return;
    deleteImage(button.dataset.deleteImage);
  });

  window.addEventListener("beforeunload", () => {
    if (socket) {
      socket.onclose = null;
      socket.close();
    }
  });
}

function prefillJoinCodeFromUrl() {
  const code = new URLSearchParams(window.location.search).get("room");
  if (code) {
    dom.joinCode.value = code.toUpperCase();
  }
}

async function handleCreateRoom(event) {
  event.preventDefault();
  const nickname = dom.createNickname.value.trim();
  if (!nickname) {
    showToast("Choose a nickname first.");
    return;
  }

  const settings = {
    mode: dom.createMode.value,
    viewing_duration_seconds: Number(dom.createViewing.value),
    drawing_duration_seconds:
      dom.createDrawing.value === ""
        ? null
        : Number(dom.createDrawing.value),
  };

  setFormBusy(dom.createForm, true);
  try {
    const result = await api.createRoom({ nickname, settings });
    beginSession(result);
    showToast("Room created. Share the code with your friends.", "success");
  } catch (error) {
    handleError(error);
  } finally {
    setFormBusy(dom.createForm, false);
  }
}

async function handleJoinRoom(event) {
  event.preventDefault();
  const roomCode = dom.joinCode.value.trim().toUpperCase();
  const nickname = dom.joinNickname.value.trim();
  if (!roomCode || !nickname) {
    showToast("Enter the room code and a nickname.");
    return;
  }

  setFormBusy(dom.joinForm, true);
  try {
    const result = await api.joinRoom({ room_code: roomCode, nickname });
    beginSession(result);
    showToast("You joined the room.", "success");
  } catch (error) {
    handleError(error);
  } finally {
    setFormBusy(dom.joinForm, false);
  }
}

function beginSession(result) {
  session = {
    roomCode: result.room.code,
    playerId: result.player.id,
    token: result.token,
    nickname: result.player.nickname,
  };
  saveSession(session);
  enterLobby(result.room);
}

async function restoreSession() {
  setConnection("connecting");
  try {
    const state = await api.getRoom(session.roomCode, session.token);
    const me = state.players.find((player) => player.id === session.playerId);
    if (!me) {
      throw new ApiError("Your player is no longer in this room.", 401);
    }
    session.nickname = me.nickname;
    saveSession(session);
    enterLobby(state);
    showToast("Session restored.", "success");
  } catch (error) {
    if (error instanceof ApiError) {
      if ([401, 404, 410].includes(error.status)) {
        clearSession();
        session = null;
        setConnection("offline");
        showToast("Your previous room session has expired.");
        return;
      }
    }
    handleError(error);
  }
}

function enterLobby(state) {
  roomState = state;
  dom.homeView.classList.add("hidden");
  dom.lobbyView.classList.remove("hidden");

  const url = new URL(window.location.href);
  url.searchParams.set("room", state.code);
  window.history.replaceState({}, "", url);

  renderLobby(state);
  connectSocket();
}

function renderLobby(state) {
  if (!state || !session) return;
  roomState = state;
  dom.roomCode.textContent = state.code;

  const me = state.players.find((player) => player.id === session.playerId);
  if (!me) {
    endSession("Your player is no longer in this room.");
    return;
  }

  dom.playersSummary.textContent =
    `${state.player_count} of ${state.max_players} players` +
    (state.player_count < state.min_players
      ? ` · ${state.min_players - state.player_count} more needed`
      : "");
  dom.readyCount.textContent = `${state.ready_count} ready`;

  renderPlayers(state, me);

  dom.readyBtn.textContent = me.is_ready
    ? "I'm ready — tap to undo"
    : "I'm ready";
  dom.readyBtn.classList.toggle("is-ready", me.is_ready);
  dom.readyBtn.disabled = false;

  renderSettings(state, me.is_host);
  renderImages(state, me.is_host);
}

function renderPlayers(state, me) {
  dom.playersList.replaceChildren();

  for (const player of state.players) {
    const row = document.createElement("li");
    row.className = "player-row";

    const avatar = document.createElement("div");
    avatar.className = "player-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = initials(player.nickname);

    const main = document.createElement("div");
    main.className = "player-main";

    const nameLine = document.createElement("div");
    nameLine.className = "player-name-line";

    const name = document.createElement("span");
    name.className = "player-name";
    name.textContent = player.nickname;
    nameLine.append(name);

    if (player.is_host) nameLine.append(makeBadge("Host", "badge-host"));
    if (player.id === me.id) nameLine.append(makeBadge("You", "badge-you"));
    nameLine.append(
      player.is_ready
        ? makeBadge("Ready", "badge-ready")
        : makeBadge("Not ready", "badge-waiting"),
    );

    const meta = document.createElement("div");
    meta.className = "player-meta";
    const dot = document.createElement("span");
    dot.className = `online-dot ${player.connection_status === "online" ? "" : "offline"}`;
    const status = document.createElement("span");
    status.textContent =
      player.connection_status === "online" ? "Online" : "Offline";
    meta.append(dot, status);

    main.append(nameLine, meta);
    row.append(avatar, main);
    dom.playersList.append(row);
  }
}

function renderSettings(state, isHost) {
  const settings = state.settings;
  dom.settingsMode.disabled = !isHost;
  dom.settingsViewing.disabled = !isHost;
  dom.settingsDrawing.disabled = !isHost;

  dom.settingsMode.value = settings.mode;
  dom.settingsViewing.value = String(settings.viewing_duration_seconds);
  dom.settingsDrawing.value =
    settings.drawing_duration_seconds == null
      ? ""
      : String(settings.drawing_duration_seconds);

  dom.settingsNote.textContent = isHost
    ? "You control these settings. Changes sync instantly."
    : "Only the host can change these settings.";
  dom.settingsSummary.textContent =
    `${MODE_LABELS[settings.mode]} · ` +
    `${settings.viewing_duration_seconds}s view · ` +
    formatDrawingDuration(settings.drawing_duration_seconds);
}

function renderImages(state, isHost) {
  dom.imagesSummary.textContent =
    `${state.uploaded_images} / ${state.required_images} uploaded`;
  dom.imagesHint.textContent =
    state.settings.mode === "same_image"
      ? "Same-image mode needs exactly one reference image."
      : `Random assignment needs one image per player (${state.required_images}).`;

  dom.uploadForm.classList.toggle(
    "hidden",
    !isHost || state.uploads_complete,
  );
  dom.imagesComplete.classList.toggle("hidden", !state.uploads_complete);

  if (!isHost) {
    dom.imagesList.replaceChildren(
      makeEmptyState("The host manages the reference images."),
    );
    return;
  }

  const signature = `${state.uploaded_images}:${state.settings.mode}`;
  if (signature !== imagesSignature) {
    imagesSignature = signature;
    loadImages();
  }
}

async function loadImages() {
  if (!session) return;
  const currentSession = session;
  const requestId = ++imagesRequestId;

  try {
    const images = await api.listImages(
      currentSession.roomCode,
      currentSession.token,
    );
    const entries = await Promise.all(
      images.map(async (image) => {
        let objectUrl = null;
        try {
          const blob = await api.fetchImageBlob(
            currentSession.roomCode,
            currentSession.token,
            image.id,
          );
          objectUrl = URL.createObjectURL(blob);
        } catch {
          objectUrl = null;
        }
        return { image, objectUrl };
      }),
    );

    if (requestId !== imagesRequestId) {
      for (const entry of entries) {
        if (entry.objectUrl) URL.revokeObjectURL(entry.objectUrl);
      }
      return;
    }

    revokeImageUrls();
    imageObjectUrls = entries
      .map((entry) => entry.objectUrl)
      .filter(Boolean);
    renderImageCards(entries);
  } catch (error) {
    if (error instanceof ApiError && [401, 410].includes(error.status)) {
      endSession("Your room session has expired.");
      return;
    }
    dom.imagesList.replaceChildren(
      makeEmptyState("Could not load image previews."),
    );
  }
}

function renderImageCards(entries) {
  dom.imagesList.replaceChildren();

  if (!entries.length) {
    dom.imagesList.append(makeEmptyState("No reference images uploaded yet."));
    return;
  }

  for (const { image, objectUrl } of entries) {
    const card = document.createElement("li");
    card.className = "image-card";

    if (objectUrl) {
      const preview = document.createElement("img");
      preview.src = objectUrl;
      preview.alt = image.original_filename || "Reference image";
      card.append(preview);
    } else {
      const preview = document.createElement("div");
      preview.className = "empty-state";
      preview.textContent = "Preview unavailable";
      card.append(preview);
    }

    const copy = document.createElement("div");
    copy.className = "image-copy";

    const text = document.createElement("div");
    const name = document.createElement("p");
    name.className = "image-name";
    name.textContent = image.original_filename || "Reference image";
    const size = document.createElement("p");
    size.className = "image-size";
    size.textContent = formatFileSize(image.file_size);
    text.append(name, size);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "delete-image";
    remove.dataset.deleteImage = image.id;
    remove.textContent = "Delete";

    copy.append(text, remove);
    card.append(copy);
    dom.imagesList.append(card);
  }
}

async function toggleReady() {
  if (!session || !roomState) return;
  const me = currentPlayer();
  if (!me) return;

  dom.readyBtn.disabled = true;
  try {
    const state = await api.setReady(
      session.roomCode,
      session.token,
      !me.is_ready,
    );
    renderLobby(state);
  } catch (error) {
    if (error instanceof ApiError && [401, 410].includes(error.status)) {
      endSession("Your room session has expired.");
      return;
    }
    handleError(error);
    dom.readyBtn.disabled = false;
  }
}

async function handleSettingsChange() {
  if (!session || !roomState) return;
  const me = currentPlayer();
  if (!me?.is_host) return;

  const payload = {
    mode: dom.settingsMode.value,
    viewing_duration_seconds: Number(dom.settingsViewing.value),
    drawing_duration_seconds:
      dom.settingsDrawing.value === ""
        ? null
        : Number(dom.settingsDrawing.value),
  };

  try {
    const state = await api.updateSettings(
      session.roomCode,
      session.token,
      payload,
    );
    renderLobby(state);
    showToast("Lobby settings updated.", "success");
  } catch (error) {
    handleError(error);
    renderLobby(roomState);
  }
}

async function handleUpload(event) {
  event.preventDefault();
  if (!session) return;

  const files = Array.from(dom.imageInput.files || []);
  if (!files.length) {
    showToast("Choose at least one image first.");
    return;
  }

  for (const file of files) {
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      showToast(`${file.name} is not a JPG, PNG, or WEBP image.`);
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      showToast(`${file.name} is larger than 5 MB.`);
      return;
    }
  }

  dom.uploadBtn.disabled = true;
  dom.uploadBtn.textContent = "Uploading…";

  try {
    let index = 0;
    for (const file of files) {
      index += 1;
      dom.uploadProgress.textContent = `Uploading ${index} of ${files.length}…`;
      const result = await api.uploadImage(
        session.roomCode,
        session.token,
        file,
      );
      renderLobby(result.room);
    }
    dom.uploadProgress.textContent = "Upload complete.";
    dom.imageInput.value = "";
    showToast("Reference images uploaded.", "success");
  } catch (error) {
    if (error instanceof ApiError && [401, 410].includes(error.status)) {
      endSession("Your room session has expired.");
      return;
    }
    handleError(error);
    await refreshRoomState();
  } finally {
    dom.uploadBtn.disabled = false;
    dom.uploadBtn.textContent = "Upload selected";
    window.setTimeout(() => {
      if (dom.uploadProgress.textContent === "Upload complete.") {
        dom.uploadProgress.textContent = "";
      }
    }, 2500);
  }
}

async function deleteImage(imageId) {
  if (!session) return;
  if (!window.confirm("Delete this reference image?")) return;

  try {
    const state = await api.deleteImage(
      session.roomCode,
      session.token,
      imageId,
    );
    renderLobby(state);
    showToast("Image deleted.", "success");
  } catch (error) {
    if (error instanceof ApiError && [401, 410].includes(error.status)) {
      endSession("Your room session has expired.");
      return;
    }
    handleError(error);
  }
}

async function copyRoomCode() {
  if (!roomState) return;
  try {
    await navigator.clipboard.writeText(roomState.code);
    showToast("Room code copied.", "success");
  } catch {
    dom.joinCode.value = roomState.code;
    showToast("Could not copy automatically. The code is in the join field.");
  }
}

function connectSocket() {
  if (!session) return;
  clearTimeout(reconnectTimer);
  stopHeartbeat();

  if (socket) {
    socket.onclose = null;
    socket.close();
    socket = null;
  }

  setConnection("connecting");

  let ws;
  try {
    ws = new WebSocket(api.socketUrl(session.roomCode, session.token));
  } catch {
    scheduleReconnect();
    return;
  }
  socket = ws;

  ws.onopen = () => {
    if (socket !== ws) return;
    reconnectAttempts = 0;
    setConnection("live");
    startHeartbeat();
  };

  ws.onmessage = (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch {
      return;
    }
    if (message.type === "lobby_state") {
      renderLobby(message.state);
    } else if (message.type === "error") {
      showToast(message.message || "Lobby error.");
    }
  };

  ws.onerror = () => {
    if (socket === ws) setConnection("reconnecting");
  };

  ws.onclose = (event) => {
    if (socket !== ws) return;
    socket = null;
    stopHeartbeat();

    if (!session) return;
    if (EXPIRED_SOCKET_CODES.has(event.code)) {
      endSession("Your room session has expired. Please join again.");
      return;
    }

    setConnection("reconnecting");
    scheduleReconnect();
  };
}

function scheduleReconnect() {
  if (!session) return;
  clearTimeout(reconnectTimer);

  const delay = Math.min(
    1000 * 2 ** Math.min(reconnectAttempts, 4),
    10000,
  );
  reconnectAttempts += 1;

  reconnectTimer = window.setTimeout(async () => {
    if (!session) return;
    try {
      const state = await api.getRoom(session.roomCode, session.token);
      renderLobby(state);
    } catch (error) {
      if (error instanceof ApiError && [401, 404, 410].includes(error.status)) {
        endSession("Your room session has expired. Please join again.");
        return;
      }
    }
    connectSocket();
  }, delay);
}

async function refreshRoomState() {
  if (!session) return;
  try {
    const state = await api.getRoom(session.roomCode, session.token);
    renderLobby(state);
  } catch (error) {
    if (error instanceof ApiError && [401, 404, 410].includes(error.status)) {
      endSession("Your room session has expired. Please join again.");
    }
  }
}

function startHeartbeat() {
  stopHeartbeat();
  heartbeatTimer = window.setInterval(() => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send("ping");
    }
  }, 25000);
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    window.clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
}

function leaveRoom(message, type = "error") {
  clearTimeout(reconnectTimer);
  stopHeartbeat();

  if (socket) {
    socket.onclose = null;
    socket.close(1000, "Leaving room");
    socket = null;
  }

  session = null;
  roomState = null;
  imagesSignature = "";
  imagesRequestId += 1;
  revokeImageUrls();
  clearSession();

  dom.lobbyView.classList.add("hidden");
  dom.homeView.classList.remove("hidden");
  dom.playersList.replaceChildren();
  dom.imagesList.replaceChildren();
  dom.uploadProgress.textContent = "";
  dom.imageInput.value = "";
  dom.readyBtn.disabled = false;
  setConnection("offline");

  const url = new URL(window.location.href);
  url.searchParams.delete("room");
  window.history.replaceState({}, "", url);

  if (message) showToast(message, type);
}

function endSession(message) {
  leaveRoom();
  showToast(message);
}

function currentPlayer() {
  if (!session || !roomState) return null;
  return roomState.players.find((player) => player.id === session.playerId);
}

function setConnection(state) {
  const labels = {
    live: "Live",
    connecting: "Connecting",
    reconnecting: "Reconnecting",
    offline: "Offline",
  };
  dom.connectionStatus.className = `connection-badge connection-${state}`;
  dom.connectionLabel.textContent = labels[state] || state;
}

function setFormBusy(form, busy) {
  const submit = form.querySelector('button[type="submit"]');
  if (submit) {
    submit.disabled = busy;
    if (busy) submit.dataset.label = submit.textContent;
    submit.textContent = busy ? "Please wait…" : submit.dataset.label || submit.textContent;
  }
}

function showToast(message, type = "error") {
  window.clearTimeout(toastTimer);
  dom.toast.textContent = message;
  dom.toast.className = `toast visible ${type}`;
  toastTimer = window.setTimeout(() => {
    dom.toast.className = "toast";
  }, 4200);
}

function handleError(error) {
  if (error instanceof ApiError) {
    if ([401, 410].includes(error.status)) {
      endSession("Your room session has expired. Please join again.");
      return;
    }
    showToast(error.message);
    return;
  }
  showToast("Something went wrong. Please try again.");
}

function makeBadge(text, className) {
  const badge = document.createElement("span");
  badge.className = `badge ${className}`;
  badge.textContent = text;
  return badge;
}

function makeEmptyState(text) {
  const empty = document.createElement("li");
  empty.className = "empty-state";
  empty.textContent = text;
  return empty;
}

function initials(name) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  return name.trim().slice(0, 2).toUpperCase();
}

function formatDrawingDuration(seconds) {
  if (seconds == null) return "Unlimited drawing";
  if (seconds === 180) return "3 min draw";
  if (seconds === 300) return "5 min draw";
  return `${seconds}s draw`;
}

function formatFileSize(bytes) {
  if (!bytes && bytes !== 0) return "Unknown size";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function revokeImageUrls() {
  for (const url of imageObjectUrls) URL.revokeObjectURL(url);
  imageObjectUrls = [];
}

init();
