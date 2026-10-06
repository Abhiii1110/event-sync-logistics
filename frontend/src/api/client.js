import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export const tokenStore = {
  get access() { return localStorage.getItem("access"); },
  get refresh() { return localStorage.getItem("refresh"); },
  set(access, refresh) {
    if (access) localStorage.setItem("access", access);
    if (refresh) localStorage.setItem("refresh", refresh);
  },
  clear() {
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
  },
};

const api = axios.create({ baseURL: `${API_URL}/api` });

// Attach the access token to every request
api.interceptors.request.use((config) => {
  const token = tokenStore.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On a 401, refresh the token once and retry the original request
let refreshing = null;

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const url = original?.url || "";
    const isAuthCall = url.includes("/auth/login/") || url.includes("/auth/refresh/");

    if (error.response?.status === 401 && !original._retried && !isAuthCall && tokenStore.refresh) {
      original._retried = true;
      try {
        refreshing =
          refreshing ||
          axios
            .post(`${API_URL}/api/auth/refresh/`, { refresh: tokenStore.refresh })
            .finally(() => { refreshing = null; });
        const { data } = await refreshing;
        tokenStore.set(data.access, data.refresh);
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch {
        tokenStore.clear();
        window.dispatchEvent(new Event("auth:logout"));
      }
    }
    return Promise.reject(error);
  }
);

// Turns a DRF error response into one readable string
export function errorMessage(err) {
  const data = err.response?.data;
  if (!data) return "Cannot reach the server. Is the backend running?";
  if (typeof data === "string") return "Something went wrong on the server.";
  if (data.detail) return data.detail;
  return Object.entries(data)
    .map(([field, msgs]) => `${field}: ${[].concat(msgs).join(" ")}`)
    .join(" | ");
}

export default api;