import { useCallback, useEffect, useState } from "react";
import { formatPlate, PlateView } from "../components/plate";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { ArrowRight, Inbox, Pin } from "../components/icons";
import {
  AddressField,
  Amount,
  CarLine,
  EmptyState,
  ErrorBox,
  Field,
  Loading,
  PersonLine,
  Photos,
  PhotoUpload,
  PriceHintBox,
  PageHead,
  PrivateNote,
  RouteStops,
  StatusText,
  usePriceHint,
} from "../components/ui";
import { dateTime, locName, money } from "../format";
import { MainAction, useInterval } from "../hooks";
import { useApp, useLoad } from "../store";
import { confirmDestructive, confirmDialog, haptic } from "../tg";
import type {
  Listing,
  ListingActivity,
  Offer,
  PriceHint,
  Vehicle,
} from "../types";

export function Specs({
  d,
  category,
}: {
  d: Record<string, any>;
  category: string;
}) {
  const { t } = useApp();
  const rows: [string, string][] = [];
  if (category === "PASSENGER") {
    if (d.whole_car) rows.push([t("l.passengers"), t("l.whole_car")]);
    else if (d.passengers) rows.push([t("l.passengers"), String(d.passengers)]);
    if (d.luggage) rows.push([t("l.luggage"), d.luggage]);
    if (d.stops_allowed) rows.push([t("l.stops_allowed"), "+"]);
  } else {
    if (d.description) rows.push([t("l.description"), d.description]);
    if (d.quantity) rows.push([t("l.quantity"), String(d.quantity)]);
    if (d.weight_kg)
      rows.push([t("l.weight"), `${d.weight_kg} ${t("unit.kg")}`]);
    if (d.length_cm)
      rows.push([
        t("l.dims"),
        `${d.length_cm} × ${d.width_cm} × ${d.height_cm}`,
      ]);
    if (d.fragile) rows.push([t("l.fragile"), "+"]);
  }
  if (!rows.length) return null;
  return (
    <dl className="specs">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

/** seats used for the price hint of a listing / booking */
function hintSeats(category: string, d: Record<string, any>): number {
  if (category !== "PASSENGER") return 1;
  return d.whole_car ? 4 : Number(d.passengers) || 1;
}

/** "8 ta tashuvchi bu yo'nalishda · 2 tasi ko'rdi" — author only, refreshed every 20 s, hidden on failure. */
function ActivityLine({ id }: { id: number }) {
  const { t } = useApp();
  const [a, setA] = useState<ListingActivity | null>(null);
  const load = useCallback(() => {
    api<ListingActivity>(`/listings/${id}/activity`)
      .then((x) =>
        setA(
          x &&
            typeof x.carriers_on_route === "number" &&
            typeof x.viewed === "number"
            ? x
            : null,
        ),
      )
      .catch(() => setA(null));
  }, [id]);
  useEffect(load, [load]);
  useInterval(load, 20000, true);
  if (!a) return null;
  return (
    <div className="card activity" role="status" aria-live="polite">
      <span className="live-dot" aria-hidden="true" />
      <span>{t("l.activity", { c: a.carriers_on_route, v: a.viewed })}</span>
    </div>
  );
}

function OfferCard({
  o,
  carrierSide,
  hint,
  onChanged,
}: {
  o: Offer;
  carrierSide: boolean;
  hint: PriceHint | null;
  onChanged: (orderId?: number) => void;
}) {
  const { t, lang, err } = useApp();
  const [counter, setCounter] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      const res: any = await fn();
      haptic("success");
      setCounter(null);
      onChanged(res?.order_id);
    } catch (e) {
      haptic("error");
      setError(err(e));
    } finally {
      setBusy(false);
    }
  }

  const accept = async () => {
    if (await confirmDialog(t("of.accept_confirm", { price: money(o.price) })))
      run(() => api(`/offers/${o.id}/accept`, { method: "POST" }));
  };

  return (
    <div className="card">
      <div className="lc-top">
        <Amount value={o.price} />
        <StatusText status={o.status} prefix="ost" />
      </div>
      <PersonLine
        u={o.counterparty}
        carrier={carrierSide}
        label={o.proposed_by_me ? t("of.by_me") : t("of.by_them")}
        vehicle={o.vehicle}
      />
      <CarLine
        v={o.vehicle}
        departure={o.vehicle ? o.route.departure_at : undefined}
      />
      {o.listing_kind === "ROUTE" && (
        <Specs d={o.details} category={o.listing_category} />
      )}
      {o.comment && <p className="lc-note">“{o.comment}”</p>}
      <Photos ids={o.photo_ids} />
      {o.status === "PENDING" && (
        <div className="small muted" style={{ marginTop: 10 }}>
          {t("of.expires", { t: dateTime(o.expires_at, lang) })}
        </div>
      )}
      {o.can_respond && counter === null && (
        <div className="actions">
          <button className="btn sm" disabled={busy} onClick={accept}>
            {t("of.accept")}
          </button>
          <button
            className="btn sm ghost"
            disabled={busy}
            onClick={() => setCounter(String(o.price))}
          >
            {t("of.counter")}
          </button>
          <button
            className="btn sm text-danger"
            disabled={busy}
            onClick={() =>
              run(() => api(`/offers/${o.id}/reject`, { method: "POST" }))
            }
          >
            {t("of.reject")}
          </button>
        </div>
      )}
      {counter !== null && (
        <div style={{ marginTop: 14 }}>
          <Field label={t("of.counter_price")}>
            <input
              type="number"
              inputMode="numeric"
              value={counter}
              onChange={(e) => setCounter(e.target.value)}
              autoFocus
            />
            <PriceHintBox
              hint={hint}
              value={counter}
              onUse={(x) => setCounter(String(x))}
            />
          </Field>
          <div className="actions" style={{ marginTop: 0 }}>
            <button
              className="btn sm"
              disabled={busy || !counter}
              onClick={() =>
                run(() =>
                  api(`/offers/${o.id}/counter`, {
                    body: { price: Number(counter) },
                  }),
                )
              }
            >
              {t("send")}
            </button>
            <button className="ulink sm mute" onClick={() => setCounter(null)}>
              {t("cancel")}
            </button>
          </div>
        </div>
      )}
      {o.status === "PENDING" && o.proposed_by_me && (
        <div className="actions" style={{ justifyContent: "space-between" }}>
          <span className="status live">{t("of.waiting")}</span>
          <button
            className="ulink sm mute"
            disabled={busy}
            onClick={() =>
              run(() => api(`/offers/${o.id}/withdraw`, { method: "POST" }))
            }
          >
            {t("of.withdraw")}
          </button>
        </div>
      )}
      {error && <div className="error-text">{error}</div>}
    </div>
  );
}

function OfferForm({ l, onSent }: { l: Listing; onSent: () => void }) {
  const { t, me, err } = useApp();
  const nav = useNavigate();
  const isRequest = l.kind === "REQUEST";
  const passenger = l.category === "PASSENGER";
  const canOffer = !isRequest || me?.carrier?.permissions.includes(l.category);
  const vehicles = useLoad(
    () =>
      isRequest && canOffer
        ? api<{ vehicles: Vehicle[] }>("/carrier").then((r) => r.vehicles)
        : Promise.resolve([]),
    [isRequest, canOffer],
  );
  const [v, setV] = useState<Record<string, any>>({
    price: String(l.price),
    comment: "",
    vehicle_id: "",
    passengers: 1,
    luggage: "",
    description: "",
    quantity: 1,
    weight_kg: "",
    length_cm: "",
    width_cm: "",
    height_cm: "",
    fragile: false,
    photo_ids: [] as number[],
    from_address: "",
    to_address: "",
    recipient_name: "",
    recipient_phone: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seats = isRequest
    ? hintSeats(l.category, l.details)
    : passenger
      ? Number(v.passengers) || 1
      : 1;
  const hint = usePriceHint(l.category, l.from.id, l.to.id, seats);
  const set = (k: string) => (val: unknown) =>
    setV((p) => ({ ...p, [k]: val }));
  const inp = (k: string, type = "text") => ({
    value: v[k],
    type,
    inputMode: type === "number" ? ("numeric" as const) : undefined,
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      set(k)(e.target.value),
  });

  async function submit() {
    setBusy(true);
    setError(null);
    const num = (x: string | number) => (x === "" ? null : Number(x));
    try {
      await api(`/listings/${l.id}/offers`, {
        body: {
          ...v,
          price: num(v.price),
          vehicle_id: num(v.vehicle_id),
          passengers: num(v.passengers),
          quantity: num(v.quantity),
          weight_kg: num(v.weight_kg),
          length_cm: num(v.length_cm),
          width_cm: num(v.width_cm),
          height_cm: num(v.height_cm),
        },
      });
      haptic("success");
      onSent();
    } catch (e) {
      haptic("error");
      setError(err(e));
    } finally {
      setBusy(false);
    }
  }

  if (!canOffer)
    return (
      <div className="card">
        <p className="body-muted" style={{ marginTop: 0 }}>
          {t("l.need_carrier")}
        </p>
        <button className="btn block" onClick={() => nav("/carrier")}>
          {t("home.become_carrier")} <ArrowRight size={18} />
        </button>
      </div>
    );

  const selectedPlate = vehicles.data?.find(
    (x) => String(x.id) === String(v.vehicle_id),
  )?.plate_number;

  return (
    <>
      <div className="card">
        <h2 className="card-title">
          {isRequest ? t("l.make_offer") : t("l.book")}
        </h2>
        {isRequest ? (
          <>
            <Field label={t("c.vehicle")}>
              <select
                value={v.vehicle_id}
                onChange={(e) => set("vehicle_id")(e.target.value)}
              >
                <option value="">—</option>
                {vehicles.data?.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.make_model} · {formatPlate(x.plate_number)}
                  </option>
                ))}
              </select>
            </Field>
            {selectedPlate && (
              <div className="plate-pick">
                <PlateView plate={selectedPlate} size="sm" />
              </div>
            )}
          </>
        ) : passenger ? (
          <>
            <Field label={t("l.passengers")}>
              <input
                type="number"
                inputMode="numeric"
                min={1}
                max={l.capacity_available}
                value={v.passengers}
                onChange={(e) => {
                  const n = e.target.value;
                  setV((p) => ({
                    ...p,
                    passengers: n,
                    price: n ? String(l.price * Number(n)) : p.price,
                  }));
                }}
              />
            </Field>
            <Field label={t("l.luggage")}>
              <input {...inp("luggage")} placeholder={t("l.luggage_hint")} />
            </Field>
          </>
        ) : (
          <>
            <Field label={t("l.description")}>
              <input {...inp("description")} />
            </Field>
            <div className="grid2">
              <Field label={t("l.quantity")}>
                <input {...inp("quantity", "number")} />
              </Field>
              <Field label={t("l.weight")}>
                <input
                  {...inp("weight_kg", "number")}
                  max={l.capacity_available}
                />
              </Field>
            </div>
            <Field label={t("l.dims")}>
              <div className="grid3">
                <input
                  {...inp("length_cm", "number")}
                  placeholder={t("l.length")}
                />
                <input
                  {...inp("width_cm", "number")}
                  placeholder={t("l.width")}
                />
                <input
                  {...inp("height_cm", "number")}
                  placeholder={t("l.height")}
                />
              </div>
            </Field>
            <label className="check">
              <input
                type="checkbox"
                checked={v.fragile}
                onChange={(e) => set("fragile")(e.target.checked)}
              />{" "}
              {t("l.fragile")}
            </label>
            <Field label={t("l.photos")} hint={t("l.photos_required")}>
              <PhotoUpload
                value={v.photo_ids}
                onChange={set("photo_ids")}
                purpose="OFFER_PHOTO"
              />
            </Field>
            <div className="grid2">
              <Field label={t("l.recipient_name")}>
                <input {...inp("recipient_name")} />
              </Field>
              <Field label={t("l.recipient_phone")}>
                <input {...inp("recipient_phone", "tel")} placeholder="+998" />
              </Field>
            </div>
          </>
        )}
        {!isRequest && (
          <>
            <AddressField
              label={t("l.from_address")}
              value={v.from_address}
              onChange={set("from_address")}
            />
            <AddressField
              label={t("l.to_address")}
              value={v.to_address}
              onChange={set("to_address")}
            />
            <PrivateNote text={t("l.address_hidden")} />
          </>
        )}
        <Field label={isRequest ? t("l.price_offer") : t("l.price_total")}>
          <input {...inp("price", "number")} />
          <PriceHintBox
            hint={hint}
            value={v.price}
            onUse={(x) => set("price")(String(x))}
          />
        </Field>
        <Field label={t("comment")} hint={t("optional")}>
          <input {...inp("comment")} />
        </Field>
        {error && <div className="error-text">{error}</div>}
      </div>
      <MainAction
        text={isRequest ? t("l.make_offer") : t("send")}
        onClick={submit}
        progress={busy}
      />
    </>
  );
}

export default function ListingDetail() {
  const { id } = useParams();
  const { t, lang, err } = useApp();
  const nav = useNavigate();
  const listing = useLoad(() => api<Listing>(`/listings/${id}`), [id]);
  const offers = useLoad(() => api<Offer[]>(`/listings/${id}/offers`), [id]);
  const [error, setError] = useState<string | null>(null);
  const l0 = listing.data;
  const hint = usePriceHint(
    l0?.category ?? "",
    l0?.from.id ?? "",
    l0?.to.id ?? "",
    l0 ? hintSeats(l0.category, l0.details) : 1,
  );

  if (listing.loading && !listing.data) return <Loading />;
  if (listing.error)
    return <ErrorBox error={listing.error} onRetry={listing.reload} />;
  const l = listing.data!;
  const visibleOffers = (offers.data ?? []).filter(
    (o) => o.status !== "COUNTERED",
  );
  const active = l.status === "PUBLISHED";
  const myPending = visibleOffers.some((o) => o.status === "PENDING");
  // the counterparty of an offer is a carrier when: I wrote a REQUEST, or I'm answering someone's ROUTE
  const counterpartyIsCarrier = l.is_mine
    ? l.kind === "REQUEST"
    : l.kind === "ROUTE";

  const onChanged = (orderId?: number) => {
    if (orderId) nav(`/orders/${orderId}`);
    else {
      listing.reload();
      offers.reload();
    }
  };

  async function cancelListing() {
    if (
      !(await confirmDestructive(
        t("l.cancel_confirm"),
        t("l.cancel_yes"),
        t("keep"),
      ))
    )
      return;
    try {
      await api(`/listings/${l.id}/cancel`, { method: "POST" });
      haptic("success");
      listing.reload();
    } catch (e) {
      haptic("error");
      setError(err(e));
    }
  }

  return (
    <div>
      <PageHead title={t(`kind.${l.kind}`)} />
      <section className="card summary">
        <div className="k">
          <span>{t(`cat.${l.category}`)}</span>
          <StatusText status={l.status} prefix="lst" />
        </div>
        <RouteStops
          size="lg"
          from={locName(l.from, lang)}
          to={locName(l.to, lang)}
        />
        <div className="sub">
          {dateTime(l.departure_at, lang)}
          {l.time_flexible ? ` · ${t("l.time_flexible")}` : ""}
        </div>
        <div className="lc-foot">
          <Amount
            value={l.price}
            className="xl"
            suffix={
              l.kind === "ROUTE" && l.category === "PASSENGER" ? " / 1" : ""
            }
          />
          {l.kind === "ROUTE" && (
            <span className="pill ok">
              {l.category === "PASSENGER"
                ? t("l.seats_left", { n: l.capacity_available })
                : t("l.kg_left", { n: l.capacity_available })}
            </span>
          )}
        </div>
      </section>

      {l.is_mine && active && <ActivityLine id={l.id} />}

      <section className="card">
        <Specs d={l.details} category={l.category} />
        {l.vehicle && <CarLine v={l.vehicle} departure={l.departure_at} />}
        {l.comment && <p className="lc-note">“{l.comment}”</p>}
        <Photos ids={l.photo_ids} />
        {!l.is_mine && (
          <PersonLine
            u={l.author}
            carrier={l.kind === "ROUTE"}
            label={t("l.author")}
            vehicle={l.vehicle}
          />
        )}
        {l.is_mine && l.from_address && (
          <div className="lc-car">
            <Pin size={18} />
            <span>
              {l.from_address} → {l.to_address}
              {l.recipient_name
                ? ` · ${l.recipient_name} ${l.recipient_phone}`
                : ""}
            </span>
          </div>
        )}
      </section>
      {!l.is_mine && <PrivateNote text={t("l.address_hidden")} />}
      {error && <div className="error-text">{error}</div>}

      {l.is_mine ? (
        <>
          <div className="sec-title">
            {t("l.offers")} <span className="n">{visibleOffers.length}</span>
          </div>
          {offers.loading && !offers.data && <Loading />}
          {visibleOffers.length === 0 && !offers.loading && (
            <EmptyState icon={<Inbox size={40} />} title={t("l.no_offers")} />
          )}
          <div className="cards">
            {visibleOffers.map((o) => (
              <OfferCard
                key={o.id}
                o={o}
                carrierSide={counterpartyIsCarrier}
                hint={hint}
                onChanged={onChanged}
              />
            ))}
          </div>
          {active && (
            <div className="actions" style={{ marginTop: 24 }}>
              <button
                className="btn block danger-ghost"
                onClick={cancelListing}
              >
                {t("l.cancel")}
              </button>
            </div>
          )}
        </>
      ) : (
        <>
          {visibleOffers.length > 0 && (
            <>
              <div className="sec-title">{t("l.your_offer")}</div>
              <div className="cards">
                {visibleOffers.map((o) => (
                  <OfferCard
                    key={o.id}
                    o={o}
                    carrierSide={counterpartyIsCarrier}
                    hint={hint}
                    onChanged={onChanged}
                  />
                ))}
              </div>
            </>
          )}
          {active && !myPending && (
            <OfferForm l={l} onSent={() => offers.reload()} />
          )}
          {!active && <p className="body-muted">{t("l.not_active")}</p>}
        </>
      )}
    </div>
  );
}
