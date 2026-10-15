import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Box, ChevronRight, Contrast, Inbox, Pen, Route, Search, Truck } from "../components/icons";
import { Amount, Avatar, IconCircle, RouteStops, StatusText } from "../components/ui";
import { dateTime, locName } from "../format";
import { useApp, useLoad } from "../store";
import type { OrderBrief } from "../types";

export const ACTIVE_ORDER = ["AWAITING_CONFIRMATION", "CONFIRMED", "IN_PROGRESS", "AWAITING_COMPLETION", "DISPUTED"];

/** Nearest active order, pinned under the greeting. Silent when there is none or the request fails. */
function ActiveOrder() {
  const { t, lang } = useApp();
  const nav = useNavigate();
  const { data } = useLoad(() => api<OrderBrief[]>("/my/orders").catch(() => [] as OrderBrief[]), []);
  const active = (data ?? [])
    .filter((o) => ACTIVE_ORDER.includes(o.status))
    .sort((a, b) => a.departure_at.localeCompare(b.departure_at));
  if (!active.length) return null;
  const o = active[0];
  return (
    <button className="card active-order" onClick={() => nav(`/orders/${o.id}`)}>
      <div className="k">
        <span>{t("home.active_order")}</span>
        <StatusText status={o.status} prefix="st" />
      </div>
      <div className="lc-top">
        <RouteStops from={locName(o.from, lang)} to={locName(o.to, lang)} />
        <Amount value={o.price} />
      </div>
      <div className="lc-sub">
        {dateTime(o.departure_at, lang)} · {t(`cat.${o.category}`)} · {o.counterparty.name}
      </div>
      <div className="next">
        <span>{active.length > 1 ? t("home.more_orders", { n: active.length - 1 }) : t("o.title", { id: o.id })}</span>
        <ChevronRight size={20} />
      </div>
    </button>
  );
}

function Tile({ icon, title, sub, onClick }: { icon: ReactNode; title: string; sub?: string; onClick: () => void }) {
  return (
    <button type="button" className="tile-btn" onClick={onClick}>
      <IconCircle size="lg">{icon}</IconCircle>
      <span className="t">{title}</span>
      {sub && <span className="s">{sub}</span>}
    </button>
  );
}

export default function Home() {
  const { me, t, toggleTheme, config } = useApp();
  const nav = useNavigate();
  const carrier = me?.carrier;
  const approved = carrier?.status === "APPROVED";
  const parcel = config?.enabled_categories.includes("PARCEL");

  return (
    <div className="home">
      <div className="greet">
        <Avatar name={me?.first_name ?? ""} />
        <div className="hello">
          <h1>{t("home.hello", { name: me?.first_name ?? "" })}</h1>
          <p>{t("home.welcome")}</p>
        </div>
        <button className="icon-btn" onClick={toggleTheme} aria-label={t("theme")}>
          <Contrast size={22} />
        </button>
      </div>

      <ActiveOrder />

      <section className="where">
        <span className="grab" aria-hidden="true" />
        <h2>{t("home.where")}</h2>
        <button type="button" className="fake-input" onClick={() => nav("/search/ROUTE")}>
          <IconCircle>
            <Search size={20} />
          </IconCircle>
          <span>{t("home.where_ph")}</span>
        </button>
        <div className="tiles">
          <Tile icon={<Route size={24} />} title={t("hero.cta")} sub={t("home.find_trip_hint")} onClick={() => nav("/search/ROUTE")} />
          <Tile icon={<Pen size={24} />} title={t("home.post_request")} sub={t("home.post_request_hint")} onClick={() => nav("/create/REQUEST")} />
          {parcel && (
            <Tile
              icon={<Box size={24} />}
              title={t("home.send_parcel")}
              sub={t("home.send_parcel_hint")}
              onClick={() => nav("/create/REQUEST", { state: { category: "PARCEL" } })}
            />
          )}
          {approved ? (
            <>
              <Tile icon={<Inbox size={24} />} title={t("home.find_requests")} sub={t("home.find_requests_hint")} onClick={() => nav("/search/REQUEST")} />
              <Tile icon={<Truck size={24} />} title={t("home.post_route")} sub={t("home.post_route_hint")} onClick={() => nav("/create/ROUTE")} />
            </>
          ) : (
            <Tile
              icon={<Truck size={24} />}
              title={t("home.become_carrier")}
              sub={carrier?.status === "PENDING" ? t("home.carrier_pending") : t("home.become_carrier_hint")}
              onClick={() => nav("/carrier")}
            />
          )}
        </div>
      </section>
    </div>
  );
}
