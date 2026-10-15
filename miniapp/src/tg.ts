// Thin wrapper over window.Telegram.WebApp so the app also runs in a normal browser (dev mode).

type BottomButtonParams = {
  text?: string;
  color?: string;
  text_color?: string;
  is_active?: boolean;
  is_visible?: boolean;
  has_shine_effect?: boolean;
  position?: "left" | "right" | "top" | "bottom";
};

export type BottomButton = {
  text: string;
  isVisible: boolean;
  isActive: boolean;
  isProgressVisible: boolean;
  setText(text: string): BottomButton;
  onClick(cb: () => void): BottomButton;
  offClick(cb: () => void): BottomButton;
  show(): BottomButton;
  hide(): BottomButton;
  enable(): BottomButton;
  disable(): BottomButton;
  showProgress(leaveActive?: boolean): BottomButton;
  hideProgress(): BottomButton;
  setParams(params: BottomButtonParams): BottomButton;
};

export type PopupButton = { id?: string; type?: "default" | "ok" | "close" | "cancel" | "destructive"; text?: string };
export type PopupParams = { title?: string; message: string; buttons?: PopupButton[] };

type CloudStorage = {
  getItem(key: string, cb: (err: string | null, value?: string) => void): void;
  setItem(key: string, value: string, cb?: (err: string | null, ok?: boolean) => void): void;
  removeItem(key: string, cb?: (err: string | null, ok?: boolean) => void): void;
};

type WebApp = {
  initData: string;
  version?: string;
  MainButton?: BottomButton;
  SecondaryButton?: BottomButton;
  CloudStorage?: CloudStorage;
  showPopup?(params: PopupParams, cb?: (buttonId: string) => void): void;
  enableClosingConfirmation?(): void;
  disableClosingConfirmation?(): void;
  colorScheme?: "light" | "dark";
  setHeaderColor?(color: string): void;
  setBackgroundColor?(color: string): void;
  setBottomBarColor?(color: string): void;
  disableVerticalSwipes?(): void;
  ready(): void;
  expand(): void;
  close(): void;
  BackButton: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void };
  HapticFeedback?: { notificationOccurred(type: "success" | "error" | "warning"): void };
  showConfirm?(message: string, cb: (ok: boolean) => void): void;
  openTelegramLink?(url: string): void;
  isVersionAtLeast?(v: string): boolean;
};

declare global {
  interface Window {
    Telegram?: { WebApp?: WebApp };
  }
}

export function tg(): WebApp | undefined {
  const w = window.Telegram?.WebApp;
  return w && w.initData ? w : undefined;
}

export function initTelegram(): void {
  const w = tg();
  w?.ready();
  w?.expand();
  try {
    w?.disableVerticalSwipes?.();
  } catch {
    /* not supported */
  }
  applyTheme(initialTheme());
}

export type Theme = "light" | "dark";

const THEME_BG: Record<Theme, string> = { light: "#FFFFFF", dark: "#121413" };

function storedTheme(): Theme | null {
  try {
    const v = localStorage.getItem("theme");
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

export function initialTheme(): Theme {
  const saved = storedTheme();
  if (saved) return saved;
  const scheme = window.Telegram?.WebApp?.colorScheme;
  if (scheme) return scheme;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Applies our own palette (not Telegram's) and paints Telegram's chrome to match. */
export function applyTheme(theme: Theme, persist = false): void {
  document.documentElement.dataset.theme = theme;
  if (persist) {
    try {
      localStorage.setItem("theme", theme);
    } catch {
      /* storage unavailable */
    }
  }
  const w = window.Telegram?.WebApp;
  try {
    w?.setHeaderColor?.(THEME_BG[theme]);
    w?.setBackgroundColor?.(THEME_BG[theme]);
    w?.setBottomBarColor?.(THEME_BG[theme]);
  } catch {
    /* older Telegram clients */
  }
}

export function haptic(type: "success" | "error" | "warning"): void {
  try {
    tg()?.HapticFeedback?.notificationOccurred(type);
  } catch {
    /* not supported */
  }
}

function atLeast(w: WebApp, v: string): boolean {
  try {
    return !!w.isVersionAtLeast?.(v);
  } catch {
    return false;
  }
}

/** Telegram's native bottom MainButton (Bot API 6.0+), or undefined outside Telegram. */
export function mainButton(): BottomButton | undefined {
  const w = tg();
  return w?.MainButton && atLeast(w, "6.0") ? w.MainButton : undefined;
}

/** Telegram's SecondaryButton exists only from Bot API 7.10. */
export function secondaryButton(): BottomButton | undefined {
  const w = tg();
  return w?.SecondaryButton && atLeast(w, "7.10") ? w.SecondaryButton : undefined;
}

/**
 * Native popup (Bot API 6.2+). Resolves with the pressed button id, or null if dismissed.
 * Outside Telegram falls back to window.confirm: OK resolves with the first non-cancel button id.
 */
export function showPopup(params: PopupParams): Promise<string | null> {
  const w = tg();
  if (w?.showPopup && atLeast(w, "6.2")) {
    return new Promise((resolve) => {
      try {
        w.showPopup!(params, (id) => resolve(id || null));
      } catch {
        resolve(null);
      }
    });
  }
  const ok = (params.buttons ?? []).find((b) => b.type !== "cancel" && b.type !== "close");
  const text = params.title ? `${params.title}\n\n${params.message}` : params.message;
  return Promise.resolve(window.confirm(text) ? (ok?.id ?? "ok") : null);
}

/** Destructive confirmation: true only when the destructive button is pressed. */
export async function confirmDestructive(message: string, okText: string, cancelText: string): Promise<boolean> {
  const id = await showPopup({
    message,
    buttons: [
      { id: "ok", type: "destructive", text: okText },
      { id: "cancel", type: "cancel", text: cancelText },
    ],
  });
  return id === "ok";
}

export function setClosingConfirmation(on: boolean): void {
  const w = tg();
  if (!w || !atLeast(w, "6.2")) return;
  try {
    if (on) w.enableClosingConfirmation?.();
    else w.disableClosingConfirmation?.();
  } catch {
    /* not supported */
  }
}

function cloud(): CloudStorage | undefined {
  const w = tg();
  return w?.CloudStorage && atLeast(w, "6.9") ? w.CloudStorage : undefined;
}

/** Telegram CloudStorage with localStorage fallback. Never throws; resolves null when unavailable. */
export const storage = {
  get(key: string): Promise<string | null> {
    const c = cloud();
    if (c)
      return new Promise((resolve) => {
        try {
          c.getItem(key, (err, value) => resolve(err ? null : value || null));
        } catch {
          resolve(null);
        }
      });
    try {
      return Promise.resolve(localStorage.getItem(key));
    } catch {
      return Promise.resolve(null);
    }
  },
  set(key: string, value: string): Promise<void> {
    const c = cloud();
    if (c)
      return new Promise((resolve) => {
        try {
          c.setItem(key, value, () => resolve());
        } catch {
          resolve();
        }
      });
    try {
      localStorage.setItem(key, value);
    } catch {
      /* storage unavailable */
    }
    return Promise.resolve();
  },
  remove(key: string): Promise<void> {
    const c = cloud();
    if (c)
      return new Promise((resolve) => {
        try {
          c.removeItem(key, () => resolve());
        } catch {
          resolve();
        }
      });
    try {
      localStorage.removeItem(key);
    } catch {
      /* storage unavailable */
    }
    return Promise.resolve();
  },
};

export function confirmDialog(message: string): Promise<boolean> {
  const w = tg();
  if (w?.showConfirm && w.isVersionAtLeast?.("6.2")) {
    return new Promise((resolve) => w.showConfirm!(message, resolve));
  }
  return Promise.resolve(window.confirm(message));
}

export function openTelegramUser(username: string): void {
  const url = `https://t.me/${username}`;
  const w = tg();
  if (w?.openTelegramLink) w.openTelegramLink(url);
  else window.open(url, "_blank");
}
