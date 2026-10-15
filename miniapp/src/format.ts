import type { Loc } from "./types";

const TZ = "Asia/Tashkent";

export function money(v: number | null | undefined): string {
  if (v === null || v === undefined) return "";
  return v.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

const WEEKDAYS: Record<string, string[]> = {
  uz: ["Yak", "Dush", "Sesh", "Chor", "Pay", "Jum", "Shan"],
  ru: ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"],
};

/** "Pay, 15.10 08:00" in Tashkent time */
export function dateTime(iso: string, lang: string): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", {
      timeZone: TZ,
      weekday: "short",
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(new Date(iso))
      .map((p) => [p.type, p.value]),
  );
  const wd = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(parts.weekday);
  return `${(WEEKDAYS[lang] ?? WEEKDAYS.uz)[wd]}, ${parts.day}.${parts.month} ${parts.hour}:${parts.minute}`;
}

export function locName(l: Loc | null | undefined, lang: string): string {
  if (!l) return "";
  return lang === "ru" ? l.name_ru : l.name_uz;
}

/** "2026-10-15T08:30" (datetime-local, Tashkent time) -> ISO string with +05:00 offset */
export function localToIso(v: string): string {
  return `${v}:00+05:00`;
}

/** default departure: tomorrow 08:00 Tashkent time, in datetime-local format */
export function defaultDeparture(): string {
  const now = new Date(Date.now() + 5 * 3600 * 1000 + 24 * 3600 * 1000);
  return `${now.toISOString().slice(0, 10)}T08:00`;
}

export function todayTashkent(): string {
  return new Date(Date.now() + 5 * 3600 * 1000).toISOString().slice(0, 10);
}

/** "08:30" in Tashkent time */
export function timeOnly(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso));
}

/** Tashkent calendar date (YYYY-MM-DD) `days` from today */
export function tashkentDate(days = 0): string {
  return new Date(Date.now() + 5 * 3600 * 1000 + days * 24 * 3600 * 1000).toISOString().slice(0, 10);
}

/** "15.10.2026" in Tashkent time */
export function dateOnly(iso: string): string {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", { timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric" })
      .formatToParts(new Date(iso))
      .map((x) => [x.type, x.value]),
  );
  return `${p.day}.${p.month}.${p.year}`;
}
