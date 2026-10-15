import { tg } from "./tg";

export class ApiError extends Error {
  constructor(
    public code: string,
    public status: number,
    public params: Record<string, unknown> = {},
  ) {
    super(code);
  }
}

function devId(): string | null {
  // Browser testing without Telegram (backend must run with DEBUG=true): open /app/?dev=<telegram_id>
  const fromUrl = new URLSearchParams(window.location.search).get("dev");
  try {
    if (fromUrl) localStorage.setItem("devId", fromUrl);
    return fromUrl ?? localStorage.getItem("devId");
  } catch {
    return fromUrl;
  }
}

export function authHeader(): string {
  const w = tg();
  if (w) return `tma ${w.initData}`;
  const dev = devId();
  return dev ? `dev ${dev}` : "";
}

type Opts = { method?: string; body?: unknown; form?: FormData };

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = { Authorization: authHeader() };
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { method: opts.method ?? (body ? "POST" : "GET"), headers, body });
  } catch {
    throw new ApiError("network", 0);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(data.error ?? "generic", res.status, data.params);
  return data as T;
}

export async function uploadFile(file: File, purpose: string): Promise<number> {
  const form = new FormData();
  form.append("purpose", purpose);
  form.append("file", file);
  const res = await api<{ id: number }>("/files", { form });
  return res.id;
}

export async function fileUrl(id: number): Promise<string> {
  const res = await fetch(`/api/files/${id}`, { headers: { Authorization: authHeader() } });
  if (!res.ok) throw new ApiError("not_found", res.status);
  return URL.createObjectURL(await res.blob());
}
