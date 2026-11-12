import { ApiError, api } from "./api.js";
import { clearSession, loadSession, saveSession } from "./session.js";

const $ = (id) => document.getElementById(id);

const dom = {
  stage: $("stage"),
  homeView: $("home-view"),
  createView: $("create-view"),
  joinView: $("join-view"),
  lobbyView: $("lobby-view"),
  gameView: $("game-view"),
  revealView: $("reveal-view"),
  headerRoomActions: $("header-room-actions"),
  brandLink: $("brand-link"),
  homeCreateBtn: $("home-create-btn"),
  homeJoinBtn: $("home-join-btn"),
  createBackBtn: $("create-back-btn"),
  joinBackBtn: $("join-back-btn"),
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
  settingsSummary: $("settings-summary"),
  settingsEdit: $("settings-edit"),
  hostStart: $("host-start"),
  startGameBtn: $("start-game-btn"),
  startHint: $("start-hint"),
  uploadForm: $("upload-form"),
  imageInput: $("image-input"),
  uploadBtn: $("upload-btn"),
  uploadProgress: $("upload-progress"),
  imagesList: $("images-list"),
  imagesSummary: $("images-summary"),
  gamePhaseEyebrow: $("game-phase-eyebrow"),
  gamePhaseTitle: $("game-phase-title"),
  gamePhaseCopy: $("game-phase-copy"),
  gameTimer: $("game-timer"),
  viewingPanel: $("viewing-panel"),
  drawingPanel: $("drawing-panel"),
  completedPanel: $("completed-panel"),
  referenceImage: $("reference-image"),
  referencePlaceholder: $("reference-placeholder"),
  drawingCanvas: $("drawing-canvas"),
  canvasLock: $("canvas-lock"),
  canvasLockTitle: $("canvas-lock-title"),
  canvasLockCopy: $("canvas-lock-copy"),
  brushColor: $("brush-color"),
  colorPalette: $("color-palette"),
  brushSize: $("brush-size"),
  brushSizeLabel: $("brush-size-label"),
  eraserBtn: $("eraser-btn"),
  undoBtn: $("undo-btn"),
  redoBtn: $("redo-btn"),
  clearBtn: $("clear-btn"),
  submitDrawingBtn: $("submit-drawing-btn"),
  saveStatus: $("save-status"),
  completedProgress: $("completed-progress"),
  startRevealBtn: $("start-reveal-btn"),
  hostGameControls: $("host-game-controls"),
  finishDrawingBtn: $("finish-drawing-btn"),
  gamePlayersList: $("game-players-list"),
  gameProgressSummary: $("game-progress-summary"),
  gamePlayerCount: $("game-player-count"),
  gameModeLabel: $("game-mode-label"),
  gameRoomCode: $("game-room-code"),
  revealRoomCode: $("reveal-room-code"),
  revealStageCard: $("reveal-stage-card"),
  revealTitle: $("reveal-title"),
  revealSubtitle: $("reveal-subtitle"),
  revealEyebrow: $("reveal-eyebrow"),
  revealPhaseBadge: $("reveal-phase-badge"),
  revealStage: $("reveal-stage"),
  revealCanvas: $("reveal-canvas"),
  revealEmpty: $("reveal-empty"),
  revealOriginalPanel: $("reveal-original-panel"),
  revealOriginalImage: $("reveal-original-image"),
  revealOriginalPlaceholder: $("reveal-original-placeholder"),
  revealOriginalName: $("reveal-original-name"),
  revealPlayerName: $("reveal-player-name"),
  revealPlayersList: $("reveal-players-list"),
  revealPlayersCard: $("reveal-players-card"),
  revealStatus: $("reveal-status"),
  revealOriginalBtn: $("reveal-original-btn"),
  nextRevealBtn: $("next-reveal-btn"),
  revealComplete: $("reveal-complete"),
  toast: $("toast"),
};

const MODE_LABELS = {
  same_image: "Same image",
  random_assignment: "Random assignment",
};
const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const EXPIRED_SOCKET_CODES = new Set([4401, 4404, 4410]);
const DRAWING_SAVE_DELAY = 900;
const CANVAS_WIDTH = 1600;
const CANVAS_HEIGHT = 1000;
const MAX_CANVAS_PIXEL_RATIO = 3;
const REVEAL_PHASES = new Set([
  "reveal_drawing",
  "reveal_original",
  "results_completed",
]);

let session = null;
let roomState = null;
let gameState = null;
let drawingState = null;
let revealState = null;

let socket = null;
let heartbeatTimer = null;
let reconnectTimer = null;
let reconnectAttempts = 0;
let toastTimer = null;

let imagesSignature = "";
let imagesRequestId = 0;
let imageObjectUrls = [];

let clockOffsetMs = 0;
let syncInFlight = false;
let lastSyncAttempt = 0;
let referenceObjectUrl = null;
let referenceRequestId = 0;
let revealOriginalObjectUrl = null;
let revealOriginalRequestId = 0;

let canvas = null;
let context = null;
let strokes = [];
let undoStack = [];
let redoStack = [];
let currentStroke = null;
let strokeStartSnapshot = null;
let drawingPointerId = null;
let drawingRevision = 0;
let canvasObserver = null;
let eraserActive = false;
let saveTimer = null;
let saveRetryTimer = null;
let activeSave = null;
let lastSavedPayload = "";
let currentView = "home";

function init() {
  bindEvents();
  setupCanvas();
  const hasJoinCode = prefillJoinCodeFromUrl();
  window.setInterval(updateCountdown, 250);

  const saved = loadSession();
  if (saved) {
    session = saved;
    restoreSession();
  } else {
    showAuthScreen(hasJoinCode ? "join" : "home");
  }
}

function bindEvents() {
  dom.homeCreateBtn.addEventListener("click", () => showAuthScreen("create"));
  dom.homeJoinBtn.addEventListener("click", () => showAuthScreen("join"));
  dom.createBackBtn.addEventListener("click", () => showAuthScreen("home"));
  dom.joinBackBtn.addEventListener("click", () => showAuthScreen("home"));
  dom.brandLink.addEventListener("click", (event) => {
    event.preventDefault();
    if (session) {
      showToast("Leave the room to return home.");
    } else {
      showAuthScreen("home");
    }
  });

  document.querySelectorAll("[data-create-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      dom.createMode.value = button.dataset.createMode;
      document.querySelectorAll("[data-create-mode]").forEach((choice) => {
        choice.classList.toggle("selected", choice === button);
      });
    });
  });

  dom.createForm.addEventListener("submit", handleCreateRoom);
  dom.joinForm.addEventListener("submit", handleJoinRoom);
  dom.readyBtn.addEventListener("click", toggleReady);
  dom.copyCodeBtn.addEventListener("click", copyRoomCode);
  dom.leaveBtn.addEventListener("click", () => leaveRoom());
  dom.settingsMode.addEventListener("change", handleSettingsChange);
  dom.settingsViewing.addEventListener("change", handleSettingsChange);
  dom.settingsDrawing.addEventListener("change", handleSettingsChange);
  dom.uploadForm.addEventListener("submit", handleUpload);
  dom.startGameBtn.addEventListener("click", handleStartGame);
  dom.finishDrawingBtn.addEventListener("click", handleFinishDrawing);
  dom.startRevealBtn.addEventListener("click", handleStartReveal);
  dom.revealOriginalBtn.addEventListener("click", handleRevealOriginal);
  dom.nextRevealBtn.addEventListener("click", handleNextReveal);
  dom.submitDrawingBtn.addEventListener("click", handleSubmitOrReopen);
  dom.undoBtn.addEventListener("click", undoStroke);
  dom.redoBtn.addEventListener("click", redoStroke);
  dom.clearBtn.addEventListener("click", clearCanvas);
  dom.eraserBtn.addEventListener("click", toggleEraser);
  dom.brushColor.addEventListener("input", () => {
    eraserActive = false;
    updateColorPalette();
    updateDrawingControls();
  });
  dom.colorPalette.addEventListener("click", (event) => {
    const swatch = event.target.closest("[data-color]");
    if (!swatch) return;
    dom.brushColor.value = swatch.dataset.color;
    eraserActive = false;
    updateColorPalette();
    updateDrawingControls();
  });
  dom.brushSize.addEventListener("input", () => {
    dom.brushSizeLabel.textContent = dom.brushSize.value;
  });

  dom.imagesList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-delete-image]");
    if (!button) return;
    deleteImage(button.dataset.deleteImage);
  });

  window.addEventListener("beforeunload", () => {
    flushDrawingOnExit();
    if (socket) {
      socket.onclose = null;
      socket.close();
    }
  });
  window.addEventListener("pagehide", flushDrawingOnExit);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flushDrawingOnExit();
  });
}

function prefillJoinCodeFromUrl() {
  const code = new URLSearchParams(window.location.search).get("room");
  if (code) {
    dom.joinCode.value = code.toUpperCase();
    return true;
  }
  return false;
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
  enterRoom(result.room);
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
    enterRoom(state);
    showToast("Session restored.", "success");
  } catch (error) {
    if (error instanceof ApiError && [401, 404, 410].includes(error.status)) {
      clearSession();
      session = null;
      setConnection("offline");
      showAuthScreen("home");
      showToast("Your previous room session has expired.");
      return;
    }
    handleError(error);
  }
}

function enterRoom(state) {
  roomState = state;
  const url = new URL(window.location.href);
  url.searchParams.set("room", state.code);
  window.history.replaceState({}, "", url);

  dom.roomCode.textContent = state.code;
  dom.gameRoomCode.textContent = state.code;
  dom.revealRoomCode.textContent = state.code;
  showRoomView("lobby");
  renderLobby(state);
  connectSocket();
  if (state.status !== "waiting") {
    refreshGameState();
  }
}

function showAuthScreen(name) {
  currentView = name;
  dom.homeView.classList.toggle("hidden", name !== "home");
  dom.createView.classList.toggle("hidden", name !== "create");
  dom.joinView.classList.toggle("hidden", name !== "join");
  dom.lobbyView.classList.add("hidden");
  dom.gameView.classList.add("hidden");
  dom.revealView.classList.add("hidden");
  dom.headerRoomActions.classList.add("hidden");
  dom.stage.classList.remove("playing");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showRoomView(view) {
  const viewChanged = currentView !== view;
  currentView = view;
  dom.homeView.classList.add("hidden");
  dom.createView.classList.add("hidden");
  dom.joinView.classList.add("hidden");
  dom.lobbyView.classList.toggle("hidden", view !== "lobby");
  dom.gameView.classList.toggle("hidden", view !== "game");
  dom.revealView.classList.toggle("hidden", view !== "reveal");
  dom.headerRoomActions.classList.toggle("hidden", false);
  dom.stage.classList.toggle(
    "playing",
    view === "game" || view === "reveal",
  );
  if (viewChanged) {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
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
    `${state.player_count} / ${state.max_players}` +
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
  renderHostStart(state, me.is_host);
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

  dom.settingsEdit.classList.toggle("hidden", !isHost);
  dom.settingsSummary.textContent =
    `${MODE_LABELS[settings.mode]} · ` +
    `${settings.viewing_duration_seconds}s view · ` +
    formatDrawingDuration(settings.drawing_duration_seconds);
}

function renderHostStart(state, isHost) {
  dom.hostStart.classList.toggle("hidden", !isHost);
  if (!isHost) return;

  dom.startGameBtn.disabled = !state.can_start;
  if (state.player_count < state.min_players) {
    const missing = state.min_players - state.player_count;
    dom.startHint.textContent = `Need ${missing} more player${missing === 1 ? "" : "s"} before starting.`;
  } else if (!state.uploads_complete) {
    dom.startHint.textContent =
      state.settings.mode === "same_image"
        ? "Upload exactly one reference image."
        : "Upload one reference image per player.";
  } else {
    dom.startHint.textContent = "Everyone is in. Start when you are ready.";
  }
}

function renderImages(state, isHost) {
  dom.imagesSummary.textContent =
    `${state.uploaded_images} / ${state.required_images} uploaded`;

  dom.uploadForm.classList.toggle(
    "hidden",
    !isHost || state.uploads_complete,
  );

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

    if (requestId !== imagesRequestId || currentSession !== session) {
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

async function handleStartGame() {
  if (!session || !roomState) return;
  dom.startGameBtn.disabled = true;

  try {
    const state = await api.startGame(session.roomCode, session.token);
    handleGameState(state);
    showToast("Game started. Memorize the reference!", "success");
  } catch (error) {
    handleError(error);
  } finally {
    renderHostStart(roomState, currentPlayer()?.is_host);
  }
}

async function handleFinishDrawing() {
  if (!session || !gameState) return;
  if (!window.confirm("End drawing for everyone now?")) return;

  dom.finishDrawingBtn.disabled = true;
  try {
    const state = await api.finishDrawing(
      session.roomCode,
      session.token,
    );
    handleGameState(state);
    showToast("Drawing locked.", "success");
  } catch (error) {
    handleError(error);
  } finally {
    dom.finishDrawingBtn.disabled = false;
  }
}

async function handleStartReveal() {
  if (!session || !gameState) return;
  dom.startRevealBtn.disabled = true;
  try {
    const state = await api.startReveal(session.roomCode, session.token);
    handleRevealState(state);
    showToast("Reveal started.", "success");
  } catch (error) {
    handleError(error);
  } finally {
    dom.startRevealBtn.disabled = false;
  }
}

async function handleRevealOriginal() {
  if (!session || !revealState) return;
  dom.revealOriginalBtn.disabled = true;
  try {
    const state = await api.revealOriginal(
      session.roomCode,
      session.token,
    );
    handleRevealState(state);
  } catch (error) {
    handleError(error);
  } finally {
    dom.revealOriginalBtn.disabled = false;
  }
}

async function handleNextReveal() {
  if (!session || !revealState) return;
  dom.nextRevealBtn.disabled = true;
  try {
    const state = await api.nextReveal(session.roomCode, session.token);
    handleRevealState(state);
    if (state.phase === "results_completed") {
      showToast("Reveal complete.", "success");
    }
  } catch (error) {
    handleError(error);
  } finally {
    dom.nextRevealBtn.disabled = false;
  }
}

async function refreshRevealState() {
  if (!session) return;
  const currentSession = session;
  try {
    const state = await api.getReveal(
      currentSession.roomCode,
      currentSession.token,
    );
    if (currentSession !== session) return;
    handleRevealState(state);
  } catch (error) {
    if (error instanceof ApiError && [401, 410].includes(error.status)) {
      endSession("Your room session has expired. Please join again.");
    }
  }
}

function handleRevealState(state) {
  if (!state) return;
  const previous = revealState;
  revealState = state;
  showRoomView("reveal");
  renderRevealState();

  const indexChanged =
    previous && previous.current_index !== state.current_index;
  if (
    state.phase === "reveal_original" &&
    (previous?.phase !== "reveal_original" ||
      indexChanged ||
      !revealOriginalObjectUrl)
  ) {
    loadRevealOriginalImage();
  } else if (state.phase !== "reveal_original") {
    clearRevealOriginalImage();
  }
}

function renderRevealState() {
  if (!revealState) return;
  const phase = revealState.phase;
  const complete = phase === "results_completed";
  dom.revealStageCard.classList.toggle("hidden", complete);
  dom.revealPlayersCard.classList.toggle("hidden", complete);
  dom.revealComplete.classList.toggle("hidden", !complete);
  dom.revealRoomCode.textContent = roomState?.code || "------";

  if (complete) {
    dom.revealEyebrow.textContent = "Reveal complete";
    dom.revealPhaseBadge.textContent = "COMPLETE";
    dom.revealOriginalBtn.classList.add("hidden");
    dom.nextRevealBtn.classList.add("hidden");
    dom.revealStatus.textContent =
      "All drawings and originals have been revealed.";
    return;
  }

  const player = revealState.current_player;
  const total = revealState.total_players;
  const currentNumber = Math.min(revealState.current_index + 1, total);

  dom.revealTitle.textContent = player
    ? `${player.nickname}'s masterpiece`
    : "The big reveal";
  dom.revealSubtitle.textContent = `Drawing ${currentNumber} of ${total}`;
  dom.revealEyebrow.textContent =
    phase === "reveal_original" ? "Original revealed" : "THE BIG REVEAL";
  dom.revealPhaseBadge.textContent = `${currentNumber} OF ${total}`;
  dom.revealOriginalPanel.classList.remove("hidden");
  dom.revealOriginalName.textContent = "The original";
  dom.revealPlayerName.textContent = player
    ? `${player.nickname}'s drawing`
    : "The drawing";

  renderRevealCanvas(player?.drawing_data);
  renderRevealPlayers();

  const isHost = Boolean(currentPlayer()?.is_host);
  dom.revealOriginalBtn.classList.toggle(
    "hidden",
    !(isHost && phase === "reveal_drawing"),
  );
  dom.nextRevealBtn.classList.toggle(
    "hidden",
    !(isHost && phase === "reveal_original"),
  );

  if (phase === "reveal_drawing") {
    dom.revealStatus.textContent = isHost
      ? "Show the original when everyone is ready."
      : "The host is in charge. Everyone else gets the popcorn 🍿";
  } else if (phase === "reveal_original") {
    dom.revealStatus.textContent = isHost
      ? "Advance when everyone has seen the original."
      : "Waiting for the host to continue.";
  }
}

function renderRevealPlayers() {
  dom.revealPlayersList.replaceChildren();
  if (!roomState?.players) return;

  const currentId = revealState?.current_player?.player_id;
  for (const player of roomState.players) {
    const item = document.createElement("li");
    item.className = "reveal-player";
    if (player.id === currentId) item.classList.add("current");
    item.textContent = `${player.nickname}${player.is_host ? " ♛" : ""}`;
    dom.revealPlayersList.append(item);
  }
}

function renderRevealCanvas(data) {
  const target = dom.revealCanvas;
  const targetContext = target.getContext("2d");
  targetContext.clearRect(0, 0, target.width, target.height);

  const revealStrokes = data?.strokes || [];
  dom.revealEmpty.classList.toggle("hidden", revealStrokes.length > 0);
  if (!revealStrokes.length) return;

  const scaleX = target.width / (data.width || target.width);
  const scaleY = target.height / (data.height || target.height);
  targetContext.save();
  targetContext.scale(scaleX, scaleY);

  for (const stroke of revealStrokes) {
    targetContext.save();
    targetContext.globalCompositeOperation = stroke.erase
      ? "destination-out"
      : "source-over";
    targetContext.strokeStyle = stroke.color;
    targetContext.fillStyle = stroke.color;
    targetContext.lineWidth = stroke.size;
    targetContext.lineCap = "round";
    targetContext.lineJoin = "round";

    if (stroke.points.length === 1) {
      targetContext.beginPath();
      targetContext.arc(
        stroke.points[0].x,
        stroke.points[0].y,
        stroke.size / 2,
        0,
        Math.PI * 2,
      );
      targetContext.fill();
    } else {
      targetContext.beginPath();
      targetContext.moveTo(stroke.points[0].x, stroke.points[0].y);
      for (let index = 1; index < stroke.points.length; index += 1) {
        targetContext.lineTo(
          stroke.points[index].x,
          stroke.points[index].y,
        );
      }
      targetContext.stroke();
    }
    targetContext.restore();
  }

  targetContext.restore();
}

async function loadRevealOriginalImage() {
  if (
    !session ||
    !revealState ||
    revealState.phase !== "reveal_original"
  ) {
    return;
  }

  const currentSession = session;
  const requestId = ++revealOriginalRequestId;
  revokeRevealOriginalUrl();
  dom.revealOriginalImage.classList.add("hidden");
  dom.revealOriginalPlaceholder.classList.remove("hidden");
  dom.revealOriginalPlaceholder.textContent = "🔒 Loading the original…";

  try {
    const blob = await api.fetchRevealReferenceBlob(
      currentSession.roomCode,
      currentSession.token,
    );
    if (
      requestId !== revealOriginalRequestId ||
      currentSession !== session
    ) {
      return;
    }
    revealOriginalObjectUrl = URL.createObjectURL(blob);
    dom.revealOriginalImage.src = revealOriginalObjectUrl;
    dom.revealOriginalImage.classList.remove("hidden");
    dom.revealOriginalPlaceholder.classList.add("hidden");
  } catch (error) {
    if (error instanceof ApiError && [401, 410].includes(error.status)) {
      endSession("Your room session has expired. Please join again.");
      return;
    }
    dom.revealOriginalPlaceholder.classList.remove("hidden");
    dom.revealOriginalPlaceholder.textContent = "Original unavailable.";
  }
}

function clearRevealOriginalImage() {
  revealOriginalRequestId += 1;
  revokeRevealOriginalUrl();
  dom.revealOriginalImage.classList.add("hidden");
  dom.revealOriginalPlaceholder.classList.remove("hidden");
  dom.revealOriginalPlaceholder.textContent =
    "🔒 Original is still a mystery!";
}

function revokeRevealOriginalUrl() {
  if (revealOriginalObjectUrl) {
    URL.revokeObjectURL(revealOriginalObjectUrl);
    revealOriginalObjectUrl = null;
  }
  dom.revealOriginalImage.removeAttribute("src");
}

function resetRevealState() {
  revealState = null;
  clearRevealOriginalImage();
  dom.revealStageCard.classList.remove("hidden");
  dom.revealPlayersCard.classList.remove("hidden");
  dom.revealComplete.classList.add("hidden");
  dom.revealOriginalPanel.classList.remove("hidden");
  dom.revealOriginalBtn.classList.add("hidden");
  dom.nextRevealBtn.classList.add("hidden");
  dom.revealOriginalBtn.disabled = false;
  dom.nextRevealBtn.disabled = false;
  dom.revealTitle.textContent = "The big reveal";
  dom.revealSubtitle.textContent = "Waiting for the reveal to begin…";
  dom.revealPhaseBadge.textContent = "REVEAL";
  dom.revealPlayerName.textContent = "The drawing";
  dom.revealOriginalName.textContent = "The original";
  dom.revealPlayersList.replaceChildren();
  dom.revealEmpty.classList.add("hidden");
  const revealContext = dom.revealCanvas.getContext("2d");
  revealContext.clearRect(
    0,
    0,
    dom.revealCanvas.width,
    dom.revealCanvas.height,
  );
}

function handleGameState(state) {
  if (!state) return;
  const previousPhase = gameState?.phase ?? null;
  gameState = state;
  clockOffsetMs = Date.parse(state.server_time) - Date.now();
  dom.roomCode.textContent = state.room_code;
  dom.gameRoomCode.textContent = state.room_code;
  dom.revealRoomCode.textContent = state.room_code;

  if (REVEAL_PHASES.has(state.phase)) {
    refreshRevealState();
    return;
  }

  showRoomView("game");
  renderGameState();

  if (state.phase === "image_viewing") {
    if (previousPhase !== "image_viewing" || !referenceObjectUrl) {
      loadReferenceImage();
    }
  } else {
    clearReferenceImage();
  }

  if (state.phase === "drawing") {
    if (
      previousPhase !== "drawing" ||
      !drawingState ||
      drawingState.game_id !== state.id
    ) {
      prepareDrawingSession(state);
      loadDrawingState();
    } else {
      updateDrawingControls();
    }
  } else if (state.phase === "drawing_completed") {
    window.clearTimeout(saveTimer);
    if (
      previousPhase !== "drawing_completed" ||
      !drawingState ||
      drawingState.status !== "locked"
    ) {
      loadDrawingState();
    }
    setSaveStatus("Drawing locked");
  } else {
    window.clearTimeout(saveTimer);
  }

  updateCountdown();
}

function renderGameState() {
  if (!gameState) return;
  const me = currentPlayer();
  const phase = gameState.phase;
  const configs = {
    image_viewing: {
      eyebrow: "VIEWING PHASE",
      title: "MEMORIZE THIS!",
      copy: "The reference disappears when the viewing countdown ends.",
    },
    drawing: {
      eyebrow: "DRAWING PHASE",
      title: "DRAW YOUR HEART OUT",
      copy: "Use the tools below. Your drawing saves automatically.",
    },
    drawing_completed: {
      eyebrow: "DRAWING COMPLETE",
      title: "PENCILS DOWN!",
      copy: "All drawings are locked. The host can start the big reveal.",
    },
  };
  const config = configs[phase] || {
    eyebrow: "Game",
    title: "Waiting for the round",
    copy: "The host is preparing the game.",
  };

  dom.gamePhaseEyebrow.textContent = config.eyebrow;
  dom.gamePhaseTitle.textContent = config.title;
  dom.gamePhaseCopy.textContent = config.copy;

  dom.viewingPanel.classList.toggle("hidden", phase !== "image_viewing");
  dom.drawingPanel.classList.toggle("hidden", phase !== "drawing");
  dom.completedPanel.classList.toggle(
    "hidden",
    phase !== "drawing_completed",
  );

  dom.hostGameControls.classList.toggle(
    "hidden",
    !(me?.is_host && phase === "drawing"),
  );
  dom.startRevealBtn.classList.toggle(
    "hidden",
    !(me?.is_host && phase === "drawing_completed"),
  );

  if (phase === "drawing_completed") {
    dom.completedProgress.textContent =
      `${gameState.submitted_count} of ${gameState.player_count} drawings locked.`;
  }

  dom.gameModeLabel.textContent =
    gameState.mode === "same_image"
      ? "Same image mode"
      : "Random assignment mode";

  renderGameProgress();
  updateDrawingControls();
  updateCountdown();
}

function renderGameProgress() {
  dom.gamePlayersList.replaceChildren();

  for (const player of gameState.players) {
    let label = "Not started";
    let stateClass = "";
    if (player.drawing_status === "submitted") {
      label = "Submitted";
      stateClass = "is-submitted";
    } else if (player.drawing_status === "locked") {
      label = "Locked";
      stateClass = "is-locked";
    } else if (player.has_drawing) {
      label = "Drawing";
      stateClass = "is-drawing";
    }

    const chip = document.createElement("span");
    chip.className = "progress-chip";
    if (player.player_id === session.playerId) {
      chip.classList.add("is-me");
    }
    if (stateClass) chip.classList.add(stateClass);
    chip.textContent = `${player.nickname} · ${label}`;
    dom.gamePlayersList.append(chip);
  }

  const summary =
    gameState.phase === "drawing_completed"
      ? `${gameState.submitted_count} of ${gameState.player_count} locked`
      : `${gameState.submitted_count} submitted`;
  dom.gameProgressSummary.textContent = summary;
  dom.gamePlayerCount.textContent = `${gameState.player_count} players`;
}

async function refreshGameState() {
  if (!session) return;
  const currentSession = session;
  try {
    const state = await api.getGame(
      currentSession.roomCode,
      currentSession.token,
    );
    if (currentSession !== session) return;
    handleGameState(state);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      gameState = null;
      drawingState = null;
      if (currentView === "game") showRoomView("lobby");
      return;
    }
    if (error instanceof ApiError && [401, 404, 410].includes(error.status)) {
      endSession("Your room session has expired. Please join again.");
    }
  }
}

async function refreshRoomState() {
  if (!session) return;
  const currentSession = session;
  try {
    const state = await api.getRoom(
      currentSession.roomCode,
      currentSession.token,
    );
    if (currentSession !== session) return;
    renderLobby(state);
  } catch (error) {
    if (error instanceof ApiError && [401, 404, 410].includes(error.status)) {
      endSession("Your room session has expired. Please join again.");
    }
  }
}

async function loadReferenceImage() {
  if (!session || !gameState || gameState.phase !== "image_viewing") return;
  const currentSession = session;
  const requestId = ++referenceRequestId;
  revokeReferenceUrl();
  dom.referenceImage.classList.add("hidden");
  dom.referencePlaceholder.classList.remove("hidden");
  dom.referencePlaceholder.textContent = "Loading your reference image…";

  try {
    const blob = await api.fetchReferenceBlob(
      currentSession.roomCode,
      currentSession.token,
    );
    if (requestId !== referenceRequestId || currentSession !== session) return;

    referenceObjectUrl = URL.createObjectURL(blob);
    dom.referenceImage.src = referenceObjectUrl;
    const decoded = await waitForImageReady(dom.referenceImage);
    if (requestId !== referenceRequestId || currentSession !== session) return;
    if (!decoded) {
      dom.referencePlaceholder.classList.remove("hidden");
      dom.referencePlaceholder.textContent = "Reference image unavailable.";
      return;
    }

    dom.referenceImage.classList.remove("hidden");
    dom.referencePlaceholder.classList.add("hidden");

    if (gameState?.phase === "image_viewing") {
      try {
        const state = await api.markReferenceLoaded(
          currentSession.roomCode,
          currentSession.token,
        );
        if (currentSession !== session) return;
        handleGameState(state);
      } catch (error) {
        if (error instanceof ApiError && [401, 410].includes(error.status)) {
          endSession("Your room session has expired.");
        }
      }
    }
  } catch (error) {
    if (error instanceof ApiError && [401, 410].includes(error.status)) {
      endSession("Your room session has expired.");
      return;
    }
    dom.referencePlaceholder.classList.remove("hidden");
    dom.referencePlaceholder.textContent = "Reference image unavailable.";
  }
}

async function waitForImageReady(image) {
  if (typeof image.decode === "function") {
    try {
      await image.decode();
      return image.naturalWidth > 0;
    } catch {
      // Fall back to the load event when decode() is unavailable or rejected.
    }
  }
  if (image.complete) return image.naturalWidth > 0;
  return new Promise((resolve) => {
    const finish = () => {
      image.removeEventListener("load", finish);
      image.removeEventListener("error", finish);
      resolve(image.naturalWidth > 0);
    };
    image.addEventListener("load", finish);
    image.addEventListener("error", finish);
  });
}

function clearReferenceImage() {
  referenceRequestId += 1;
  revokeReferenceUrl();
  dom.referenceImage.classList.add("hidden");
  dom.referencePlaceholder.classList.remove("hidden");
  dom.referencePlaceholder.textContent = "The reference is hidden for now.";
}

function revokeReferenceUrl() {
  if (referenceObjectUrl) {
    URL.revokeObjectURL(referenceObjectUrl);
    referenceObjectUrl = null;
  }
  dom.referenceImage.removeAttribute("src");
}

function prepareDrawingSession(state) {
  const me = state.players.find(
    (player) => player.player_id === session?.playerId,
  );
  const status = me?.drawing_status || "draft";
  const canEdit = status === "draft";

  drawingState = {
    id: null,
    game_id: state.id,
    status,
    data: null,
    submitted_at: null,
    updated_at: null,
    can_edit: canEdit,
    can_submit: canEdit,
    can_unsubmit: status === "submitted",
    phase: state.phase,
    phase_ends_at: state.phase_ends_at,
    server_time: state.server_time,
  };
  strokes = [];
  undoStack = [];
  redoStack = [];
  currentStroke = null;
  strokeStartSnapshot = null;
  drawingPointerId = null;
  drawingRevision = 0;
  lastSavedPayload = "";
  redrawCanvas();
  setSaveStatus("All changes saved");
  updateDrawingControls();
  syncCanvasSurface();
}

async function loadDrawingState() {
  if (!session || !gameState) return;
  const currentSession = session;
  const localRevision = drawingRevision;
  try {
    const state = await api.getDrawing(
      currentSession.roomCode,
      currentSession.token,
    );
    if (currentSession !== session) return;
    drawingState = state;
    applyDrawingData(state.data, { loaded: true, localRevision });
    if (gameState?.phase === "drawing_completed") {
      setSaveStatus("Drawing locked");
    }
    updateDrawingControls();
  } catch (error) {
    if (error instanceof ApiError && [401, 410].includes(error.status)) {
      endSession("Your room session has expired.");
    }
  }
}

function applyDrawingData(data, { loaded = false, localRevision = null } = {}) {
  const incoming = (data?.strokes || []).map((stroke) => ({
    color: stroke.color,
    size: stroke.size,
    erase: Boolean(stroke.erase),
    points: stroke.points.map((point) => ({ x: point.x, y: point.y })),
  }));
  const localEdits =
    localRevision !== null && drawingRevision !== localRevision;
  const baselinePayload = data ? JSON.stringify(data) : "";

  if (localEdits) {
    strokes = incoming.concat(strokes);
    undoStack = [];
    redoStack = [];
    if (currentStroke) {
      strokeStartSnapshot = strokes.slice();
    } else {
      drawingPointerId = null;
    }
    redrawCanvas();
    lastSavedPayload = baselinePayload;
    if (loaded) {
      setSaveStatus("Unsaved changes");
      if (gameState?.phase === "drawing" && canEditDrawing()) {
        scheduleSave();
      }
    }
    updateDrawingControls();
    return true;
  }

  strokes = incoming;
  undoStack = [];
  redoStack = [];
  currentStroke = null;
  strokeStartSnapshot = null;
  drawingPointerId = null;
  redrawCanvas();
  lastSavedPayload = data ? JSON.stringify(buildDrawingData()) : "";
  if (loaded) {
    setSaveStatus(data ? "Drawing loaded" : "All changes saved");
  }
  updateDrawingControls();
  return false;
}

function setupCanvas() {
  canvas = dom.drawingCanvas;
  context = canvas.getContext("2d");
  canvas.addEventListener("pointerdown", beginStroke);
  canvas.addEventListener("pointermove", moveStroke);
  canvas.addEventListener("pointerup", endStroke);
  canvas.addEventListener("pointercancel", endStroke);

  if (typeof ResizeObserver !== "undefined") {
    canvasObserver = new ResizeObserver(() => syncCanvasSurface());
    canvasObserver.observe(canvas);
  }
  window.addEventListener("resize", syncCanvasSurface);
  window.visualViewport?.addEventListener("resize", syncCanvasSurface);
  syncCanvasSurface();
}

function syncCanvasSurface() {
  if (!canvas || !context) return;
  const rect = canvas.getBoundingClientRect();
  if (rect.width < 1 || rect.height < 1) return;

  const ratio = Math.min(
    window.devicePixelRatio || 1,
    MAX_CANVAS_PIXEL_RATIO,
  );
  const targetWidth = Math.max(1, Math.round(rect.width * ratio));
  const targetHeight = Math.max(1, Math.round(rect.height * ratio));
  if (canvas.width === targetWidth && canvas.height === targetHeight) {
    return;
  }

  canvas.width = targetWidth;
  canvas.height = targetHeight;
  redrawCanvas();
}

function applyCanvasTransform() {
  if (!canvas || !context) return;
  context.setTransform(
    canvas.width / CANVAS_WIDTH,
    0,
    0,
    canvas.height / CANVAS_HEIGHT,
    0,
    0,
  );
}

function canvasPoint(event) {
  const rect = canvas.getBoundingClientRect();
  if (rect.width < 1 || rect.height < 1) return { x: 0, y: 0 };
  const scaleX = CANVAS_WIDTH / rect.width;
  const scaleY = CANVAS_HEIGHT / rect.height;
  return {
    x: clamp((event.clientX - rect.left) * scaleX, 0, CANVAS_WIDTH),
    y: clamp((event.clientY - rect.top) * scaleY, 0, CANVAS_HEIGHT),
  };
}

function beginStroke(event) {
  if (!canEditDrawing()) return;
  event.preventDefault();
  const point = canvasPoint(event);
  drawingPointerId = event.pointerId;
  drawingRevision += 1;
  try {
    canvas.setPointerCapture(event.pointerId);
  } catch {
    // Pointer capture is optional.
  }
  strokeStartSnapshot = strokes.slice();
  currentStroke = {
    color: dom.brushColor.value,
    size: Number(dom.brushSize.value),
    erase: eraserActive,
    points: [point],
  };
  drawStrokeDot(currentStroke, point);
  setSaveStatus("Unsaved changes");
}

function moveStroke(event) {
  if (!currentStroke || event.pointerId !== drawingPointerId) return;
  event.preventDefault();
  const point = canvasPoint(event);
  const previous = currentStroke.points[currentStroke.points.length - 1];
  if (Math.hypot(point.x - previous.x, point.y - previous.y) < 1) return;
  currentStroke.points.push(point);
  drawStrokeSegment(currentStroke, previous, point);
}

function endStroke(event) {
  if (!currentStroke || event.pointerId !== drawingPointerId) return;
  try {
    if (canvas.hasPointerCapture(event.pointerId)) {
      canvas.releasePointerCapture(event.pointerId);
    }
  } catch {
    // Ignore pointer capture release errors.
  }

  if (currentStroke.points.length > 0) {
    undoStack.push(strokeStartSnapshot || []);
    redoStack = [];
    strokes.push(currentStroke);
    drawingRevision += 1;
  }

  currentStroke = null;
  strokeStartSnapshot = null;
  drawingPointerId = null;
  updateDrawingControls();
  scheduleSave();
}

function drawStrokeDot(stroke, point) {
  context.save();
  context.globalCompositeOperation = stroke.erase
    ? "destination-out"
    : "source-over";
  context.fillStyle = stroke.color;
  context.beginPath();
  context.arc(point.x, point.y, stroke.size / 2, 0, Math.PI * 2);
  context.fill();
  context.restore();
}

function drawStrokeSegment(stroke, from, to) {
  context.save();
  context.globalCompositeOperation = stroke.erase
    ? "destination-out"
    : "source-over";
  context.strokeStyle = stroke.color;
  context.lineWidth = stroke.size;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.beginPath();
  context.moveTo(from.x, from.y);
  context.lineTo(to.x, to.y);
  context.stroke();
  context.restore();
}

function drawWholeStroke(stroke) {
  if (stroke.points.length === 1) {
    drawStrokeDot(stroke, stroke.points[0]);
    return;
  }

  context.save();
  context.globalCompositeOperation = stroke.erase
    ? "destination-out"
    : "source-over";
  context.strokeStyle = stroke.color;
  context.lineWidth = stroke.size;
  context.lineCap = "round";
  context.lineJoin = "round";
  context.beginPath();
  context.moveTo(stroke.points[0].x, stroke.points[0].y);
  for (let index = 1; index < stroke.points.length; index += 1) {
    context.lineTo(stroke.points[index].x, stroke.points[index].y);
  }
  context.stroke();
  context.restore();
}

function redrawCanvas() {
  if (!canvas || !context) return;
  applyCanvasTransform();
  context.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
  for (const stroke of strokes) {
    drawWholeStroke(stroke);
  }
  if (currentStroke) {
    drawWholeStroke(currentStroke);
  }
}

function undoStroke() {
  if (!canEditDrawing() || undoStack.length === 0) return;
  redoStack.push(strokes.slice());
  strokes = undoStack.pop();
  drawingRevision += 1;
  redrawCanvas();
  updateDrawingControls();
  scheduleSave();
}

function redoStroke() {
  if (!canEditDrawing() || redoStack.length === 0) return;
  undoStack.push(strokes.slice());
  strokes = redoStack.pop();
  drawingRevision += 1;
  redrawCanvas();
  updateDrawingControls();
  scheduleSave();
}

function clearCanvas() {
  if (!canEditDrawing() || strokes.length === 0) return;
  undoStack.push(strokes.slice());
  redoStack = [];
  strokes = [];
  drawingRevision += 1;
  redrawCanvas();
  updateDrawingControls();
  scheduleSave();
}

function toggleEraser() {
  if (!canEditDrawing()) return;
  eraserActive = !eraserActive;
  updateDrawingControls();
}

function canEditDrawing() {
  return Boolean(
    gameState?.phase === "drawing" &&
      drawingState?.can_edit &&
      !currentStroke,
  );
}

function buildDrawingData() {
  return {
    version: 1,
    width: CANVAS_WIDTH,
    height: CANVAS_HEIGHT,
    strokes: strokes.map((stroke) => ({
      color: stroke.color,
      size: roundCoord(stroke.size),
      erase: Boolean(stroke.erase),
      points: stroke.points.map((point) => ({
        x: roundCoord(point.x),
        y: roundCoord(point.y),
      })),
    })),
  };
}

function scheduleSave() {
  if (!canEditDrawing()) return;
  window.clearTimeout(saveTimer);
  setSaveStatus("Saving changes…");
  saveTimer = window.setTimeout(() => {
    saveDrawing();
  }, DRAWING_SAVE_DELAY);
}

async function saveDrawing(force = false) {
  if (!session || !canEditDrawing()) return false;
  if (activeSave) {
    await activeSave;
  }
  if (!session || !canEditDrawing()) return false;

  const data = buildDrawingData();
  const payload = JSON.stringify(data);
  if (!force && payload === lastSavedPayload) {
    setSaveStatus("All changes saved");
    return true;
  }

  const currentSession = session;
  let succeeded = false;
  activeSave = (async () => {
    try {
      const result = await api.saveDrawing(
        currentSession.roomCode,
        currentSession.token,
        data,
      );
      if (currentSession !== session) return;
      drawingState = {
        ...drawingState,
        ...mutationFields(result),
        data,
      };
      lastSavedPayload = payload;
      setSaveStatus("All changes saved");
      updateDrawingControls();
      succeeded = true;
    } catch (error) {
      if (error instanceof ApiError && [401, 410].includes(error.status)) {
        endSession("Your room session has expired.");
        return;
      }
      if (error instanceof ApiError && error.status === 409) {
        setSaveStatus("Drawing is locked", true);
        await refreshGameState();
        return;
      }
      setSaveStatus("Could not save. Retrying…", true);
      window.clearTimeout(saveRetryTimer);
      saveRetryTimer = window.setTimeout(() => {
        if (canEditDrawing()) scheduleSave();
      }, 1800);
    } finally {
      activeSave = null;
    }
  })();

  await activeSave;
  return succeeded;
}

async function handleSubmitOrReopen() {
  if (!session || !gameState || !drawingState) return;
  if (gameState.phase !== "drawing") return;

  dom.submitDrawingBtn.disabled = true;
  try {
    if (drawingState.status === "submitted") {
      const result = await api.unsubmitDrawing(
        session.roomCode,
        session.token,
      );
      drawingState = {
        ...drawingState,
        ...mutationFields(result),
      };
      setSaveStatus("Drawing reopened for editing");
      updateDrawingControls();
      showToast("You can edit your drawing again.", "success");
      return;
    }

    window.clearTimeout(saveTimer);
    const saved = await saveDrawing(true);
    if (!saved || !drawingState || drawingState.status !== "draft") {
      return;
    }

    const result = await api.submitDrawing(
      session.roomCode,
      session.token,
    );
    drawingState = {
      ...drawingState,
      ...mutationFields(result),
    };
    setSaveStatus("Drawing submitted");
    updateDrawingControls();
    showToast("Drawing submitted.", "success");
  } catch (error) {
    handleError(error);
  } finally {
    updateDrawingControls();
  }
}

function updateDrawingControls() {
  const canEdit = canEditDrawing();
  const phase = gameState?.phase;
  const status = drawingState?.status;

  dom.brushColor.disabled = !canEdit;
  dom.brushSize.disabled = !canEdit;
  dom.eraserBtn.disabled = !canEdit;
  dom.eraserBtn.classList.toggle("is-active", eraserActive);
  dom.undoBtn.disabled = !canEdit || undoStack.length === 0;
  dom.redoBtn.disabled = !canEdit || redoStack.length === 0;
  dom.clearBtn.disabled = !canEdit || strokes.length === 0;
  dom.brushSizeLabel.textContent = dom.brushSize.value;
  dom.colorPalette.querySelectorAll("[data-color]").forEach((swatch) => {
    swatch.disabled = !canEdit;
  });
  updateColorPalette();

  let submitLabel = "SUBMIT MY ART!";
  let submitDisabled = true;
  if (phase === "drawing") {
    if (status === "submitted") {
      submitLabel = "REOPEN MY ART";
      submitDisabled = false;
    } else if (status === "draft") {
      submitLabel = "SUBMIT MY ART!";
      submitDisabled = false;
    } else {
      submitLabel = "LOCKED";
    }
  } else if (phase === "drawing_completed") {
    submitLabel = "LOCKED";
  }
  dom.submitDrawingBtn.textContent = submitLabel;
  dom.submitDrawingBtn.disabled = submitDisabled;

  const showLock =
    phase === "drawing" && status && status !== "draft";
  dom.canvasLock.classList.toggle("hidden", !showLock);
  if (showLock) {
    if (status === "submitted") {
      dom.canvasLockTitle.textContent = "Drawing submitted";
      dom.canvasLockCopy.textContent =
        "Reopen your drawing to keep editing before time runs out.";
    } else {
      dom.canvasLockTitle.textContent = "Drawing locked";
      dom.canvasLockCopy.textContent =
        "The drawing deadline has passed. Your saved drawing is safe.";
    }
  }
  dom.drawingCanvas.classList.toggle("is-locked", !canEdit);
}

function updateColorPalette() {
  const value = dom.brushColor.value.toLowerCase();
  dom.colorPalette.querySelectorAll("[data-color]").forEach((swatch) => {
    swatch.classList.toggle(
      "selected",
      swatch.dataset.color.toLowerCase() === value,
    );
  });
}

function flushDrawingOnExit() {
  if (!session || !canEditDrawing()) return;
  const data = buildDrawingData();
  const payload = JSON.stringify(data);
  if (payload === lastSavedPayload) return;
  api.saveDrawingKeepalive(session.roomCode, session.token, data);
}

function updateCountdown() {
  if (!gameState) return;

  if (gameState.phase === "drawing_completed") {
    dom.gameTimer.textContent = "Locked";
    dom.gameTimer.classList.remove("urgent");
    return;
  }

  if (!gameState.phase_ends_at) {
    dom.gameTimer.textContent =
      gameState.phase === "drawing" ? "∞" : "--:--";
    dom.gameTimer.classList.remove("urgent");
    return;
  }

  const endTime = Date.parse(gameState.phase_ends_at);
  if (Number.isNaN(endTime)) return;

  const remaining = Math.max(0, endTime - (Date.now() + clockOffsetMs));
  dom.gameTimer.textContent = formatClock(remaining);
  dom.gameTimer.classList.toggle(
    "urgent",
    remaining > 0 && remaining <= 30_000,
  );

  if (
    remaining <= 0 &&
    ["image_viewing", "drawing"].includes(gameState.phase) &&
    !syncInFlight &&
    Date.now() - lastSyncAttempt >= 1000
  ) {
    lastSyncAttempt = Date.now();
    syncGameState();
  }
}

async function syncGameState() {
  if (!session || syncInFlight) return;
  const currentSession = session;
  syncInFlight = true;
  try {
    const state = await api.syncGame(
      currentSession.roomCode,
      currentSession.token,
    );
    if (currentSession !== session) return;
    handleGameState(state);
  } catch (error) {
    if (error instanceof ApiError && [401, 410].includes(error.status)) {
      endSession("Your room session has expired. Please join again.");
    }
  } finally {
    syncInFlight = false;
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
    } else if (message.type === "game_state") {
      handleGameState(message.state);
    } else if (message.type === "reveal_state") {
      handleRevealState(message.state);
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
    const currentSession = session;
    try {
      const state = await api.getRoom(
        currentSession.roomCode,
        currentSession.token,
      );
      if (currentSession !== session) return;
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
  window.clearTimeout(saveTimer);
  window.clearTimeout(saveRetryTimer);
  stopHeartbeat();
  clearReferenceImage();

  if (socket) {
    socket.onclose = null;
    socket.close(1000, "Leaving room");
    socket = null;
  }

  session = null;
  roomState = null;
  gameState = null;
  drawingState = null;
  activeSave = null;
  resetRevealState();
  dom.startRevealBtn.classList.add("hidden");
  dom.startRevealBtn.disabled = false;
  imagesSignature = "";
  imagesRequestId += 1;
  revokeImageUrls();
  clearSession();
  resetDrawingCanvas();
  setSaveStatus("All changes saved");
  showAuthScreen("home");
  dom.roomCode.textContent = "------";
  dom.gameRoomCode.textContent = "------";
  dom.revealRoomCode.textContent = "------";
  dom.playersList.replaceChildren();
  dom.imagesList.replaceChildren();
  dom.gamePlayersList.replaceChildren();
  dom.completedProgress.textContent = "";
  dom.uploadProgress.textContent = "";
  dom.imageInput.value = "";
  dom.readyBtn.disabled = false;
  dom.startGameBtn.disabled = true;
  dom.finishDrawingBtn.disabled = false;
  setConnection("offline");

  const url = new URL(window.location.href);
  url.searchParams.delete("room");
  window.history.replaceState({}, "", url);

  if (message) showToast(message, type);
}

function resetDrawingCanvas() {
  strokes = [];
  undoStack = [];
  redoStack = [];
  currentStroke = null;
  strokeStartSnapshot = null;
  drawingPointerId = null;
  drawingRevision += 1;
  eraserActive = false;
  lastSavedPayload = "";
  if (context && canvas) redrawCanvas();
  updateDrawingControls();
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
  dom.connectionStatus.className = `pill connection-badge connection-${state}`;
  dom.connectionLabel.textContent = labels[state] || state;
}

function setFormBusy(form, busy) {
  const submit = form.querySelector('button[type="submit"]');
  if (submit) {
    submit.disabled = busy;
    if (busy) submit.dataset.label = submit.textContent;
    submit.textContent = busy
      ? "Please wait…"
      : submit.dataset.label || submit.textContent;
  }
}

function setSaveStatus(text, isError = false) {
  dom.saveStatus.textContent = text;
  dom.saveStatus.classList.toggle("error", isError);
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

function mutationFields(result) {
  return {
    status: result.status,
    submitted_at: result.submitted_at,
    updated_at: result.updated_at,
    can_edit: result.can_edit,
    can_submit: result.can_submit,
    can_unsubmit: result.can_unsubmit,
    phase: result.phase,
    phase_ends_at: result.phase_ends_at,
    server_time: result.server_time,
  };
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

function formatClock(milliseconds) {
  const totalSeconds = Math.ceil(milliseconds / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function roundCoord(value) {
  return Math.round(value * 10) / 10;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function revokeImageUrls() {
  for (const url of imageObjectUrls) URL.revokeObjectURL(url);
  imageObjectUrls = [];
}

init();
