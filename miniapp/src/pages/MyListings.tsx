import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { ArrowRight, Send, Stack } from "../components/icons";
import { Amount, Badge, EmptyState, ErrorBox, ListingCard, Loading, PageHead, RouteStops, Tabs } from "../components/ui";
import { dateTime, locName } from "../format";
import { useApp, useLoad } from "../store";
import type { Listing, Offer } from "../types";

export default function MyListings() {
  const { t, lang } = useApp();
  const nav = useNavigate();
  const [tab, setTab] = useState<"listings" | "offers">("listings");
  const listings = useLoad(() => api<Listing[]>("/my/listings"), []);
  const offers = useLoad(() => api<Offer[]>("/my/offers"), []);

  return (
    <div>
      <PageHead title={t("nav.my")} back={false} />
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "listings", label: `${t("my.listings")}${listings.data ? ` · ${listings.data.length}` : ""}` },
          { value: "offers", label: `${t("my.offers")}${offers.data ? ` · ${offers.data.length}` : ""}` },
        ]}
      />
      {tab === "listings" ? (
        <>
          {listings.loading && !listings.data && <Loading />}
          {listings.error ? <ErrorBox error={listings.error} onRetry={listings.reload} /> : null}
          {listings.data?.length === 0 && (
            <EmptyState icon={<Stack size={44} />} title={t("my.no_listings")}>
              <button className="btn block" onClick={() => nav("/create/REQUEST")}>
                {t("hero.cta2")} <ArrowRight size={18} />
              </button>
            </EmptyState>
          )}
          <div className="cards">
            {listings.data?.map((l) => (
              <ListingCard key={l.id} l={l} onClick={() => nav(`/listings/${l.id}`)} />
            ))}
          </div>
        </>
      ) : (
        <>
          {offers.loading && !offers.data && <Loading />}
          {offers.error ? <ErrorBox error={offers.error} onRetry={offers.reload} /> : null}
          {offers.data?.length === 0 && <EmptyState icon={<Send size={44} />} title={t("my.no_offers")} />}
          <div className="cards">
            {offers.data?.map((o) => (
              <button key={o.id} className="card" onClick={() => nav(`/listings/${o.listing_id}`)}>
                <div className="lc-top">
                  <RouteStops from={locName(o.route.from, lang)} to={locName(o.route.to, lang)} />
                  <Amount value={o.price} />
                </div>
                <div className="lc-sub">
                  {dateTime(o.route.departure_at, lang)} · {t(`cat.${o.listing_category}`)}
                </div>
                <div className="lc-foot">
                  <Badge status={o.status} prefix="ost" />
                  {o.can_respond && <span className="pill ok">{t("of.by_them")}</span>}
                </div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
