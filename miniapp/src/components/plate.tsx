import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useApp } from "../store";
import { Check } from "./icons";
import { Chips, Sheet } from "./ui";

/** Uzbek licence plates. Normalized value (sent to API) has no spaces: 01A111AA / 01111AAA. */
export type PlateKind = "individual" | "legal";

export const PLATE_REGIONS = [
  "01",
  "10",
  "20",
  "25",
  "30",
  "40",
  "50",
  "60",
  "70",
  "75",
  "80",
  "85",
  "90",
  "95",
] as const;

const RE: Record<PlateKind, RegExp> = {
  individual: /^(\d{2})([A-Z])(\d{3})([A-Z]{2})$/,
  legal: /^(\d{2})(\d{3})([A-Z]{3})$/,
};

/** Segment layout after the region: kind of characters and length. */
const SEGS: Record<PlateKind, { digits: boolean; len: number }[]> = {
  individual: [
    { digits: false, len: 1 },
    { digits: true, len: 3 },
    { digits: false, len: 2 },
  ],
  legal: [
    { digits: true, len: 3 },
    { digits: false, len: 3 },
  ],
};

const PLACEHOLDER: Record<PlateKind, string[]> = {
  individual: ["A", "123", "BC"],
  legal: ["123", "ABC"],
};

export function parsePlate(
  v: string | null | undefined,
): { kind: PlateKind; region: string; segs: string[] } | null {
  const s = (v ?? "").replace(/[\s|-]/g, "").toUpperCase();
  for (const kind of ["individual", "legal"] as PlateKind[]) {
    const m = RE[kind].exec(s);
    if (m) return { kind, region: m[1], segs: m.slice(2) };
  }
  return null;
}

export const isValidPlate = (v: string | null | undefined) =>
  parsePlate(v) !== null;

/** "01A111AA" -> "01 A 111 AA"; unknown formats are returned as is. */
export function formatPlate(v: string | null | undefined): string {
  const p = parsePlate(v);
  return p ? [p.region, ...p.segs].join(" ") : (v ?? "");
}

/** Cyrillic look-alikes typed on a Russian keyboard map to the Latin plate letters. */
const CYR: Record<string, string> = {
  А: "A",
  В: "B",
  Е: "E",
  К: "K",
  М: "M",
  Н: "H",
  О: "O",
  Р: "P",
  С: "C",
  Т: "T",
  У: "Y",
  Х: "X",
};

function clean(raw: string, digits: boolean, len: number): string {
  const up = raw.toUpperCase().replace(/[А-ЯЁ]/g, (c) => CYR[c] ?? "");
  return up.replace(digits ? /[^0-9]/g : /[^A-Z]/g, "").slice(0, len);
}

function Flag() {
  return (
    <span className="pl-flag" aria-hidden="true">
      <span className="flag" />
      <span className="uz">UZ</span>
    </span>
  );
}

/** Read-only plate. Falls back to plain text when the value is not a known format. */
export function PlateView({
  plate,
  size,
}: {
  plate: string | null | undefined;
  size?: "sm";
}) {
  const p = parsePlate(plate);
  if (!p) return plate ? <span className="plate-text">{plate}</span> : null;
  return (
    <span
      className={`plate ${size ?? ""}`}
      role="img"
      aria-label={formatPlate(plate)}
    >
      <span className="pl-region">{p.region}</span>
      <span className="pl-main">
        {p.segs.map((s, i) => (
          <span key={i} className="pl-seg">
            {s}
          </span>
        ))}
      </span>
      <Flag />
    </span>
  );
}

/** Plate constructor: type switch + the plate itself as the input. */
export function PlateInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const { t, lang } = useApp();
  const init = parsePlate(value);
  const [kind, setKind] = useState<PlateKind>(init?.kind ?? "individual");
  const [region, setRegion] = useState(init?.region ?? "");
  const [segs, setSegs] = useState<string[]>(
    init?.segs ?? SEGS[kind].map(() => ""),
  );
  const [picking, setPicking] = useState(false);
  const emitted = useRef(value);
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const regionBtn = useRef<HTMLButtonElement>(null);

  // external value changes (e.g. form reset) re-parse into segments
  useEffect(() => {
    if (value === emitted.current) return;
    emitted.current = value;
    const p = parsePlate(value);
    if (p) {
      setKind(p.kind);
      setRegion(p.region);
      setSegs(p.segs);
    } else if (!value) {
      setRegion("");
      setSegs(SEGS[kind].map(() => ""));
    }
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps

  function emit(k: PlateKind, r: string, s: string[]) {
    setKind(k);
    setRegion(r);
    setSegs(s);
    const v = r + s.join("");
    emitted.current = v;
    onChange(v);
  }

  function focus(i: number) {
    const el = refs.current[i];
    if (el) {
      el.focus();
      const n = el.value.length;
      el.setSelectionRange?.(n, n);
    }
  }

  function onSeg(i: number, raw: string) {
    const whole = parsePlate(raw);
    if (whole) {
      emit(whole.kind, whole.region, whole.segs);
      return;
    }
    const spec = SEGS[kind][i];
    const next = segs.slice();
    next[i] = clean(raw, spec.digits, spec.len);
    emit(kind, region, next);
    if (next[i].length === spec.len && i < SEGS[kind].length - 1) focus(i + 1);
  }

  function onKey(i: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key !== "Backspace" || segs[i] !== "") return;
    e.preventDefault();
    if (i === 0) {
      regionBtn.current?.focus();
      return;
    }
    const next = segs.slice();
    next[i - 1] = next[i - 1].slice(0, -1);
    emit(kind, region, next);
    focus(i - 1);
  }

  const complete = isValidPlate(region + segs.join(""));
  const started = region !== "" || segs.some((s) => s !== "");
  const regionName = (code: string) => t(`plate.r${code}`);

  return (
    <div className="plate-input">
      <Chips
        label={t("cr.plate")}
        value={kind}
        onChange={(k) => {
          if (k === kind) return;
          emit(
            k,
            region,
            SEGS[k].map(() => ""),
          );
        }}
        options={[
          { value: "individual" as PlateKind, label: t("plate.individual") },
          { value: "legal" as PlateKind, label: t("plate.legal") },
        ]}
      />
      <div className={`plate lg editable ${complete ? "complete" : ""}`}>
        <button
          ref={regionBtn}
          type="button"
          className={`pl-region ${region ? "" : "empty"}`}
          onClick={() => setPicking(true)}
          aria-label={`${t("plate.region")}: ${region ? `${region} ${regionName(region)}` : "—"}`}
        >
          {region || "01"}
        </button>
        <span className="pl-main" key={kind}>
          {SEGS[kind].map((spec, i) => (
            <input
              key={i}
              ref={(el) => {
                refs.current[i] = el;
              }}
              className="pl-seg"
              style={{ ["--n" as string]: spec.len }}
              value={segs[i] ?? ""}
              placeholder={PLACEHOLDER[kind][i]}
              inputMode={spec.digits ? "numeric" : "text"}
              autoCapitalize={spec.digits ? "off" : "characters"}
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              maxLength={spec.len + 10}
              aria-label={t(
                spec.digits
                  ? "plate.seg_digits"
                  : spec.len === 1
                    ? "plate.seg_letter"
                    : "plate.seg_letters",
                { n: spec.len },
              )}
              onChange={(e) => onSeg(i, e.target.value)}
              onKeyDown={(e) => onKey(i, e)}
            />
          ))}
        </span>
        <Flag />
      </div>
      <div className="plate-hint">
        <span>
          {t(
            kind === "individual"
              ? "plate.hint_individual"
              : "plate.hint_legal",
          )}
        </span>
        <span
          className={`plate-state ${complete ? "ok" : started ? "bad" : ""}`}
          aria-live="polite"
        >
          {complete && <Check size={16} strokeWidth={2.4} />}
          {complete ? t("plate.complete") : t("plate.incomplete")}
        </span>
      </div>

      {picking && (
        <Sheet title={t("plate.region")} onClose={() => setPicking(false)}>
          <div className="city-list" lang={lang}>
            {PLATE_REGIONS.map((code) => (
              <button
                key={code}
                type="button"
                className={`city-row ${code === region ? "on" : ""}`}
                onClick={() => {
                  emit(kind, code, segs);
                  setPicking(false);
                  setTimeout(() => focus(0), 50);
                }}
              >
                <span className="region-code">{code}</span>
                <span className="body">
                  <span className="t">{regionName(code)}</span>
                </span>
                {code === region && <Check size={20} className="ok" />}
              </button>
            ))}
          </div>
        </Sheet>
      )}
    </div>
  );
}
