# Yo'lchi — loyiha qoidalari (Claude va agentlar uchun)

Telegram bot + Mini App + admin-panel: O'zbekistonda shaharlararo yo'lovchi va posilka tashish. Hozir **pilot** bosqichi.
Foydalanuvchi bilan o'zbek tilida (lotin) gaplashiladi.

## Qabul qilingan qarorlar (qayta muhokama qilinmaydi)
- Bot + Telegram Mini App gibridi; admin — alohida web-panel (`/admin`).
- Pilot **to'lovsiz**: komissiya faqat hisoblanadi (`estimated_commission`), yechilmaydi. Payme/Click — R2 bosqichi.
- Tillar: o'zbek (lotin) + rus. Ingliz — keyinroq.
- Toifalar pilotda: PASSENGER, PARCEL (qolganlari kodda bor, sozlamada o'chirilgan).
- Stek: Python 3.12, FastAPI, aiogram 3, SQLAlchemy 2 + Alembic, PostgreSQL 16 (prod) / SQLite (test, dev); React 18 + TS + Vite.
- Yuklama 100–500 → bitta server, bitta uvicorn worker (fon vazifalar va notifier shu jarayonda).
- Prod server **O'zbekistonda** (shaxsiy ma'lumotlar qonuni).

## Tuzilma va egalik (qaysi agent qayerda ishlaydi)
| Papka | Egasi (agent) |
|-------|---------------|
| `backend/app/services`, `api`, `bot`, `admin`, `i18n`, `migrations`, `backend/tests` | `backend-engineer` |
| `miniapp/src` | `miniapp-engineer` |
| `Dockerfile`, `infra/`, `.github/`, `docs/03_ISHGA_TUSHIRISH.md` | `devops-release` |
| `docs/design/` (tadqiqot va tavsiyalar) | `design-researcher` |
| Hech narsani o'zgartirmaydi, faqat tekshiradi va hisobot beradi | `qa-verifier` |

Bitta vazifa — bitta egasi. Ikki agent bir faylga parallel yozmaydi. Chegaradan chiqish kerak bo'lsa (masalan, Mini App uchun yangi API maydoni) — avval backend-engineer API'ni qo'shadi, keyin miniapp-engineer ishlatadi.

## Asosiy buyruqlar
```bash
# backend (backend/ ichida)
.venv/Scripts/python -m pytest -q                       # barcha testlar (23+), har o'zgarishdan keyin
.venv/Scripts/python run_dev.py                         # lokal server :8000 (migratsiya + reload)
.venv/Scripts/alembic revision --autogenerate -m "..."   # model o'zgarsa
.venv/Scripts/python -m app.cli dev-user 111 Aziz       # DEBUG: test foydalanuvchi → /app/?dev=111
# miniapp (miniapp/ ichida)
npm run build                                           # tsc + vite; backend /app/ dan beradi
```

## Kod qoidalari
- Biznes-qoidalar faqat `services/` da; API/bot/admin — yupqa qatlam. Holat o'tishlari faqat `services/orders.py` dagi `TRANSITIONS` orqali.
- Xatolar: `DomainError("kod")`; kod `err.<kod>` sifatida `backend/app/i18n/*.json` va `miniapp/src/i18n.ts` ikkalasida tarjima qilinadi.
- Bildirishnomalar: `notify.queue(...)` (commit'dan keyin yuboriladi). Yangi kalit → uz.json + ru.json (`tests/test_i18n.py` tekshiradi).
- Maxfiylik: aniq manzil, telefon, davlat raqami faqat `serializers.py` orqali va faqat tasdiqlangan buyurtmada.
- Pul — butun son (so'm), vaqt — UTC saqlanadi, `Asia/Tashkent` (UTC+5) da ko'rsatiladi.
- Sozlanadigan biznes-parametrlar kodga yozilmaydi → `services/settings.py` DEFAULTS + admin `/admin/settings`.
- Model o'zgarsa — Alembic migratsiya majburiy.

## Dizayn tizimi (Mini App)
- Joriy uslub: **D — yashil** ([docs/design/2026-10-15-D-yashil-uslub.md](docs/design/2026-10-15-D-yashil-uslub.md)), Behance "Car Booking | Ride Sharing" asosida (faqat uslub; muallif illyustratsiyalari ishlatilmaydi). Avvalgi editorial uslub (Unbounded, kontur sarlavhalar) bekor qilingan.
- Tokenlar `miniapp/src/styles.css` `:root[data-theme]` da; rangni to'g'ridan-to'g'ri yozmang. Yashil `#46C96B` — faqat tugma foni va katta ikonkalar; kichik yashil matn uchun to'qroq token.
- Shrift: Open Sans (kirill va o'zbek lotinini qo'llaydi).
- Ikonkalar faqat `components/icons.tsx` dan (1.6 stroke, 24px). **Emoji ishlatilmaydi.**
- Tayyor komponentlar: `components/ui.tsx` (Field, Badge, Price, ListingCard, RowLink, PageHead, PrivateNote, ...).
- Har UI o'zgarishi 375px kenglikda, och va qorong'i mavzuda tekshiriladi.
