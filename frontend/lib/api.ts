export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8765";

function cookie(name: string): string {
  if (typeof document === "undefined") return "";
  const item = document.cookie.split("; ").find((entry) => entry.startsWith(`${name}=`));
  return item ? decodeURIComponent(item.split("=").slice(1).join("=")) : "";
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET") {
    const csrf = cookie("smp_csrf");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers,
    cache: "no-store"
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail ?? `Request failed: ${response.status}`);
  return body as T;
}
