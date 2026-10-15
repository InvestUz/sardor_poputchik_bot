import { useState } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { Chat, Check, Info, Lock, Phone } from "../components/icons";
import { CarLine, EmptyState, ErrorBox, Field, IconCircle, Loading, PageHead, PersonLine, PrivateNote, RouteStops, Sheet, StatusText, Stars } from "../components/ui";
import { dateTime, locName, money } from "../format";
import { MainAction, SecondaryAction } from "../hooks";
import { useApp, useLoad } from "../store";
import { confirmDestructive, confirmDialog, haptic, openTelegramUser } from "../tg";
import type { Order } from "../types";
import { Specs } from "./ListingDetail";

type Mode = null | "cancel" | "complain" | "review" | "code";
const FLOW = ["AWAITING_CONFIRMATION", "CONFIRMED", "IN_PROGRESS", "AWAITING_COMPLETION", "COMPLETED"];
const PRIMARY = new Set(["confirm", "start", "deliver", "complete", "review"]);

/** Vertical stepper with the time each stage was reached (timeline from the API, when present). */
function Stepper({ o }: { o: Order }) {
  const { t, lang } = useApp();
  const at = (s: string) => {
    const hit = o.timeline?.find((x) => x.status === s)?.at;
    if (hit) return hit;
    return s === "AWAITING_CONFIRMATION" ? o.created_at : undefined;
  };
  const off = o.status === "CANCELLED" || o.status === "DISPUTED";
  // for CANCELLED/DISPUTED, progress = the last FLOW status reached according to the timeline
  let idx = FLOW.indexOf(o.status);
  if (off) idx = Math.max(0, ...FLOW.map((s, i) => (at(s) ? i : 0)));
  const steps = off ? FLOW.slice(0, idx + 1) : FLOW;
  return (
    <ol className="stepper">
      {steps.map((s, i) => {
        const state = o.status === "COMPLETED" || i < idx || (off && i === idx) ? "done" : i === idx ? "now" : "todo";
        const time = at(s);
        return (
          <li key={s} className={state}>
            <span className="dot">{state === "done" && <Check size={14} strokeWidth={2.6} />}</span>
            <span className="lbl">{t(`o.vstep.${s}`)}</span>
            <span className="tm">{time && state !== "todo" ? dateTime(time, lang) : ""}</span>
          </li>
        );
      })}
      {off && (
        <li className="bad">
          <span className="dot" />
          <span className="lbl">{t(`st.${o.status}`)}</span>
          <span className="tm">{at(o.status) ? dateTime(at(o.status)!, lang) : ""}</span>
        </li>
      )}
    </ol>
  );
}

function nextStepKey(o: Order): string | null {
  const parcel = o.category !== "PASSENGER";
  switch (o.status) {
    case "AWAITING_CONFIRMATION":
    case "AWAITING_COMPLETION":
      return `o.next.${o.status}.${o.role}`;
    case "CONFIRMED":
      return `o.next.CONFIRMED.${o.role}${o.role === "client" && parcel ? "_parcel" : ""}`;
    case "IN_PROGRESS":
      if (o.role === "carrier" && o.code_locked) return "o.next.locked";
      return `o.next.IN_PROGRESS.${o.role}${o.role === "carrier" && o.needs_code ? "_parcel" : ""}`;
    case "COMPLETED":
      return o.actions.includes("review") ? "o.next.COMPLETED.review" : "o.next.COMPLETED.done";
    case "DISPUTED":
      return "o.next.DISPUTED";
    default:
      return null;
  }
}

export default function OrderDetail() {
  const { id } = useParams();
  const { t, lang, err, config } = useApp();
  const { data: o, error, loading, reload, setData } = useLoad(() => api<Order>(`/orders/${id}`), [id]);
  const [mode, setMode] = useState<Mode>(null);
  const [reason, setReason] = useState("");
  const [text, setText] = useState("");
  const [rating, setRating] = useState(0);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function run(path: string, body?: unknown) {
    setBusy(true);
    setMsg(null);
    try {
      setData(await api<Order>(`/orders/${o!.id}/${path}`, body === undefined ? { method: "POST" } : { body }));
      setMode(null);
      setReason("");
      setText("");
      setCode("");
      haptic("success");
    } catch (e) {
      haptic("error");
      setMsg(err(e));
      // backend demands the parcel code: open the code form; refresh attempts counter after a wrong code
      if (path === "deliver" && e instanceof ApiError && e.code === "code_required") setMode("code");
      if (path === "deliver" && e instanceof ApiError && (e.code === "invalid_code" || e.code === "code_locked")) {
        if (e.code === "code_locked") setMode(null);
        reload();
      }
    } finally {
      setBusy(false);
    }
  }

  async function act(action: string) {
    setMsg(null);
    if (action === "cancel" || action === "complain" || action === "review") {
      setMode(action);
      return;
    }
    if (action === "deliver" && o?.needs_code && !o.code_locked) {
      setMode("code");
      return;
    }
    if (await confirmDialog(t("act.confirm_ask"))) run(action);
  }

  async function sendReason() {
    if (mode === "cancel" && !(await confirmDestructive(t("o.cancel_confirm"), t("l.cancel_yes"), t("keep")))) return;
    run(mode!, { reason_code: reason, text });
  }

  // bottom-button wiring (MainButton in Telegram, in-page button in a browser)
  const primary = o ? o.actions.filter((a) => PRIMARY.has(a)) : [];
  const secondary = o ? o.actions.filter((a) => !PRIMARY.has(a)) : [];
  let main: { text: string; onClick: () => void; disabled?: boolean; variant?: "accent" } | null = null;
  if (o && mode === null && primary[0])
    main = { text: t(`act.${primary[0]}`), onClick: () => act(primary[0]), variant: primary[0] === "complete" || primary[0] === "confirm" ? "accent" : undefined };
  else if (o && mode === "code") main = { text: t("o.code_submit"), onClick: () => run("deliver", { code }), disabled: code.length !== 4 };
  else if (o && mode === "review") main = { text: t("send"), onClick: () => run("review", { rating, text }), disabled: !rating };

  if (loading && !o) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!o) return null;

  const cp = o.counterparty;
  const reasons = mode === "cancel" ? config!.cancel_reasons : config!.complaint_reasons;
  const next = nextStepKey(o);
  const locked = o.role === "carrier" && !!o.code_locked && o.status === "IN_PROGRESS";
  const mainEl = main && (
    <div style={{ margin: "14px 0" }}>
      <MainAction text={main.text} onClick={main.onClick} disabled={main.disabled} progress={busy} variant={main.variant} />
    </div>
  );
  const passenger = o.category === "PASSENGER";
  const d = o.details ?? {};
  const load = passenger
    ? d.whole_car
      ? t("l.whole_car")
      : String(d.passengers ?? o.quantity ?? "—")
    : d.weight_kg
      ? `${d.weight_kg} ${t("unit.kg")}`
      : "—";
  const plate = o.vehicle?.plate_number;
  const contact = o.revealed && (cp.phone || cp.username) && (
    <div className="call-btns">
      {cp.phone && (
        <a className="round-btn" href={`tel:${cp.phone}`} aria-label={`${t("o.call")} ${cp.phone}`}>
          <Phone size={20} />
        </a>
      )}
      {cp.username && (
        <button type="button" className="round-btn" onClick={() => openTelegramUser(cp.username!)} aria-label={t("o.write")}>
          <Chat size={20} />
        </button>
      )}
    </div>
  );

  return (
    <div>
      <PageHead title={t("o.title", { id: o.id })} />
      <section className="card summary">
        <div className="k">
          <span>
            {t(o.role === "client" ? "o.role_client" : "o.role_carrier")} · {t(`cat.${o.category}`)}
          </span>
          <StatusText status={o.status} prefix="st" />
        </div>
        <RouteStops size="lg" from={locName(o.from, lang)} to={locName(o.to, lang)} />
        <div className="sub">{dateTime(o.departure_at, lang)}</div>
      </section>

      {next && o.status === "COMPLETED" ? (
        <EmptyState icon={<Check size={44} strokeWidth={2.2} />} title={t("st.COMPLETED")} text={t(next)} />
      ) : next ? (
        <section className={`next-step ${locked ? "locked" : ""}`} aria-live="polite">
          <IconCircle>{locked ? <Lock size={20} /> : <Info size={20} />}</IconCircle>
          <div>
            <div className="k">{t("o.next")}</div>
            <p>{t(next)}</p>
            {o.confirm_deadline && o.status === "AWAITING_CONFIRMATION" && (
              <div className="sub">{t("o.confirm_until", { t: dateTime(o.confirm_deadline, lang) })}</div>
            )}
            {o.auto_complete_at && o.status === "AWAITING_COMPLETION" && (
              <div className="sub">{t("o.auto_complete", { t: dateTime(o.auto_complete_at, lang) })}</div>
            )}
          </div>
        </section>
      ) : null}

      {o.role === "client" && o.delivery_code && (
        <section className="code-card">
          <div className="k">{t("o.code_title")}</div>
          <div className="code-big" aria-label={o.delivery_code.split("").join(" ")}>
            {o.delivery_code}
          </div>
          <div className="hint">
            <Lock size={16} />
            <span>{t("o.code_hint")}</span>
          </div>
        </section>
      )}

      {mode === null && mainEl}
      {mode === null && primary[1] && (
        <div style={{ marginTop: 10 }}>
          <SecondaryAction text={t(`act.${primary[1]}`)} onClick={() => act(primary[1])} disabled={busy} />
        </div>
      )}
      {msg && mode === null && <div className="error-text">{msg}</div>}

      <section className="card driver">
        <PersonLine
          u={o.revealed ? { ...cp, name: cp.full_name || cp.name } : cp}
          carrier={o.role === "client"}
          label={t(o.role === "client" ? "o.counterparty_carrier" : "o.counterparty_client")}
          vehicle={o.vehicle}
          right={contact}
        />
        <div className="cols">
          <div>
            <span className="l">{t("price")}</span>
            <span className="v">
              {money(o.price)} <small>{t("som")}</small>
            </span>
          </div>
          <div>
            <span className="l">{plate ? t("o.plate") : t("l.vehicle")}</span>
            <span className="v">{plate ?? o.vehicle?.make_model ?? "—"}</span>
          </div>
          <div>
            <span className="l">{passenger ? t("o.col_seats") : t("o.col_weight")}</span>
            <span className="v">{load}</span>
          </div>
        </div>
        {o.vehicle && !o.revealed && <CarLine v={o.vehicle} />}
        {o.revealed && (
          <dl className="specs">
            {cp.phone && (
              <div>
                <dt>{t("p.phone")}</dt>
                <dd>
                  <a href={`tel:${cp.phone}`}>{cp.phone}</a>
                </dd>
              </div>
            )}
            {o.vehicle && (
              <div>
                <dt>{t("l.vehicle")}</dt>
                <dd>
                  {o.vehicle.make_model} {o.vehicle.color ?? ""}
                </dd>
              </div>
            )}
            {o.from_address && (
              <div>
                <dt>{t("l.from_address")}</dt>
                <dd>{o.from_address}</dd>
              </div>
            )}
            {o.to_address && (
              <div>
                <dt>{t("l.to_address")}</dt>
                <dd>{o.to_address}</dd>
              </div>
            )}
            {o.recipient_name && (
              <div>
                <dt>{t("o.recipient")}</dt>
                <dd>
                  {o.recipient_name}
                  <br />
                  {o.recipient_phone}
                </dd>
              </div>
            )}
          </dl>
        )}
        <Specs d={o.details} category={o.category} />
      </section>
      {!o.revealed && o.status !== "CANCELLED" && <PrivateNote text={t("l.address_hidden")} />}

      <section className="card">
        <h2 className="card-title">{t("o.stages")}</h2>
        <Stepper o={o} />
      </section>

      {o.my_review && (
        <section className="card">
          <h2 className="card-title">{t("o.your_review")}</h2>
          <Stars value={o.my_review.rating} size={20} />
          {o.my_review.text && <p style={{ marginBottom: 0 }}>“{o.my_review.text}”</p>}
        </section>
      )}

      {mode === null && secondary.length > 0 && (
        <div className="stack" style={{ marginTop: 20 }}>
          {secondary.map((a) => (
            <button key={a} className="btn block danger-ghost" disabled={busy} onClick={() => act(a)}>
              {t(`act.${a}`)}
            </button>
          ))}
        </div>
      )}

      {mode === "code" && (
        <Sheet title={t("o.code_title")} onClose={() => setMode(null)}>
          <Field label={t("o.code_enter")}>
            <input
              className="code-input"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={4}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 4))}
              autoFocus
            />
          </Field>
          {typeof o.code_attempts_left === "number" && <div className="small muted">{t("o.attempts_left", { n: o.code_attempts_left })}</div>}
          {msg && <div className="error-text">{msg}</div>}
          {mainEl}
        </Sheet>
      )}

      {(mode === "cancel" || mode === "complain") && (
        <Sheet title={t(`act.${mode}`)} onClose={() => setMode(null)}>
          <Field label={t("o.reason")}>
            <select value={reason} onChange={(e) => setReason(e.target.value)}>
              <option value="">—</option>
              {reasons.map((r) => (
                <option key={r} value={r}>
                  {t(`reason.${r}`)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("o.details_text")}>
            <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} />
          </Field>
          {msg && <div className="error-text">{msg}</div>}
          <button className="btn block danger" disabled={busy || !reason} onClick={sendReason}>
            {t("send")}
          </button>
        </Sheet>
      )}

      {mode === "review" && (
        <Sheet title={t("o.review_title")} onClose={() => setMode(null)}>
          <div className="stars-center">
            <Stars value={rating} onChange={setRating} size={36} />
          </div>
          <Field label={t("comment")} hint={t("optional")}>
            <textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} />
          </Field>
          {msg && <div className="error-text">{msg}</div>}
          {mainEl}
        </Sheet>
      )}
    </div>
  );
}
