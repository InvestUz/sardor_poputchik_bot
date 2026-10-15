import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { ArrowRight, Route } from "../components/icons";
import { Amount, EmptyState, ErrorBox, Loading, PageHead, RouteStops, StatusText } from "../components/ui";
import { dateTime, locName } from "../format";
import { useApp, useLoad } from "../store";
import type { OrderBrief } from "../types";

export default function Orders() {
  const { t, lang } = useApp();
  const nav = useNavigate();
  const { data, error, loading, reload } = useLoad(() => api<OrderBrief[]>("/my/orders"), []);
  return (
    <div>
      <PageHead title={t("nav.orders")} back={false} />
      {loading && !data && <Loading />}
      {error ? <ErrorBox error={error} onRetry={reload} /> : null}
      {data?.length === 0 && (
        <EmptyState icon={<Route size={44} />} title={t("o.none")}>
          <button className="btn block" onClick={() => nav("/search/ROUTE")}>
            {t("hero.cta")} <ArrowRight size={18} />
          </button>
        </EmptyState>
      )}
      <div className="cards">
        {data?.map((o) => (
          <button key={o.id} className="card" onClick={() => nav(`/orders/${o.id}`)}>
            <div className="lc-top">
              <RouteStops from={locName(o.from, lang)} to={locName(o.to, lang)} />
              <Amount value={o.price} />
            </div>
            <div className="lc-sub">
              #{o.id} · {dateTime(o.departure_at, lang)} · {t(`cat.${o.category}`)}
            </div>
            <div className="lc-foot">
              <StatusText status={o.status} prefix="st" />
              <span className="small muted">
                {t(o.role === "client" ? "o.counterparty_carrier" : "o.counterparty_client")}: {o.counterparty.name}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
