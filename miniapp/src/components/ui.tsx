import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api, fileUrl, uploadFile } from "../api";
import { dateTime, locName, money, tashkentDate, timeOnly } from "../format";
import { useApp } from "../store";
import type { Listing, Loc, PriceHint, UserPublic, Vehicle } from "../types";
import { Alert, ArrowLeft, Car, Check, ChevronRight, Close, Info, Locate, Lock, Pin, Plus, Search as SearchIcon, Star, Swap } from "./icons";
import { tg } from "../tg";
import { geoSupported, getPosition, hasCoords, locHaystack, mapSearchUrl, nearestLoc, searchKey, splitMapLinks, withGeo, type GeoError } from "../geo";

export function Loading() {
  const { t } = useApp();
  return <div className="center muted">{t("loading")}</div>;
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { err, t } = useApp();
  return (
    <div className="panel">
      <div className="error-text">{err(error)}</div>
      {onRetry && (
        <button className="ulink sm" onClick={onRetry}>
          {t("retry")}
        </button>
      )}
    </div>
  );
}

/** `group` renders a <div role="group"> instead of <label> — for compound inputs (several fields / buttons). */
export function Field({ label, hint, group, children }: { label: string; hint?: string; group?: boolean; children: ReactNode }) {
  if (group)
    return (
      <div className="field" role="group" aria-label={label}>
        <span className="label">{label}</span>
        {children}
        {hint && <span className="hint">{hint}</span>}
      </div>
    );
  return (
    <label className="field">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </label>
  );
}

const TONE: Record<string, string> = {
  PUBLISHED: "live",
  IN_PROGRESS: "live",
  APPROVED: "ok",
  CONFIRMED: "ok",
  COMPLETED: "ok",
  ACCEPTED: "ok",
  PENDING: "wait",
  AWAITING_CONFIRMATION: "wait",
  AWAITING_COMPLETION: "wait",
  RESUBMIT: "wait",
  CANCELLED: "bad",
  REJECTED: "bad",
  REVOKED: "bad",
  DISPUTED: "bad",
  EXPIRED: "bad",
  WITHDRAWN: "bad",
  AUTO_CLOSED: "bad",
};

export function Badge({ status, prefix }: { status: string; prefix: string }) {
  const { t } = useApp();
  return <span className={`chip ${TONE[status] ?? ""}`}>{t(`${prefix}.${status}`)}</span>;
}

export function Stars({ value, onChange, size = 26 }: { value: number; onChange?: (v: number) => void; size?: number }) {
  return (
    <span className="stars">
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={i <= value ? "on" : ""} onClick={() => onChange?.(i)} role={onChange ? "button" : undefined}>
          <Star size={size} filled={i <= value} />
        </span>
      ))}
    </span>
  );
}

export function Rating({ rating, count }: { rating: number | null; count: number }) {
  const { t } = useApp();
  return rating ? (
    <span className="rating">
      <Star size={14} filled />
      {rating.toFixed(1)}
      <span className="muted">({count})</span>
    </span>
  ) : (
    <span className="muted">{t("l.no_rating")}</span>
  );
}

export function Avatar({ name, size }: { name: string; size?: "lg" }) {
  return <span className={`avatar ${size ?? ""}`}>{(name || "?").trim().charAt(0).toUpperCase()}</span>;
}

/** Light-green circle with a green icon (list rows, tiles). */
export function IconCircle({ children, size }: { children: ReactNode; size?: "lg" }) {
  return <span className={`ic-circle ${size ?? ""}`} aria-hidden="true">{children}</span>;
}

export function PrivateNote({ text }: { text: string }) {
  return (
    <div className="private-note">
      <Lock size={18} />
      <span>{text}</span>
    </div>
  );
}

const POPULAR = ["toshkent", "samarkand", "buhoro", "fargona", "andijon", "namangan", "karshi", "nukus"];

/** One city row in the picker sheet (≥48px, check on the selected one). */
function CityRow({ title, sub, on, onClick, icon, subError }: { title: string; sub?: string; on: boolean; onClick: () => void; icon?: ReactNode; subError?: boolean }) {
  return (
    <button type="button" className={`city-row ${on ? "on" : ""}`} aria-pressed={on} onClick={onClick}>
      {icon && <IconCircle>{icon}</IconCircle>}
      <span className="body">
        <span className="t">{title}</span>
        {sub && <span className={`s ${subError ? "err" : ""}`}>{sub}</span>}
      </span>
      {on && <Check size={20} strokeWidth={2.2} className="ok" />}
    </button>
  );
}

/** Bottom-sheet city picker body: sticky search, nearby, popular chips, region-grouped list. */
function CitySheet({
  value,
  onPick,
  optional,
}: {
  value: number | "";
  onPick: (v: number | "") => void;
  optional?: boolean;
}) {
  const { locations, lang, t } = useApp();
  const [q, setQ] = useState("");
  const [geo, setGeo] = useState<"idle" | "busy" | GeoError | "none">("idle");
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const id = window.setTimeout(() => input.current?.focus({ preventScroll: true }), 50);
    return () => window.clearTimeout(id);
  }, []);
  const region = (l: Loc) => (lang === "ru" ? l.region_ru : l.region_uz);
  const index = useMemo(() => locations.map((l) => ({ l, key: locHaystack(l), name: searchKey(l.name_uz), name2: searchKey(l.name_ru) })), [locations]);
  const key = searchKey(q);
  const canGeo = geoSupported() && locations.some(hasCoords);

  async function nearby() {
    setGeo("busy");
    try {
      const p = await getPosition();
      const n = nearestLoc(locations, p.lat, p.lon);
      if (!n) return setGeo("none");
      setGeo("idle");
      onPick(n.id);
    } catch (e) {
      setGeo(typeof e === "string" ? (e as GeoError) : "unavailable");
    }
  }

  let body: ReactNode;
  if (key) {
    const hits = index
      .filter((x) => x.key.includes(key))
      .sort((a, b) => Number(!(a.name.startsWith(key) || a.name2.startsWith(key))) - Number(!(b.name.startsWith(key) || b.name2.startsWith(key))));
    body = hits.length ? (
      <div className="city-list">
        {hits.map(({ l }) => (
          <CityRow key={l.id} title={locName(l, lang)} sub={region(l)} on={value === l.id} onClick={() => onPick(l.id)} />
        ))}
      </div>
    ) : (
      <div className="city-empty muted">{t("city.not_found")}</div>
    );
  } else {
    const groups = new Map<string, Loc[]>();
    for (const l of locations) groups.set(region(l), [...(groups.get(region(l)) ?? []), l]);
    const popular = POPULAR.map((p) => index.find((x) => x.name === p || x.name.startsWith(p + " "))?.l).filter((l): l is Loc => !!l);
    const geoSub =
      geo === "busy" ? t("geo.locating") : geo === "denied" ? t("geo.denied") : geo === "timeout" ? t("geo.timeout") : geo === "unavailable" ? t("geo.unavailable") : geo === "none" ? t("city.not_found") : t("geo.nearby_sub");
    body = (
      <>
        {optional && <div className="city-list"><CityRow title={t("city.any")} on={value === ""} onClick={() => onPick("")} /></div>}
        {canGeo && (
          <div className="city-list">
            <CityRow icon={<Locate size={20} />} title={t("geo.nearby")} sub={geoSub} subError={geo !== "idle" && geo !== "busy"} on={false} onClick={nearby} />
            {geo !== "idle" && geo !== "busy" && <span className="sr-only" role="alert">{geoSub}</span>}
          </div>
        )}
        {popular.length > 0 && (
          <>
            <div className="city-region static">{t("city.popular")}</div>
            <Chips options={popular.map((l) => ({ value: l.id, label: locName(l, lang) }))} value={value === "" ? null : value} onChange={(v) => onPick(v)} label={t("city.popular")} />
          </>
        )}
        {[...groups.entries()].map(([g, items]) => (
          <div key={g} className="city-group">
            <div className="city-region">{g}</div>
            <div className="city-list">
              {items.map((l) => (
                <CityRow key={l.id} title={locName(l, lang)} on={value === l.id} onClick={() => onPick(l.id)} />
              ))}
            </div>
          </div>
        ))}
      </>
    );
  }
  return (
    <>
      <div className="city-search">
        <SearchIcon size={20} aria-hidden="true" />
        <input ref={input} type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("city.search_ph")} aria-label={t("city.search_ph")} autoComplete="off" enterKeyHint="search" />
        {q && (
          <button type="button" className="clear" onClick={() => { setQ(""); input.current?.focus(); }} aria-label={t("city.clear")}>
            <Close size={18} />
          </button>
        )}
      </div>
      {body}
    </>
  );
}

/** Tap-to-open city picker (bottom sheet). Value contract: location id or "". */
export function LocationSelect({
  value,
  onChange,
  placeholder,
  label,
  optional,
}: {
  value: number | "";
  onChange: (v: number | "") => void;
  placeholder: string;
  label?: string;
  optional?: boolean;
}) {
  const { locations, lang } = useApp();
  const [open, setOpen] = useState(false);
  const cur = value === "" ? null : locations.find((l) => l.id === value);
  return (
    <>
      <button type="button" className={`loc-trigger ${cur ? "" : "ph"}`} aria-haspopup="dialog" aria-label={label ? `${label}: ${cur ? locName(cur, lang) : placeholder}` : undefined} onClick={() => setOpen(true)}>
        {cur ? locName(cur, lang) : placeholder}
      </button>
      {open && (
        <Sheet title={label ?? placeholder} onClose={() => setOpen(false)} className="city-sheet">
          <CitySheet
            value={value}
            optional={optional}
            onPick={(v) => {
              onChange(v);
              setOpen(false);
            }}
          />
        </Sheet>
      )}
    </>
  );
}

/** Address input + "Joriy joylashuvni qo'shish" (appends coordinates and a map link). */
export function AddressField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  const { t } = useApp();
  const [state, setState] = useState<"idle" | "busy" | GeoError>("idle");
  async function add() {
    setState("busy");
    try {
      const p = await getPosition();
      onChange(withGeo(value ?? "", p.lat, p.lon));
      setState("idle");
    } catch (e) {
      setState(typeof e === "string" ? (e as GeoError) : "unavailable");
    }
  }
  return (
    <div className="field">
      <label className="label" htmlFor={`addr-${label}`}>{label}</label>
      <input id={`addr-${label}`} type="text" value={value} onChange={(e) => onChange(e.target.value)} />
      <button type="button" className="geo-add" onClick={add} disabled={state === "busy"}>
        <Locate size={18} />
        {state === "busy" ? t("geo.locating") : t("geo.add_current")}
      </button>
      {state !== "idle" && state !== "busy" && (
        <div className="error-text" role="alert" style={{ margin: 0 }}>
          {t(`geo.${state}`)}
        </div>
      )}
    </div>
  );
}

/** Shows an address; map URLs become "Xaritada ochish" links, plain addresses get a map search link. */
export function AddressText({ text, city }: { text: string; city?: string }) {
  const { t } = useApp();
  const parts = splitMapLinks(text);
  const hasUrl = parts.some((p) => p.url);
  const link = (href: string, k?: number) => (
    <a key={k} className="map-link" href={href} target="_blank" rel="noreferrer">
      <Pin size={16} />
      {t("geo.open_map")}
    </a>
  );
  if (!hasUrl)
    return (
      <>
        {text}
        <br />
        {link(mapSearchUrl(city ? `${text}, ${city}` : text))}
      </>
    );
  return <>{parts.map((p, i) => (p.url ? link(p.url, i) : <Fragment key={i}>{p.text!.replace(/\s*·\s*$/, "")} </Fragment>))}</>;
}

export function AuthImg({ id, className }: { id: number; className?: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    let alive = true;
    fileUrl(id)
      .then((u) => {
        url = u;
        if (alive) setSrc(u);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [id]);
  return src ? <img src={src} className={className ?? "thumb"} alt="" /> : <div className={className ?? "thumb"} />;
}

export function Photos({ ids }: { ids: number[] }) {
  if (!ids.length) return null;
  return (
    <div className="photos">
      {ids.map((id) => (
        <AuthImg key={id} id={id} />
      ))}
    </div>
  );
}

export function PhotoUpload({ value, onChange, purpose, max = 5 }: { value: number[]; onChange: (ids: number[]) => void; purpose: string; max?: number }) {
  const { err } = useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function onFiles(files: FileList | null) {
    if (!files) return;
    setBusy(true);
    setError(null);
    const ids = [...value];
    try {
      for (const f of Array.from(files).slice(0, max - ids.length)) ids.push(await uploadFile(f, purpose));
      onChange(ids);
    } catch (e) {
      setError(err(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <div className="photos">
        {value.map((id) => (
          <div key={id} className="photo-edit">
            <AuthImg id={id} />
            <button type="button" className="x" onClick={() => onChange(value.filter((x) => x !== id))} aria-label="remove">
              <Close size={14} />
            </button>
          </div>
        ))}
        {value.length < max && (
          <label className={`thumb add ${busy ? "busy" : ""}`}>
            <Plus size={24} />
            <input type="file" accept="image/*" multiple hidden onChange={(e) => onFiles(e.target.files)} />
          </label>
        )}
      </div>
      {error && <div className="error-text">{error}</div>}
    </div>
  );
}

/** Colour + text status, utilitarian surfaces. */
export function StatusText({ status, prefix }: { status: string; prefix: string }) {
  const { t } = useApp();
  return <span className={`status ${TONE[status] ?? ""}`}>{t(`${prefix}.${status}`)}</span>;
}

/** Large tabular amount: "175 000 so'm". */
export function Amount({ value, suffix, className = "" }: { value: number; suffix?: string; className?: string }) {
  const { t } = useApp();
  return (
    <span className={`amount ${className}`}>
      {money(value)}
      <small>
        {t("som")}
        {suffix ?? ""}
      </small>
    </span>
  );
}

/**
 * Trust pill. Carriers: green "Tasdiqlangan" when verified, amber "Yangi" otherwise.
 * Clients: amber "Yangi" only for a first trip. Hidden when the backend doesn't send the fields yet.
 */
export function TrustPill({ u, carrier }: { u: UserPublic; carrier: boolean }) {
  const { t } = useApp();
  if (carrier && u.verified === true)
    return (
      <span className="pill ok">
        <Check size={14} strokeWidth={2.4} />
        {t("trust.verified")}
      </span>
    );
  const isNew = carrier ? u.verified === false : u.trips === 0;
  return isNew ? <span className="pill new">{t("trust.new")}</span> : null;
}

/** "★ 4.9 · 127 ta safar" */
export function TrustMeta({ u }: { u: UserPublic }) {
  const { t } = useApp();
  return (
    <div className="meta-line">
      {u.rating ? (
        <>
          <Star size={15} filled />
          <span>{u.rating.toFixed(1)}</span>
        </>
      ) : (
        <span>{t("l.no_rating")}</span>
      )}
      {typeof u.trips === "number" && (
        <>
          <span className="sep">·</span>
          <span>{t("trust.trips", { n: u.trips })}</span>
        </>
      )}
    </div>
  );
}

/** Avatar + name (opens the trust page when `link`) + trust pill + meta line. */
export function PersonLine({
  u,
  carrier,
  link = true,
  label,
  vehicle,
  right,
}: {
  u: UserPublic;
  carrier: boolean;
  link?: boolean;
  label?: string;
  /** handed to the trust page for its car rows */
  vehicle?: Vehicle | null;
  right?: ReactNode;
}) {
  const { t } = useApp();
  const nav = useNavigate();
  return (
    <div className="lc-person">
      <Avatar name={u.name} />
      <div className="who">
        {label && <div className="small muted">{label}</div>}
        <div className="name-row">
          {link ? (
            <button
              type="button"
              className="name-btn"
              aria-label={t("u.open", { name: u.name })}
              onClick={(e) => {
                e.stopPropagation();
                nav(`/users/${u.id}`, { state: { user: u, carrier, vehicle: vehicle ?? null } });
              }}
            >
              {u.name}
            </button>
          ) : (
            <span>{u.name}</span>
          )}
          <TrustPill u={u} carrier={carrier} />
        </div>
        <TrustMeta u={u} />
      </div>
      {right}
    </div>
  );
}

/** Car line: "Chevrolet Cobalt oq · jo'nash 08:00" */
export function CarLine({ v, departure }: { v: Vehicle | null; departure?: string }) {
  const { t } = useApp();
  if (!v && !departure) return null;
  return (
    <div className="lc-car">
      <Car size={18} />
      <span>
        {v ? `${v.make_model}${v.color ? ` ${v.color}` : ""}` : ""}
        {v && departure ? " · " : ""}
        {departure ? t("l.depart_at", { t: timeOnly(departure) }) : ""}
      </span>
    </div>
  );
}

/** Generic chip group. */
export function Chips<T extends string | number>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string; divider?: boolean }[];
  value: T | null;
  onChange: (v: T) => void;
  label?: string;
}) {
  return (
    <div className="chips" role="group" aria-label={label}>
      {options.map((o) => (
        <Fragment key={String(o.value)}>
          {o.divider && <span className="div" aria-hidden="true" />}
          <button type="button" className={value === o.value ? "on" : ""} aria-pressed={value === o.value} onClick={() => onChange(o.value)}>
            {o.label}
          </button>
        </Fragment>
      ))}
    </div>
  );
}

/** Date chips: Bugun / Ertaga / Indinga / Boshqa sana (+ optional "any"). Value is YYYY-MM-DD or "". */
export function DateChips({ value, onChange, allowAny = false }: { value: string; onChange: (v: string) => void; allowAny?: boolean }) {
  const { t } = useApp();
  const days = [0, 1, 2].map((d) => tashkentDate(d));
  const preset = value === "" ? (allowAny ? "any" : null) : days.includes(value) ? value : "other";
  const [other, setOther] = useState(preset === "other");
  const current = other ? "other" : preset;
  const opts: { value: string; label: string }[] = [
    ...(allowAny ? [{ value: "any", label: t("d.any") }] : []),
    { value: days[0], label: t("d.today") },
    { value: days[1], label: t("d.tomorrow") },
    { value: days[2], label: t("d.after") },
    { value: "other", label: t("d.other") },
  ];
  return (
    <>
      <Chips
        options={opts}
        value={current}
        label={t("date")}
        onChange={(v) => {
          if (v === "other") {
            setOther(true);
            if (days.includes(value) || value === "") onChange(tashkentDate(3));
          } else {
            setOther(false);
            onChange(v === "any" ? "" : v);
          }
        }}
      />
      {current === "other" && <input type="date" min={tashkentDate(0)} value={value} onChange={(e) => onChange(e.target.value)} aria-label={t("d.other")} />}
    </>
  );
}

const hintCache = new Map<string, PriceHint | null>();

/** GET /api/price-hint (contract C). Returns null while loading, on failure, or when the endpoint is missing. */
export function usePriceHint(category: string, from: number | "", to: number | "", seats = 1): PriceHint | null {
  const key = from && to && category ? `category=${category}&from_location_id=${from}&to_location_id=${to}&seats=${seats || 1}` : "";
  const [hint, setHint] = useState<PriceHint | null>(key ? (hintCache.get(key) ?? null) : null);
  useEffect(() => {
    if (!key) {
      setHint(null);
      return;
    }
    if (hintCache.has(key)) {
      setHint(hintCache.get(key) ?? null);
      return;
    }
    let alive = true;
    api<PriceHint>(`/price-hint?${key}`)
      .then((h) => (h && typeof h.min === "number" && typeof h.max === "number" ? h : null))
      .catch(() => null)
      .then((h) => {
        hintCache.set(key, h);
        if (alive) setHint(h);
      });
    return () => {
      alive = false;
    };
  }, [key]);
  return hint;
}

/** "Odatda 150 000–200 000 so'm": amber below the range, green inside, neutral above. */
export function PriceHintBox({ hint, value, onUse }: { hint: PriceHint | null; value: string | number; onUse?: (v: number) => void }) {
  const { t } = useApp();
  if (!hint) return null;
  const n = value === "" || value === null ? NaN : Number(value);
  const tone = Number.isNaN(n) || n <= 0 ? "" : n < hint.min ? "low" : n <= hint.max ? "ok" : "high";
  const src =
    hint.source === "history"
      ? t("ph.source_history")
      : hint.source === "distance" && hint.distance_km
        ? t("ph.source_distance", { km: Math.round(hint.distance_km) })
        : "";
  return (
    <div className={`price-hint ${tone === "high" ? "" : tone}`} role="status">
      {tone === "low" ? <Alert size={18} /> : tone === "ok" ? <Check size={18} /> : <Info size={18} />}
      <span>
        <b>{t("ph.usual", { min: money(hint.min), max: money(hint.max) })}</b>
        {src && <span className="src">{src}</span>}
        {tone && <span className="src">{t(`ph.${tone}`)}</span>}
        {onUse && hint.typical && Number(value) !== hint.typical && (
          <button type="button" className="use" onClick={() => onUse(hint.typical)}>
            {t("ph.use", { v: money(hint.typical) })}
          </button>
        )}
      </span>
    </div>
  );
}

/** Vertical pickup / dropoff: green dots joined by a line. */
export function RouteStops({ from, to, size }: { from: ReactNode; to: ReactNode; size?: "lg" }) {
  const { t } = useApp();
  return (
    <div className={`stops ${size ?? ""}`}>
      <div className="stop">
        <span className="pt" aria-hidden="true" />
        <span className="txt">
          <span className="k">{t("from")}</span>
          <span className="v">{from}</span>
        </span>
      </div>
      <div className="stop">
        <span className="pt to" aria-hidden="true" />
        <span className="txt">
          <span className="k">{t("to")}</span>
          <span className="v">{to}</span>
        </span>
      </div>
    </div>
  );
}

/** Pickup / dropoff picker: tap-to-open city sheets inside the vertical stops block + swap button. */
export function RoutePick({
  from,
  to,
  onFrom,
  onTo,
  onSwap,
  placeholder,
  optional,
}: {
  from: number | "";
  to: number | "";
  onFrom: (v: number | "") => void;
  onTo: (v: number | "") => void;
  onSwap: () => void;
  placeholder: string;
  /** shows an "Istalgan shahar" row (search filters) */
  optional?: boolean;
}) {
  const { t } = useApp();
  return (
    <div className="route-pick">
      <div className="stops">
        <div className="stop">
          <span className="pt" aria-hidden="true" />
          <span className="txt">
            <span className="k">{t("from")}</span>
            <LocationSelect value={from} onChange={onFrom} placeholder={placeholder} label={t("from")} optional={optional} />
          </span>
        </div>
        <div className="stop">
          <span className="pt to" aria-hidden="true" />
          <span className="txt">
            <span className="k">{t("to")}</span>
            <LocationSelect value={to} onChange={onTo} placeholder={placeholder} label={t("to")} optional={optional} />
          </span>
        </div>
      </div>
      <button className="swap-btn" type="button" onClick={onSwap} aria-label={t("swap")}>
        <Swap size={20} />
      </button>
    </div>
  );
}

/** Listing card: route stops + price, date, author trust, car · departure time. */
export function ListingCard({ l, onClick }: { l: Listing; onClick: () => void }) {
  const { t, lang } = useApp();
  const passenger = l.category === "PASSENGER";
  const cap =
    l.kind === "ROUTE"
      ? passenger
        ? t("l.seats_left", { n: l.capacity_available })
        : t("l.kg_left", { n: l.capacity_available })
      : passenger
        ? l.details.whole_car
          ? t("l.whole_car")
          : `${t("l.passengers")}: ${l.details.passengers ?? 1}`
        : l.details.weight_kg
          ? `${l.details.weight_kg} ${t("unit.kg")}`
          : "";
  return (
    <button className="card" onClick={onClick}>
      <div className="lc-top">
        <RouteStops from={locName(l.from, lang)} to={locName(l.to, lang)} />
        <Amount value={l.price} />
      </div>
      <div className="lc-sub">
        {dateTime(l.departure_at, lang)} · {t(`cat.${l.category}`)}
        {cap ? ` · ${cap}` : ""}
      </div>
      {l.is_mine ? (
        <div className="lc-foot">
          <StatusText status={l.status} prefix="lst" />
          {l.pending_offers ? <span className="pill ok">{t("l.pending_offers", { n: l.pending_offers })}</span> : null}
        </div>
      ) : (
        <>
          <PersonLine u={l.author} carrier={l.kind === "ROUTE"} link={false} />
          {l.vehicle && <CarLine v={l.vehicle} departure={l.departure_at} />}
        </>
      )}
    </button>
  );
}

/** Grey list row: green icon in a light-green circle, title, optional sub, chevron (or custom right side). */
export function RowLink({
  icon,
  title,
  sub,
  onClick,
  right,
  href,
}: {
  icon?: ReactNode;
  title: string;
  sub?: string;
  onClick?: () => void;
  right?: ReactNode;
  href?: string;
}) {
  const inner = (
    <>
      {icon && <IconCircle>{icon}</IconCircle>}
      <span className="body">
        <span className="t">{title}</span>
        {sub && <span className="s">{sub}</span>}
      </span>
      <span className="go">{right ?? <ChevronRight size={20} />}</span>
    </>
  );
  if (href)
    return (
      <a className="row-link" href={href} target="_blank" rel="noreferrer">
        {inner}
      </a>
    );
  return (
    <button type="button" className="row-link" onClick={onClick}>
      {inner}
    </button>
  );
}

/** Centered bold page title; back arrow in a browser (inside Telegram the native BackButton is used). */
export function PageHead({ title, sub, back = true }: { title: string; sub?: string; back?: boolean }) {
  const { t } = useApp();
  const nav = useNavigate();
  const showBack = back && !tg();
  return (
    <header className="page-head">
      <div className="bar">
        {showBack ? (
          <button type="button" className="back-btn" onClick={() => nav(-1)} aria-label={t("back")}>
            <ArrowLeft size={22} />
          </button>
        ) : (
          <span className="back-ph" />
        )}
        <h1>{title}</h1>
        <span className="back-ph" />
      </div>
      {sub && <p className="sub">{sub}</p>}
    </header>
  );
}

/** Three grey stat tiles: green icon, bold value, small label. */
export function StatTiles({ items }: { items: { icon: ReactNode; value: string; label: string }[] }) {
  return (
    <div className="stat-tiles">
      {items.map((x) => (
        <div key={x.label} className="tile">
          <span className="ti">{x.icon}</span>
          <span className="v">{x.value}</span>
          <span className="l">{x.label}</span>
        </div>
      ))}
    </div>
  );
}

/** Text tabs with a green underline on the active one. */
export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { value: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((x) => (
        <button
          key={x.value}
          type="button"
          role="tab"
          aria-selected={value === x.value}
          className={value === x.value ? "on" : ""}
          onClick={() => onChange(x.value)}
        >
          {x.label}
        </button>
      ))}
    </div>
  );
}

/** White bottom sheet with a grab handle over a dimmed backdrop. */
export function Sheet({ title, onClose, children, className }: { title: string; onClose: () => void; children: ReactNode; className?: string }) {
  const { t } = useApp();
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && close.current();
    window.addEventListener("keydown", k);
    document.body.classList.add("sheet-open");
    return () => {
      window.removeEventListener("keydown", k);
      document.body.classList.remove("sheet-open");
    };
  }, []);
  return (
    <div className="sheet-wrap">
      <button type="button" className="sheet-backdrop" aria-label={t("close")} onClick={onClose} />
      <section className={`sheet ${className ?? ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <span className="grab" aria-hidden="true" />
        <div className="sheet-head">
          <h2>{title}</h2>
          <button type="button" className="sheet-x" onClick={onClose} aria-label={t("close")}>
            <Close size={20} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}

/** Success / empty state: big green circle with a white icon, title, text, optional action. */
export function EmptyState({ icon, title, text, children }: { icon: ReactNode; title: string; text?: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <span className="big-circle" aria-hidden="true">
        {icon}
      </span>
      <h2>{title}</h2>
      {text && <p>{text}</p>}
      {children}
    </div>
  );
}
