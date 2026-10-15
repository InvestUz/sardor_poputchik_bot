import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { ArrowRight, Truck } from "../components/icons";
import {
  Chips,
  DateChips,
  EmptyState,
  ErrorBox,
  Field,
  Loading,
  PageHead,
  PhotoUpload,
  PriceHintBox,
  PrivateNote,
  RoutePick,
  usePriceHint,
} from "../components/ui";
import { localToIso, tashkentDate } from "../format";
import { MainAction, useClosingConfirmation } from "../hooks";
import { useApp, useLoad } from "../store";
import { haptic, storage } from "../tg";
import type { Listing, Vehicle } from "../types";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="card">
      <h2 className="card-title">{title}</h2>
      {children}
    </section>
  );
}

const SEAT_CHOICES = [1, 2, 3, 4];
/** whole_car requests reserve a regular sedan */
const WHOLE_CAR_SEATS = 4;

export default function CreateListing() {
  const { kind = "REQUEST" } = useParams();
  const { t, config, me, err } = useApp();
  const nav = useNavigate();
  const isRoute = kind === "ROUTE";
  const allowed = isRoute
    ? config!.enabled_categories.filter((c) => me?.carrier?.permissions.includes(c))
    : config!.enabled_categories;
  const draftKey = `draft_${kind}`;
  // Home "Posilka yuborish" tile preselects the parcel category
  const wanted = (useLocation().state as { category?: string } | null)?.category;
  const preset = wanted && allowed.includes(wanted) ? wanted : undefined;

  const vehicles = useLoad(() => (isRoute ? api<{ vehicles: Vehicle[] }>("/carrier").then((r) => r.vehicles) : Promise.resolve([])), [isRoute]);

  const initial = useMemo<Record<string, any>>(
    () => ({
      category: preset ?? allowed[0] ?? "",
      from_location_id: "",
      to_location_id: "",
      date: tashkentDate(1),
      time: "08:00",
      time_flexible: false,
      price: "",
      comment: "",
      passengers: 1,
      whole_car: false,
      luggage: "",
      stops_allowed: false,
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
      vehicle_id: "",
      seats: "",
      capacity_kg: "",
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [kind],
  );
  const [v, setV] = useState<Record<string, any>>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [restored, setRestored] = useState(false);
  const loaded = useRef(false);
  const dirty = JSON.stringify(v) !== JSON.stringify(initial);

  // restore draft (Telegram CloudStorage, else localStorage)
  useEffect(() => {
    loaded.current = false;
    let alive = true;
    storage.get(draftKey).then((raw) => {
      if (!alive) return;
      loaded.current = true;
      if (!raw) return;
      try {
        const d = JSON.parse(raw);
        if (!d || typeof d !== "object") return;
        const merged = { ...initial, ...d };
        if (!merged.date || merged.date < tashkentDate(0)) merged.date = initial.date;
        if (!allowed.includes(merged.category) || preset) merged.category = initial.category;
        if (JSON.stringify(merged) !== JSON.stringify(initial)) {
          setV(merged);
          setRestored(true);
        }
      } catch {
        /* broken draft */
      }
    });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftKey]);

  // autosave draft
  useEffect(() => {
    if (!loaded.current) return;
    const id = window.setTimeout(() => {
      if (dirty) storage.set(draftKey, JSON.stringify(v));
      else storage.remove(draftKey);
    }, 600);
    return () => window.clearTimeout(id);
  }, [v, dirty, draftKey]);

  useClosingConfirmation(dirty && !busy);

  const passenger = v.category === "PASSENGER";
  const hintSeats = !isRoute && passenger ? (v.whole_car ? WHOLE_CAR_SEATS : Number(v.passengers) || 1) : 1;
  const hint = usePriceHint(v.category, v.from_location_id, v.to_location_id, hintSeats);

  const set = (k: string) => (val: unknown) => setV((p) => ({ ...p, [k]: val }));
  const inp = (k: string, type = "text") => ({
    value: v[k],
    type,
    inputMode: type === "number" ? ("numeric" as const) : undefined,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => set(k)(e.target.value),
  });
  const chk = (k: string) => ({ checked: !!v[k], type: "checkbox", onChange: (e: React.ChangeEvent<HTMLInputElement>) => set(k)(e.target.checked) });

  async function clearDraft() {
    await storage.remove(draftKey);
    setV(initial);
    setRestored(false);
  }

  const num = (x: string | number) => (x === "" || x === null || x === undefined ? null : Number(x));

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const body = {
        kind,
        category: v.category,
        from_location_id: num(v.from_location_id),
        to_location_id: num(v.to_location_id),
        departure_at: localToIso(`${v.date}T${v.time || "08:00"}`),
        time_flexible: v.time_flexible,
        price: num(v.price),
        comment: v.comment,
        passengers: v.whole_car ? WHOLE_CAR_SEATS : num(v.passengers),
        whole_car: !isRoute && passenger ? !!v.whole_car : undefined,
        luggage: v.luggage,
        stops_allowed: v.stops_allowed,
        description: v.description,
        quantity: num(v.quantity),
        weight_kg: num(v.weight_kg),
        length_cm: num(v.length_cm),
        width_cm: num(v.width_cm),
        height_cm: num(v.height_cm),
        fragile: v.fragile,
        photo_ids: v.photo_ids,
        from_address: v.from_address,
        to_address: v.to_address,
        recipient_name: v.recipient_name,
        recipient_phone: v.recipient_phone,
        vehicle_id: num(v.vehicle_id),
        seats: num(v.seats),
        capacity_kg: num(v.capacity_kg),
      };
      const l = await api<Listing>("/listings", { body });
      await storage.remove(draftKey);
      haptic("success");
      nav(`/listings/${l.id}`, { replace: true });
    } catch (e) {
      haptic("error");
      setError(err(e));
      setBusy(false);
    }
  }

  const head = <PageHead title={t(`c.title_${kind}`)} />;

  if (isRoute && allowed.length === 0)
    return (
      <div>
        {head}
        <EmptyState icon={<Truck size={44} />} title={t("home.become_carrier")} text={t("c.no_permission")}>
          <button className="btn block" onClick={() => nav("/carrier")}>
            {t("home.become_carrier")} <ArrowRight size={18} />
          </button>
        </EmptyState>
      </div>
    );
  if (isRoute && vehicles.loading) return <Loading />;
  if (vehicles.error) return <ErrorBox error={vehicles.error} onRetry={vehicles.reload} />;
  if (isRoute && vehicles.data && vehicles.data.length === 0)
    return (
      <div>
        {head}
        <EmptyState icon={<Truck size={44} />} title={t("p.carrier_open")} text={t("c.no_vehicle")}>
          <button className="btn block" onClick={() => nav("/carrier")}>
            {t("p.carrier_open")} <ArrowRight size={18} />
          </button>
        </EmptyState>
      </div>
    );

  const seatValue: number | "whole" = v.whole_car ? "whole" : Number(v.passengers) || 1;

  return (
    <div>
      {head}
      {restored && (
        <div className="price-hint" role="status" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <span>{t("c.draft_restored")}</span>
          <button type="button" className="ulink sm" onClick={clearDraft}>
            {t("c.draft_clear")}
          </button>
        </div>
      )}

      <Section title={t("c.category")}>
        <Chips options={allowed.map((c) => ({ value: c, label: t(`cat.${c}`) }))} value={v.category} onChange={set("category")} label={t("c.category")} />
      </Section>

      <Section title={t("c.route")}>
        <RoutePick
          from={v.from_location_id}
          to={v.to_location_id}
          onFrom={set("from_location_id")}
          onTo={set("to_location_id")}
          onSwap={() => setV((p) => ({ ...p, from_location_id: p.to_location_id, to_location_id: p.from_location_id }))}
          placeholder={t("c.pick_city")}
        />
        <div className="field">
          <span className="label">{t("date")}</span>
          <DateChips value={v.date} onChange={set("date")} />
        </div>
        <Field label={t("c.time")}>
          <input type="time" value={v.time} onChange={(e) => set("time")(e.target.value)} />
        </Field>
        <label className="check" style={{ marginBottom: 0 }}>
          <input {...chk("time_flexible")} /> {t("c.flexible")}
        </label>
      </Section>

      <Section title={t(`cat.${v.category}`)}>
        {isRoute ? (
          <>
            <Field label={t("c.vehicle")}>
              <select value={v.vehicle_id} onChange={(e) => set("vehicle_id")(e.target.value)}>
                <option value="">—</option>
                {vehicles.data?.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.make_model} · {x.plate_number}
                  </option>
                ))}
              </select>
            </Field>
            {passenger ? (
              <>
                <Field label={t("l.seats")}>
                  <input {...inp("seats", "number")} min={1} />
                </Field>
                <Field label={t("l.luggage")} hint={t("optional")}>
                  <input {...inp("luggage")} placeholder={t("l.luggage_hint")} />
                </Field>
                <label className="check" style={{ marginBottom: 0 }}>
                  <input {...chk("stops_allowed")} /> {t("l.stops_allowed")}
                </label>
              </>
            ) : (
              <Field label={t("l.capacity_kg")}>
                <input {...inp("capacity_kg", "number")} min={1} />
              </Field>
            )}
          </>
        ) : (
          <>
            {passenger ? (
              <>
                <div className="field">
                  <span className="label">{t("l.passengers")}</span>
                  <Chips<number | "whole">
                    label={t("l.passengers")}
                    value={seatValue}
                    options={[
                      ...SEAT_CHOICES.map((n) => ({ value: n as number | "whole", label: String(n) })),
                      { value: "whole", label: t("l.whole_car"), divider: true },
                    ]}
                    onChange={(x) => setV((p) => (x === "whole" ? { ...p, whole_car: true } : { ...p, whole_car: false, passengers: x }))}
                  />
                </div>
                <Field label={t("l.luggage")}>
                  <input {...inp("luggage")} placeholder={t("l.luggage_hint")} />
                </Field>
                <label className="check">
                  <input {...chk("stops_allowed")} /> {t("l.stops_allowed")}
                </label>
              </>
            ) : (
              <>
                <Field label={t("l.description")}>
                  <textarea {...inp("description")} rows={2} />
                </Field>
                <div className="grid2">
                  <Field label={t("l.quantity")}>
                    <input {...inp("quantity", "number")} min={1} />
                  </Field>
                  {v.category !== "DOCUMENTS" && (
                    <Field label={t("l.weight")}>
                      <input {...inp("weight_kg", "number")} min={1} />
                    </Field>
                  )}
                </div>
                {v.category !== "DOCUMENTS" && (
                  <Field label={t("l.dims")}>
                    <div className="grid3">
                      <input {...inp("length_cm", "number")} placeholder={t("l.length")} />
                      <input {...inp("width_cm", "number")} placeholder={t("l.width")} />
                      <input {...inp("height_cm", "number")} placeholder={t("l.height")} />
                    </div>
                  </Field>
                )}
                <label className="check">
                  <input {...chk("fragile")} /> {t("l.fragile")}
                </label>
                <Field label={t("l.photos")} hint={v.category !== "DOCUMENTS" ? t("l.photos_required") : t("optional")}>
                  <PhotoUpload value={v.photo_ids} onChange={set("photo_ids")} purpose="LISTING_PHOTO" />
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
            <Field label={t("l.from_address")}>
              <input {...inp("from_address")} />
            </Field>
            <Field label={t("l.to_address")}>
              <input {...inp("to_address")} />
            </Field>
            <PrivateNote text={t("l.address_hidden")} />
          </>
        )}
      </Section>

      <Section title={t("price")}>
        <Field label={isRoute ? (passenger ? t("l.price_per_seat") : t("l.price_start")) : t("l.price_offer")}>
          <input {...inp("price", "number")} placeholder={t("som")} />
          <PriceHintBox hint={hint} value={v.price} onUse={(x) => set("price")(String(x))} />
        </Field>
        <Field label={t("comment")} hint={t("optional")}>
          <textarea {...inp("comment")} rows={2} />
        </Field>
      </Section>
      {error && <div className="error-text">{error}</div>}
      <MainAction text={t("c.publish")} onClick={submit} progress={busy} />
    </div>
  );
}
