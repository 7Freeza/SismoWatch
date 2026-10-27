import type { Session } from "./types";

const SESSION_KEY = "sismowatch_session";
const LOGOUT_EVENT = "sismowatch:logout";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export function getSession(): Session | null {
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    localStorage.removeItem(SESSION_KEY);
    return null;
  }
}

export function saveSession(session: Session) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
  window.dispatchEvent(new Event(LOGOUT_EVENT));
}

export function onLogout(listener: () => void) {
  window.addEventListener(LOGOUT_EVENT, listener);
  return () => window.removeEventListener(LOGOUT_EVENT, listener);
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (body.detail) return JSON.stringify(body.detail);
  } catch {
    return `Error HTTP ${response.status}`;
  }
  return `Error HTTP ${response.status}`;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  const session = getSession();
  if (session) headers.set("Authorization", `Bearer ${session.token}`);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) {
    clearSession();
  }
  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function login(email: string, password: string): Promise<Session> {
  const data = await apiFetch<{
    access_token: string;
    role: "viewer" | "admin";
    email: string;
  }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
  return { token: data.access_token, role: data.role, email: data.email };
}

export async function downloadFile(path: string, filename: string) {
  const session = getSession();
  const headers = new Headers();
  if (session) headers.set("Authorization", `Bearer ${session.token}`);
  const response = await fetch(path, { headers });
  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
