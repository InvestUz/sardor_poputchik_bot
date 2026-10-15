import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { ArrowRight, Bell, Search as SearchIcon } from "../components/icons";
import { DateChips, EmptyState, ErrorBox, Field, ListingCard, Loading, PageHead, RoutePick } from "../components/ui";
import { useApp, useLoad } from "../store";
import type { Listing } from "../types";

type Filters = {
  category: string;
  from_location_id: number | "";
  to_location_id: number | "";
  date: string;
  price_max: string;
  min_rating: string;
  vehicle_type: string;
};

const EMPTY: Filters = { category: "", from_location_id: "", to_location_id: "", date: "", price_max: "", min_rating: "", vehicle_type: "" };

export default function Search() {
  const { kind = "ROUTE" } = useParams();
  const { t, config, err } = useApp();
  const nav = useNavigate();
  const [f, setF] = useState<Filters>(EMPTY);
  const [applied, setApplied] = useState<Filters>(EMPTY);
  const [more, setMore] = useState(false);
  const [subMsg, setSubMsg] = useState<string | null>(null);

  const { data, error, loading, reload } = useLoad(() => {
    const q = new URLSearchParams({ kind });
    for (const [k, v] of Object.entries(applied)) if (v !== "" && v !== null) q.set(k, String(v));
    return api<Listing[]>(`/listings?${q}`);
  }, [kind, applied]);

  const set = (k: keyof Filters) => (v: string | number) => setF((p) => ({ ...p, [k]: v }));
  const swap = () => setF((p) => ({ ...p, from_location_id: p.to_location_id, to_location_id: p.from_location_id }));

  async function subscribe() {
    setSubMsg(null);
    try {
      await api("/subscriptions", {
        body: { kind, category: f.category, from_location_id: f.from_location_id, to_location_id: f.to_location_id },
      });
      setSubMsg(t("search.subscribed"));
    } catch (e) {
      setSubMsg(err(e));
    }
  }

  const canSubscribe = f.category && f.from_location_id && f.to_location_id;

  return (
    <div>
      <PageHead title={t(`search.title_${kind}`)} />

      <div className="form-block">
        <RoutePick
          from={f.from_location_id}
          to={f.to_location_id}
          onFrom={set("from_location_id")}
          onTo={set("to_location_id")}
          onSwap={swap}
          placeholder={t("city.any")}
          optional
        />
        <div className="field">
          <span className="label">{t("date")}</span>
          <DateChips value={f.date} onChange={set("date")} allowAny />
        </div>
        <div className="grid2">
          <Field label={t("search.category")}>
            <select value={f.category} onChange={(e) => set("category")(e.target.value)}>
              <option value="">{t("any")}</option>
              {config!.enabled_categories.map((c) => (
                <option key={c} value={c}>
                  {t(`cat.${c}`)}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {more && (
          <div className="grid2">
            <Field label={t("search.price_max")}>
              <input type="number" inputMode="numeric" value={f.price_max} onChange={(e) => set("price_max")(e.target.value)} />
            </Field>
            <Field label={t("search.min_rating")}>
              <select value={f.min_rating} onChange={(e) => set("min_rating")(e.target.value)}>
                <option value="">{t("any")}</option>
                {[4.5, 4, 3].map((r) => (
                  <option key={r} value={r}>
                    {r}+
                  </option>
                ))}
              </select>
            </Field>
            {kind === "ROUTE" && (
              <Field label={t("search.vehicle_type")}>
                <select value={f.vehicle_type} onChange={(e) => set("vehicle_type")(e.target.value)}>
                  <option value="">{t("any")}</option>
                  {config!.vehicle_types.map((v) => (
                    <option key={v} value={v}>
                      {t(`vt.${v}`)}
                    </option>
                  ))}
                </select>
              </Field>
            )}
          </div>
        )}
        <button className="btn block" onClick={() => setApplied({ ...f })}>
          {t("search.button")}
        </button>
        <div className="actions" style={{ justifyContent: "space-between" }}>
          {!more ? (
            <button className="ulink sm" onClick={() => setMore(true)}>
              {t("search.more_filters")}
            </button>
          ) : (
            <span />
          )}
          {canSubscribe ? (
            <button className="ulink sm" onClick={subscribe}>
              <Bell size={15} /> {t("search.subscribe")}
            </button>
          ) : null}
        </div>
        {subMsg && <div className="hint" style={{ marginTop: 10 }}>{subMsg}</div>}
      </div>

      {loading && !data && <Loading />}
      {error ? <ErrorBox error={error} onRetry={reload} /> : null}
      {data && <div className="sec-title">{t("search.results", { n: data.length })}</div>}
      {data && data.length === 0 && (
        <EmptyState icon={<SearchIcon size={44} />} title={t("search.nothing")}>
          <button className="btn block" onClick={() => nav(kind === "ROUTE" ? "/create/REQUEST" : "/create/ROUTE")}>
            {t("search.post_own")} <ArrowRight size={18} />
          </button>
        </EmptyState>
      )}
      {data && data.length > 0 && (
        <div className="cards">
          {data.map((l) => (
            <ListingCard key={l.id} l={l} onClick={() => nav(`/listings/${l.id}`)} />
          ))}
        </div>
      )}
    </div>
  );
}
