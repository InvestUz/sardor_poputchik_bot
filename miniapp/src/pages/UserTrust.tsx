import { useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { api } from "../api";
import { Calendar, Car, Check, Close, Plate, Road, Seat, Star } from "../components/icons";
import { Avatar, ErrorBox, IconCircle, Loading, PageHead, StatTiles, Stars, Tabs, TrustPill } from "../components/ui";
import { dateOnly } from "../format";
import { useApp, useLoad } from "../store";
import type { Review, UserPublic, UserTrust as Trust, Vehicle } from "../types";

const CHECKS: [keyof NonNullable<Trust["checks"]>, string][] = [
  ["phone", "p.phone"],
  ["driver_license", "doc.DRIVER_LICENSE"],
  ["tech_passport", "doc.TECH_PASSPORT"],
  ["vehicle_photo", "doc.VEHICLE_PHOTO"],
];

/** whole years since `iso` */
function yearsSince(iso: string): number {
  const ms = Date.now() - new Date(iso).getTime();
  return Math.max(0, Math.floor(ms / (365.25 * 24 * 3600 * 1000)));
}

/**
 * Trust page (contract B). Falls back to the user passed via navigation state plus the
 * existing /users/{id}/reviews endpoint when GET /users/{id} is not available.
 */
export default function UserTrust() {
  const { id } = useParams();
  const { t } = useApp();
  const state = (useLocation().state ?? {}) as { user?: UserPublic; carrier?: boolean; vehicle?: Vehicle | null };
  const [tab, setTab] = useState<"about" | "reviews">("about");
  const { data, error, loading, reload } = useLoad(async () => {
    try {
      return await api<Trust>(`/users/${id}`);
    } catch (e) {
      if (!state.user) throw e;
      const reviews = await api<Review[]>(`/users/${id}/reviews`).catch(() => [] as Review[]);
      return { ...state.user, reviews } as Trust;
    }
  }, [id]);

  if (loading && !data) return <Loading />;
  if (error || !data) return <ErrorBox error={error} onRetry={reload} />;
  const u = data;
  const carrier = state.carrier ?? !!u.verified;
  const reviews = u.reviews ?? [];
  const v = state.vehicle;
  const years = u.member_since ? yearsSince(u.member_since) : null;

  return (
    <div>
      <PageHead title={t(carrier ? "o.counterparty_carrier" : "o.counterparty_client")} />
      <div className="profile-hero">
        <Avatar name={u.name} size="lg" />
        <h2>{u.name}</h2>
        <TrustPill u={u} carrier={carrier} />
      </div>

      <StatTiles
        items={[
          { icon: <Road size={22} />, value: typeof u.trips === "number" ? String(u.trips) : "—", label: t("u.trips") },
          { icon: <Calendar size={22} />, value: years === null ? "—" : String(years), label: t("u.years", { n: years ?? 0 }) },
          {
            icon: <Star size={22} />,
            value: u.rating ? u.rating.toFixed(1) : "—",
            label: u.rating_count ? `${t("p.rating")} · ${u.rating_count}` : t("p.rating"),
          },
        ]}
      />

      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "about", label: t("u.about") },
          { value: "reviews", label: `${t("u.reviews")}${reviews.length ? ` · ${reviews.length}` : ""}` },
        ]}
      />

      {tab === "about" ? (
        <div className="rows">
          {u.member_since && (
            <div className="info-row">
              <IconCircle>
                <Calendar size={20} />
              </IconCircle>
              <span className="body">
                <span className="t">{t("u.member_since", { d: dateOnly(u.member_since) })}</span>
              </span>
            </div>
          )}
          {v && (
            <>
              <div className="sec-title">{t("u.car")}</div>
              <div className="info-row">
                <IconCircle>
                  <Car size={20} />
                </IconCircle>
                <span className="body">
                  <span className="s">{t("l.vehicle")}</span>
                  <span className="t">
                    {v.make_model}
                    {v.color ? ` · ${v.color}` : ""}
                  </span>
                </span>
              </div>
              <div className="info-row">
                <IconCircle>
                  <Seat size={20} />
                </IconCircle>
                <span className="body">
                  <span className="s">{t(`vt.${v.vehicle_type}`)}</span>
                  <span className="t">
                    {t("cr.seats")}: {v.seats} · {v.max_weight_kg} {t("unit.kg")}
                  </span>
                </span>
              </div>
              {v.plate_number && (
                <div className="info-row">
                  <IconCircle>
                    <Plate size={20} />
                  </IconCircle>
                  <span className="body">
                    <span className="s">{t("o.plate")}</span>
                    <span className="t">{v.plate_number}</span>
                  </span>
                </div>
              )}
            </>
          )}
          {u.checks && (
            <>
              <div className="sec-title">{t("u.checks")}</div>
              {CHECKS.map(([k, label]) => {
                const ok = !!u.checks?.[k];
                return (
                  <div key={k} className={`info-row ${ok ? "" : "no"}`}>
                    <IconCircle>{ok ? <Check size={18} strokeWidth={2.4} /> : <Close size={16} />}</IconCircle>
                    <span className="body">
                      <span className="t">{t(label)}</span>
                      {!ok && <span className="s">{t("u.check_missing")}</span>}
                    </span>
                  </div>
                );
              })}
            </>
          )}
          {!u.member_since && !v && !u.checks && <p className="body-muted">{t("u.no_info")}</p>}
        </div>
      ) : (
        <div>
          {reviews.length === 0 && <p className="body-muted">{t("u.no_reviews")}</p>}
          {reviews.map((r, i) => (
            <div key={i} className="review">
              <div className="top">
                <Avatar name={r.author} />
                <span className="who">
                  <b>{r.author}</b>
                  <span>{dateOnly(r.created_at)}</span>
                </span>
                <Stars value={r.rating} size={16} />
              </div>
              {r.text && <p>{r.text}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
