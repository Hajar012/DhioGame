const meta = document.querySelector('meta[name="dhiogame-api-base"]');
export const API_BASE = (meta?.content || window.location.origin).replace(/\/$/, "");
const WS_BASE = API_BASE.replace(/^http/, "ws");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function extractDetail(payload, fallback) {
  if (!payload) return fallback;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    return payload.detail
      .map((item) => item.msg || item.message || "Invalid value")
      .join(", ");
  }
  return fallback;
}

async function parseResponse(response) {
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return null;
}

async function request(path, options = {}) {
  const { method = "GET", token, body, isForm = false } = options;
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  let payload = body;
  if (body && !isForm) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError("Cannot reach the DhioGame server.", 0);
  }

  const data = await parseResponse(response);
  if (!response.ok) {
    throw new ApiError(
      extractDetail(data, `Request failed (${response.status})`),
      response.status,
    );
  }
  return data;
}

const roomPath = (code) => `/api/rooms/${encodeURIComponent(code.toUpperCase())}`;

export const api = {
  createRoom: (body) => request("/api/rooms", { method: "POST", body }),
  joinRoom: (body) => request("/api/rooms/join", { method: "POST", body }),
  getRoom: (code, token) => request(roomPath(code), { token }),
  setReady: (code, token, isReady) =>
    request(`${roomPath(code)}/ready`, {
      method: "POST",
      token,
      body: { is_ready: isReady },
    }),
  updateSettings: (code, token, settings) =>
    request(`${roomPath(code)}/settings`, {
      method: "PATCH",
      token,
      body: settings,
    }),
  listImages: (code, token) =>
    request(`${roomPath(code)}/images`, { token }),
  uploadImage: (code, token, file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`${roomPath(code)}/images`, {
      method: "POST",
      token,
      body: form,
      isForm: true,
    });
  },
  deleteImage: (code, token, imageId) =>
    request(`${roomPath(code)}/images/${encodeURIComponent(imageId)}`, {
      method: "DELETE",
      token,
    }),
  fetchImageBlob: async (code, token, imageId) => {
    let response;
    try {
      response = await fetch(
        `${API_BASE}${roomPath(code)}/images/${encodeURIComponent(imageId)}/content`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
    } catch {
      throw new ApiError("Cannot reach the DhioGame server.", 0);
    }
    if (!response.ok) {
      throw new ApiError("Could not load the image preview.", response.status);
    }
    return response.blob();
  },
  getGame: (code, token) =>
    request(`${roomPath(code)}/game`, { token }),
  startGame: (code, token) =>
    request(`${roomPath(code)}/game/start`, { method: "POST", token }),
  syncGame: (code, token) =>
    request(`${roomPath(code)}/game/sync`, { method: "POST", token }),
  finishDrawing: (code, token) =>
    request(`${roomPath(code)}/game/finish-drawing`, {
      method: "POST",
      token,
    }),
  fetchReferenceBlob: async (code, token) => {
    let response;
    try {
      response = await fetch(`${API_BASE}${roomPath(code)}/game/reference`, {
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {
      throw new ApiError("Cannot reach the DhioGame server.", 0);
    }
    if (!response.ok) {
      throw new ApiError(
        "The reference image is not available.",
        response.status,
      );
    }
    return response.blob();
  },
  getDrawing: (code, token) =>
    request(`${roomPath(code)}/drawing`, { token }),
  saveDrawing: (code, token, data) =>
    request(`${roomPath(code)}/drawing`, {
      method: "PUT",
      token,
      body: { data },
    }),
  submitDrawing: (code, token) =>
    request(`${roomPath(code)}/drawing/submit`, {
      method: "POST",
      token,
    }),
  unsubmitDrawing: (code, token) =>
    request(`${roomPath(code)}/drawing/unsubmit`, {
      method: "POST",
      token,
    }),
  saveDrawingKeepalive: (code, token, data) => {
    try {
      fetch(`${API_BASE}${roomPath(code)}/drawing`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ data }),
        keepalive: true,
      });
    } catch {
      // Best-effort save on page exit.
    }
  },
  startReveal: (code, token) =>
    request(`${roomPath(code)}/reveal/start`, {
      method: "POST",
      token,
    }),
  getReveal: (code, token) =>
    request(`${roomPath(code)}/reveal`, { token }),
  revealOriginal: (code, token) =>
    request(`${roomPath(code)}/reveal/original`, {
      method: "POST",
      token,
    }),
  nextReveal: (code, token) =>
    request(`${roomPath(code)}/reveal/next`, {
      method: "POST",
      token,
    }),
  fetchRevealReferenceBlob: async (code, token) => {
    let response;
    try {
      response = await fetch(
        `${API_BASE}${roomPath(code)}/reveal/reference`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
    } catch {
      throw new ApiError("Cannot reach the DhioGame server.", 0);
    }
    if (!response.ok) {
      throw new ApiError(
        "The original image is not available.",
        response.status,
      );
    }
    return response.blob();
  },
  socketUrl: (code, token) =>
    `${WS_BASE}/api/ws/rooms/${encodeURIComponent(code.toUpperCase())}?token=${encodeURIComponent(token)}`,
};
