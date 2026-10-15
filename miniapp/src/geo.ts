// City search normalisation, nearest-city lookup and browser geolocation helpers.
import type { Loc } from "./types";

const CYR: Record<string, string> = {
  а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "yo", ж: "j", з: "z", и: "i", й: "y", к: "k", л: "l",
  м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t", у: "u", ф: "f", х: "x", ц: "ts", ч: "ch", ш: "sh",
  щ: "sh", ъ: "", ы: "i", ь: "", э: "e", ю: "yu", я: "ya", ў: "o", қ: "q", ғ: "g", ҳ: "h",
};

/**
 * Loose search key: lower case, Cyrillic transliterated to Latin, Uzbek apostrophe variants dropped
 * (o' / oʻ / o‘ / o` / o all equal), and q/k, x/h/kh folded so "Самарканд", "samarq" and "bukh" still match.
 */
export function searchKey(s: string): string {
  let out = "";
  for (const ch of s.toLowerCase()) out += CYR[ch] ?? ch;
  return out
    .replace(/['`ʻʼ‘’´]/g, "")
    .replace(/kh/g, "h")
    .replace(/x/g, "h")
    .replace(/q/g, "k")
    .replace(/\s+/g, " ")
    .trim();
}

export function locHaystack(l: Loc): string {
  return searchKey([l.name_uz, l.name_ru, l.region_uz, l.region_ru].join(" | "));
}

function haversineKm(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const r = (d: number) => (d * Math.PI) / 180;
  const dLat = r(bLat - aLat);
  const dLon = r(bLon - aLon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(r(aLat)) * Math.cos(r(bLat)) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

export const hasCoords = (l: Loc) => typeof l.lat === "number" && typeof l.lon === "number";

export function nearestLoc(locs: Loc[], lat: number, lon: number): Loc | null {
  let best: Loc | null = null;
  let bestD = Infinity;
  for (const l of locs) {
    if (!hasCoords(l)) continue;
    const d = haversineKm(lat, lon, l.lat as number, l.lon as number);
    if (d < bestD) {
      bestD = d;
      best = l;
    }
  }
  return best;
}

export type GeoError = "denied" | "unavailable" | "timeout";

export const geoSupported = () => typeof navigator !== "undefined" && "geolocation" in navigator;

export function getPosition(): Promise<{ lat: number; lon: number }> {
  return new Promise((resolve, reject) => {
    if (!geoSupported()) return reject("unavailable" as GeoError);
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lon: p.coords.longitude }),
      (e) => reject((e.code === 1 ? "denied" : e.code === 3 ? "timeout" : "unavailable") as GeoError),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  });
}

const MAP_RE = /https:\/\/maps\.google\.com\/\?q=[-\d.]+,[-\d.]+/g;

export function geoText(lat: number, lon: number): string {
  const a = lat.toFixed(6);
  const b = lon.toFixed(6);
  return `${a}, ${b} · https://maps.google.com/?q=${a},${b}`;
}

/** Appends the coordinates + map link to an address, replacing an earlier inserted one. */
export function withGeo(address: string, lat: number, lon: number): string {
  const base = address.replace(/\s*(?:·\s*)?[-\d.]+,\s*[-\d.]+\s*·\s*https:\/\/maps\.google\.com\/\?q=[-\d.]+,[-\d.]+/g, "").trim();
  return base ? `${base} · ${geoText(lat, lon)}` : geoText(lat, lon);
}

/** Splits text into plain parts and map URLs. */
export function splitMapLinks(text: string): { text?: string; url?: string }[] {
  const out: { text?: string; url?: string }[] = [];
  let last = 0;
  for (const m of text.matchAll(MAP_RE)) {
    const i = m.index ?? 0;
    if (i > last) out.push({ text: text.slice(last, i) });
    out.push({ url: m[0] });
    last = i + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}

export const mapSearchUrl = (q: string) => `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`;
