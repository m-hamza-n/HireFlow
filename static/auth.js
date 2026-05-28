// HireFlow API Wrapper & Auth Handling
const API_BASE = ""; // Relative path assuming frontend and backend are on same origin

function setTokens(access, refresh) {
    localStorage.setItem("hf_access", access);
    localStorage.setItem("hf_refresh", refresh);
}

function clearTokens() {
    localStorage.removeItem("hf_access");
    localStorage.removeItem("hf_refresh");
}

function getAccessToken() { return localStorage.getItem("hf_access"); }
function getRefreshToken() { return localStorage.getItem("hf_refresh"); }

async function apiFetch(endpoint, options = {}) {
    let token = getAccessToken();
    const headers = { ...options.headers };
    
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (!(options.body instanceof FormData) && options.body) {
        headers["Content-Type"] = "application/json";
        options.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    }

    let response = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });

    // Handle 401 Unauthorized -> Attempt token refresh
    if (response.status === 401 && getRefreshToken()) {
        const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: getRefreshToken() })
        });

        if (refreshRes.ok) {
            const data = await refreshRes.json();
            setTokens(data.access_token, getRefreshToken()); // Keep old refresh token
            
            // Retry original request
            headers["Authorization"] = `Bearer ${data.access_token}`;
            response = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
        } else {
            clearTokens();
            window.location.href = "/static/index.html";
        }
    }
    
    return response;
}

async function logout() {
    const refresh = getRefreshToken();
    if (refresh) {
        await apiFetch("/auth/logout", { method: "POST", body: { refresh_token: refresh } });
    }
    clearTokens();
    window.location.href = "/static/index.html";
}

function parseJwt(token) {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        return JSON.parse(window.atob(base64));
    } catch (e) { return null; }
}

function checkAuthAndRedirect() {
    const token = getAccessToken();
    if (!token) return false;
    const payload = parseJwt(token);
    if (!payload) return false;
    
    const isIndex = window.location.pathname.endsWith("index.html") || window.location.pathname === "/";
    if (isIndex) {
        if (payload.role === "candidate") window.location.href = "/static/candidate.html";
        if (payload.role === "recruiter") window.location.href = "/static/recruiter.html";
    }
    return payload;
}

// Global WebSocket setup
let ws;
function connectWebSocket() {
    const token = getAccessToken();
    if (!token) return;
    
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/notifications/ws?token=${token}`;
    ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        showToast(`[${data.type.toUpperCase()}] ${data.title}: ${data.body}`);
    };
    
    ws.onclose = () => setTimeout(connectWebSocket, 5000); // Reconnect logic
}

function showToast(message) {
    const container = document.getElementById("notifications") || createNotificationContainer();
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

function createNotificationContainer() {
    const div = document.createElement("div");
    div.id = "notifications";
    document.body.appendChild(div);
    return div;
}