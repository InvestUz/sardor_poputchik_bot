import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Bell, Check, Close, Contrast, FileText, Globe, Help, Truck } from "../components/icons";
import { Avatar, Badge, PageHead, Rating, RowLink, Sheet } from "../components/ui";
import { locName } from "../format";
import type { Lang } from "../i18n";
import { useApp, useLoad } from "../store";
import { openTelegramUser } from "../tg";

type Sub = { id: number; kind: string; category: string; from_location_id: number; to_location_id: number };

const LANGS: Lang[] = ["uz", "ru"];

export default function Profile() {
  const { me, t, lang, setLang, locations, config, theme, toggleTheme } = useApp();
  const nav = useNavigate();
  const subs = useLoad(() => api<Sub[]>("/subscriptions"), []);
  const [sheet, setSheet] = useState<null | "subs" | "lang">(null);
  const loc = (id: number) => locName(locations.find((l) => l.id === id), lang);
  const support = config?.support_contact ?? "";

  async function removeSub(id: number) {
    await api(`/subscriptions/${id}`, { method: "DELETE" });
    subs.reload();
  }

  return (
    <div>
      <PageHead title={t("p.title")} back={false} />
      <div className="profile-hero">
        <Avatar name={me?.first_name ?? ""} size="lg" />
        <h2>
          {me?.first_name} {me?.last_name ?? ""}
        </h2>
        <div className="small muted">{me?.phone}</div>
        <Rating rating={me?.rating ?? null} count={me?.rating_count ?? 0} />
      </div>

      <div className="rows">
        <RowLink
          icon={<Truck size={20} />}
          title={t("p.carrier_open")}
          right={<Badge status={me?.carrier?.status ?? "DRAFT"} prefix="cs" />}
          onClick={() => nav("/carrier")}
        />
        <RowLink
          icon={<Bell size={20} />}
          title={t("p.subscriptions")}
          sub={subs.data ? (subs.data.length ? String(subs.data.length) : t("p.none")) : undefined}
          onClick={() => setSheet("subs")}
        />
        <RowLink icon={<Globe size={20} />} title={t("p.language")} sub={t(`p.lang_${lang}`)} onClick={() => setSheet("lang")} />
        <RowLink
          icon={<Contrast size={20} />}
          title={t("theme")}
          sub={t(theme === "dark" ? "p.theme_dark" : "p.theme_light")}
          onClick={toggleTheme}
          right={<span className={`switch ${theme === "dark" ? "on" : ""}`} aria-hidden="true" />}
        />
        <RowLink
          icon={<Help size={20} />}
          title={t("p.support")}
          sub={support}
          onClick={support.startsWith("@") ? () => openTelegramUser(support.slice(1)) : undefined}
          right={support.startsWith("@") ? undefined : <span />}
        />
        <RowLink icon={<FileText size={20} />} title={t("p.terms")} href={`/terms?lang=${lang}`} />
      </div>

      {sheet === "subs" && (
        <Sheet title={t("p.subscriptions")} onClose={() => setSheet(null)}>
          {subs.data?.length === 0 && <p className="body-muted">{t("p.no_subscriptions")}</p>}
          <div className="rows">
            {subs.data?.map((s) => (
              <div key={s.id} className="info-row">
                <span className="body">
                  <span className="s">
                    {t(`cat.${s.category}`)} · {t(`kind.${s.kind}`)}
                  </span>
                  <span className="t">
                    {loc(s.from_location_id)} → {loc(s.to_location_id)}
                  </span>
                </span>
                <button className="icon-btn" onClick={() => removeSub(s.id)} aria-label={t("delete")}>
                  <Close size={18} />
                </button>
              </div>
            ))}
          </div>
        </Sheet>
      )}

      {sheet === "lang" && (
        <Sheet title={t("p.language")} onClose={() => setSheet(null)}>
          <div className="rows" role="radiogroup" aria-label={t("p.language")}>
            {LANGS.map((l) => (
              <button
                key={l}
                type="button"
                role="radio"
                aria-checked={lang === l}
                className={`row-link choice ${lang === l ? "on" : ""}`}
                onClick={async () => {
                  await setLang(l);
                  setSheet(null);
                }}
              >
                <span className="body">
                  <span className="t">{t(`p.lang_${l}`)}</span>
                </span>
                <span className="go">{lang === l ? <Check size={20} strokeWidth={2.4} /> : null}</span>
              </button>
            ))}
          </div>
        </Sheet>
      )}
    </div>
  );
}
