import type {
  Alert,
  AppSettings,
  CheckRun,
  Monitor,
  PreviewLoad,
  PreviewSelection,
  PushoverProfile
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    }
  });

  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      message = await response.text();
    }
    throw new Error(message || `Request failed with ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  appSettings: () => request<AppSettings>("/api/app-settings"),
  updateAppSettings: (payload: Record<string, unknown>) =>
    request<AppSettings>("/api/app-settings", { method: "PATCH", body: JSON.stringify(payload) }),
  monitors: () => request<Monitor[]>("/api/monitors"),
  monitor: (id: number) => request<Monitor>(`/api/monitors/${id}`),
  createMonitor: (payload: Record<string, unknown>) =>
    request<Monitor>("/api/monitors", { method: "POST", body: JSON.stringify(payload) }),
  updateMonitor: (id: number, payload: Record<string, unknown>) =>
    request<Monitor>(`/api/monitors/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteMonitor: (id: number) => request<void>(`/api/monitors/${id}`, { method: "DELETE" }),
  checkNow: (id: number) => request<CheckRun>(`/api/monitors/${id}/check-now`, { method: "POST" }),
  pause: (id: number) => request<Monitor>(`/api/monitors/${id}/pause`, { method: "POST" }),
  resume: (id: number) => request<Monitor>(`/api/monitors/${id}/resume`, { method: "POST" }),
  rebaseline: (id: number) => request(`/api/monitors/${id}/rebaseline`, { method: "POST" }),
  runs: (id: number) => request<CheckRun[]>(`/api/monitors/${id}/runs`),
  previewLoad: (payload: Record<string, unknown>) =>
    request<PreviewLoad>("/api/preview/load", { method: "POST", body: JSON.stringify(payload) }),
  previewSelect: (payload: Record<string, unknown>) =>
    request<PreviewSelection>("/api/preview/select-element", { method: "POST", body: JSON.stringify(payload) }),
  profiles: () => request<PushoverProfile[]>("/api/pushover-profiles"),
  validateProfile: (payload: Record<string, unknown>) =>
    request<{ status: string; devices: string[]; response: string }>("/api/pushover-profiles/validate", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createProfile: (payload: Record<string, unknown>) =>
    request<PushoverProfile>("/api/pushover-profiles", { method: "POST", body: JSON.stringify(payload) }),
  updateProfile: (id: number, payload: Record<string, unknown>) =>
    request<PushoverProfile>(`/api/pushover-profiles/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteProfile: (id: number) => request<void>(`/api/pushover-profiles/${id}`, { method: "DELETE" }),
  refreshProfileDevices: (id: number) =>
    request<PushoverProfile>(`/api/pushover-profiles/${id}/refresh-devices`, { method: "POST" }),
  testProfile: (id: number, payload: Record<string, unknown>) =>
    request<{ status: string; response: string }>(`/api/pushover-profiles/${id}/test`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  alerts: () => request<Alert[]>("/api/alerts")
};
