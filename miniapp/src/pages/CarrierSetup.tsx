import { useState } from "react";
import { api, uploadFile } from "../api";
import { Car, Check, Close, FileText, Plus, Truck } from "../components/icons";
import { AuthImg, Badge, ErrorBox, Field, IconCircle, Loading, PageHead } from "../components/ui";
import { useApp, useLoad } from "../store";
import { haptic } from "../tg";
import type { Vehicle } from "../types";

type Carrier = {
  status: string;
  full_name: string | null;
  admin_comment: string | null;
  permissions: string[];
  vehicles: Vehicle[];
  documents: { id: number; kind: string; file_id: number }[];
};

const EDITABLE = ["DRAFT", "REJECTED", "RESUBMIT", "REVOKED"];
const VEHICLE_LABELS = {
  make_model: "cr.make_model",
  plate_number: "cr.plate",
  color: "cr.color",
  seats: "cr.seats",
  max_weight_kg: "cr.max_weight",
} as const;

export default function CarrierSetup() {
  const { t, err, config, refreshMe } = useApp();
  const { data: c, error, loading, reload } = useLoad(() => api<Carrier>("/carrier"), []);
  const [vehicle, setVehicle] = useState<Record<string, string> | null>(null);
  const [fullName, setFullName] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (loading && !c) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!c) return null;
  const editable = EDITABLE.includes(c.status);

  async function act(fn: () => Promise<unknown>, ok?: string) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      haptic("success");
      if (ok) setMsg(ok);
      await reload();
    } catch (e) {
      haptic("error");
      setMsg(err(e));
    } finally {
      setBusy(false);
    }
  }

  const required = config!.required_documents;
  const docKinds = [...required, ...config!.document_kinds.filter((k) => !required.includes(k) && k !== "OTHER")];

  return (
    <div>
      <PageHead title={t("cr.title")} />
      <div className="info-row status-row">
        <IconCircle>
          <Truck size={20} />
        </IconCircle>
        <span className="body">
          <span className="t">{t("p.carrier")}</span>
          {c.permissions.length > 0 && <span className="s">{c.permissions.map((p) => t(`cat.${p}`)).join(" · ")}</span>}
        </span>
        <Badge status={c.status} prefix="cs" />
      </div>
      {c.status === "DRAFT" && <p className="body-muted">{t("cr.intro")}</p>}
      {c.admin_comment && (
        <div className="private-note">
          <span>
            <span className="small">{t("cr.comment")}</span>
            <br />
            <b>{c.admin_comment}</b>
          </span>
        </div>
      )}
      {c.status === "PENDING" && <p className="body-muted">{t("cr.locked")}</p>}

      <div className="sec-title">{t("cr.vehicles")}</div>
      <div className="rows">
        {c.vehicles.map((v) => (
          <div key={v.id} className="info-row">
            <IconCircle>
              <Car size={20} />
            </IconCircle>
            <span className="body">
              <span className="t">{v.make_model}</span>
              <span className="s">
                {v.plate_number} · {t(`vt.${v.vehicle_type}`)} · {v.seats} / {v.max_weight_kg} {t("unit.kg")}
              </span>
            </span>
            <button className="icon-btn" onClick={() => act(() => api(`/carrier/vehicles/${v.id}`, { method: "DELETE" }))} aria-label={t("delete")}>
              <Close size={18} />
            </button>
          </div>
        ))}
      </div>
      {vehicle ? (
        <div className="card">
          <Field label={t("cr.vehicle_type")}>
            <select value={vehicle.vehicle_type} onChange={(e) => setVehicle({ ...vehicle, vehicle_type: e.target.value })}>
              {config!.vehicle_types.map((v) => (
                <option key={v} value={v}>
                  {t(`vt.${v}`)}
                </option>
              ))}
            </select>
          </Field>
          {(Object.keys(VEHICLE_LABELS) as (keyof typeof VEHICLE_LABELS)[]).map((k) => (
            <Field key={k} label={t(VEHICLE_LABELS[k])}>
              <input
                type={k === "seats" || k === "max_weight_kg" ? "number" : "text"}
                value={vehicle[k]}
                onChange={(e) => setVehicle({ ...vehicle, [k]: e.target.value })}
              />
            </Field>
          ))}
          <div className="actions">
            <button
              className="btn block"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await api("/carrier/vehicles", {
                    body: { ...vehicle, seats: Number(vehicle.seats || 0), max_weight_kg: Number(vehicle.max_weight_kg || 0) },
                  });
                  setVehicle(null);
                })
              }
            >
              {t("save")}
            </button>
            <button className="btn block ghost" onClick={() => setVehicle(null)}>
              {t("cancel")}
            </button>
          </div>
        </div>
      ) : (
        <button
          className="btn ghost block"
          style={{ marginTop: 10 }}
          onClick={() => setVehicle({ vehicle_type: "SEDAN", make_model: "", plate_number: "", color: "", seats: "4", max_weight_kg: "100" })}
        >
          <Plus size={20} /> {t("cr.add_vehicle")}
        </button>
      )}

      <div className="sec-title">{t("cr.documents")}</div>
      <div className="rows">
        {docKinds.map((kind) => {
          const docs = c.documents.filter((d) => d.kind === kind);
          const isRequired = required.includes(kind);
          return (
            <div key={kind} className="doc-row">
              <div className="info-row">
                <IconCircle>{docs.length > 0 ? <Check size={18} strokeWidth={2.4} /> : <FileText size={20} />}</IconCircle>
                <span className="body">
                  <span className="t">{t(`doc.${kind}`)}</span>
                  <span className="s">{docs.length > 0 ? t("cr.uploaded") : isRequired ? t("cr.required") : t("optional")}</span>
                </span>
              </div>
              <div className="photos">
                {docs.map((d) => (
                  <div key={d.id} className="photo-edit">
                    <AuthImg id={d.file_id} />
                    {editable && (
                      <button className="x" onClick={() => act(() => api(`/carrier/documents/${d.id}`, { method: "DELETE" }))} aria-label={t("delete")}>
                        <Close size={14} />
                      </button>
                    )}
                  </div>
                ))}
                {editable && (
                  <label className={`thumb add ${busy ? "busy" : ""}`}>
                    <Plus size={24} />
                    <input
                      type="file"
                      accept="image/*,application/pdf"
                      hidden
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f)
                          act(async () => {
                            const fileId = await uploadFile(f, "DOCUMENT");
                            await api("/carrier/documents", { body: { kind, file_id: fileId } });
                          });
                      }}
                    />
                  </label>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {editable && (
        <>
          <div className="sec-title">{t("cr.submit")}</div>
          <Field label={t("cr.full_name")}>
            <input value={fullName ?? c.full_name ?? ""} onChange={(e) => setFullName(e.target.value)} />
          </Field>
          <button
            className="btn block"
            disabled={busy}
            onClick={() =>
              act(async () => {
                await api("/carrier/submit", { body: { full_name: fullName ?? c.full_name ?? "" } });
                await refreshMe();
              }, t("cr.submitted"))
            }
          >
            {t("cr.submit")}
          </button>
        </>
      )}
      {msg && <div className="private-note">{msg}</div>}
    </div>
  );
}
