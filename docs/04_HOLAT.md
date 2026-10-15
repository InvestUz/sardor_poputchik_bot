# Loyiha holati — 2026-10-15

## Tayyor (lokal sinovdan o'tgan)
| Qism | Holat | Dalil |
|------|-------|-------|
| Biznes-logika: e'lon, taklif/qarshi narx, buyurtma holatlari, bekor qilish, shikoyat, baho, obuna | ✅ | 23 avtomatik test |
| Fon vazifalar: muddatlar, tasdiq taymauti, avto-yakun, eslatma | ✅ | testlar |
| Mini App (uz/ru, och/qorong'i mavzu, yangi dizayn) | ✅ | brauzerda 375px da ko'rildi |
| Bot: ro'yxatdan o'tish, menyu, tez tugmalar | ✅ | soxta Telegram sessiyasi bilan testlar |
| Admin-panel: tekshiruv, foydalanuvchilar, e'lonlar, buyurtmalar, shikoyatlar, sharhlar, sozlamalar, audit, statistika | ✅ | testlar + brauzer |
| Maxfiylik: manzil/telefon/raqam faqat tasdiqdan keyin | ✅ | API testi + brauzer |
| C variant dizayni: ishonch belgilari, narx maslahati, faollik hisoblagichi, posilka kodi, bosqichlar, Telegram tugmalari | ✅ | 33 test + build + QA hisoboti (2026-10-15) |
| Deploy fayllari: Docker, Caddy (HTTPS), backup/restore, CI | ✅ yozilgan | ⚠️ ishga tushirib ko'rilmagan |

## Hali tekshirilmagan / qilinmagan
| Nima | Nega | Kim |
|------|------|-----|
| Haqiqiy Telegram bot (token bilan) | Token yo'q | Siz → devops-release |
| PostgreSQL'da ishlash | Lokal Docker/PostgreSQL yo'q; testlar SQLite'da | devops-release + qa-verifier |
| Docker build va serverga joylash | Server yo'q | devops-release |
| Haqiqiy telefonlarda Mini App (Android/iOS, Telegram ichida) | Bot yo'q | qa-verifier |
| Oferta va maxfiylik siyosati yakuniy matni | Yurist kerak | Siz |
| Dizaynni raqobatchilar asosida takomillashtirish | Tadqiqot jarayonda | design-researcher → miniapp-engineer |

## Agentlar (`.claude/agents/`)
| Agent | Yo'nalishi | O'zgartiradi |
|-------|-----------|--------------|
| `backend-engineer` | Biznes-qoidalar, API, bot, admin, migratsiyalar, testlar | `backend/` |
| `miniapp-engineer` | Mini App ekranlari, dizayn tizimi, i18n | `miniapp/src` |
| `qa-verifier` | Mustaqil tekshiruv, e2e oqimlar, maxfiylik va ruxsatlar | hech narsa (faqat hisobot) |
| `devops-release` | Server, Docker, HTTPS, backup, CI, go-live | `infra/`, `Dockerfile`, `.github/` |
| `design-researcher` | Raqobatchilar UX tahlili, tavsiyalar | `docs/design/` |

Ish tartibi: **design-researcher → (siz tasdiqlaysiz) → miniapp-engineer / backend-engineer → qa-verifier**. Bir faylga ikki agent parallel yozmaydi.

## Keyingi qadamlar
1. Dizayn tavsiyalaridan birini tanlash (`docs/design/`).
2. Bot tokeni + O'zbekistondagi server + domen → devops-release bilan joylash.
3. qa-verifier: PostgreSQL va haqiqiy Telegram'da to'liq sinov.
4. 20–50 tashuvchini jalb qilish → pilot.
