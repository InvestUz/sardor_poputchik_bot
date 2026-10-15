import { useEffect, useRef, type ReactNode } from "react";
import { mainButton, secondaryButton, setClosingConfirmation, type BottomButton } from "./tg";

type Opts = { disabled?: boolean; progress?: boolean; visible?: boolean; variant?: "default" | "accent" };

function cssVar(name: string): string | undefined {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || undefined;
}

function useBottomButton(get: () => BottomButton | undefined, text: string, onClick: () => void, opts: Opts, secondary: boolean): boolean {
  const btn = get();
  const cb = useRef(onClick);
  cb.current = onClick;
  const { disabled = false, progress = false, visible = true, variant = "default" } = opts;

  // one stable click handler per mount
  useEffect(() => {
    if (!btn) return;
    const handler = () => cb.current();
    btn.onClick(handler);
    return () => {
      try {
        btn.offClick(handler);
        btn.hideProgress();
        btn.hide();
      } catch {
        /* client closed */
      }
    };
  }, [btn]);

  useEffect(() => {
    if (!btn) return;
    try {
      btn.setParams({
        text,
        is_visible: visible,
        is_active: !disabled && !progress,
        ...(secondary
          ? { position: "bottom" as const }
          : {
              color: cssVar("--primary"),
              text_color: cssVar("--on-primary"),
            }),
      });
      if (progress) btn.showProgress(false);
      else btn.hideProgress();
    } catch {
      /* older clients */
    }
  }, [btn, text, disabled, progress, visible, variant, secondary]);

  return !!btn;
}

/** Drives Telegram's MainButton. Returns true when the native button is used (else render an in-page button). */
export function useMainButton(text: string, onClick: () => void, opts: Opts = {}): boolean {
  return useBottomButton(mainButton, text, onClick, opts, false);
}

/** Drives Telegram's SecondaryButton (Bot API 7.10+). Returns true when native. */
export function useSecondaryButton(text: string, onClick: () => void, opts: Opts = {}): boolean {
  return useBottomButton(secondaryButton, text, onClick, opts, true);
}

/** Primary page action: native MainButton inside Telegram, a normal block button in a browser. Use once per page. */
export function MainAction({
  text,
  onClick,
  disabled,
  progress,
  variant,
  icon = null,
}: {
  text: string;
  onClick: () => void;
  disabled?: boolean;
  progress?: boolean;
  variant?: "default" | "accent";
  icon?: ReactNode;
}) {
  const native = useMainButton(text, onClick, { disabled, progress, variant });
  if (native) return null;
  return (
    <button className="btn block" disabled={disabled || progress} onClick={onClick}>
      {text}
      {icon}
    </button>
  );
}

/** Secondary page action: native SecondaryButton when supported, otherwise an in-page ghost button. */
export function SecondaryAction({ text, onClick, disabled }: { text: string; onClick: () => void; disabled?: boolean }) {
  const native = useSecondaryButton(text, onClick, { disabled });
  if (native) return null;
  return (
    <button className="btn block ghost" disabled={disabled} onClick={onClick}>
      {text}
    </button>
  );
}

/** Asks Telegram to confirm before closing the Mini App while `on` is true. */
export function useClosingConfirmation(on: boolean): void {
  useEffect(() => {
    setClosingConfirmation(on);
    return () => setClosingConfirmation(false);
  }, [on]);
}

/** Re-runs `fn` every `ms` while `active`. */
export function useInterval(fn: () => void, ms: number, active: boolean): void {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => ref.current(), ms);
    return () => window.clearInterval(id);
  }, [ms, active]);
}
