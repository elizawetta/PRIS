export type ApiError = {
  status: number;
  message: string;
  raw?: unknown;
};

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8000";

let accessToken: string | null = localStorage.getItem("mediconnect_token");

export function setAccessToken(token: string | null) {
  accessToken = token;
  if (token) localStorage.setItem("mediconnect_token", token);
  else localStorage.removeItem("mediconnect_token");
}

export function getAccessToken() {
  return accessToken;
}

async function parseJsonSafe(res: Response): Promise<any> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function api<T>(
  path: string,
  opts: {
    method?: string;
    query?: Record<string, string | number | boolean | undefined | null>;
    json?: unknown;
    form?: Record<string, string>;
    headers?: Record<string, string>;
  } = {},
): Promise<T> {
  const url = new URL(API_BASE_URL + path);
  if (opts.query) {
    for (const [k, v] of Object.entries(opts.query)) {
      if (v === undefined || v === null) continue;
      url.searchParams.set(k, String(v));
    }
  }

  const headers: Record<string, string> = { ...(opts.headers || {}) };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  let body: BodyInit | undefined = undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = new URLSearchParams(opts.form).toString();
  }

  const res = await fetch(url.toString(), {
    method: opts.method || "GET",
    headers,
    body,
  });

  if (!res.ok) {
    const raw = await parseJsonSafe(res);
    const message = typeof raw === "object" && raw && "detail" in raw ? String((raw as any).detail) : res.statusText;
    const err: ApiError = { status: res.status, message, raw };
    throw err;
  }

  return (await parseJsonSafe(res)) as T;
}

