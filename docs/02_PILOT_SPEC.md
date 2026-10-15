# Pilot spetsifikatsiyasi (to'lovsiz versiya)

> Asos: [01_METODOLOGIYA_VA_PROD_REJA.md](01_METODOLOGIYA_VA_PROD_REJA.md), qarorlar D1–D7.
> Maqsad: platformani haqiqiy mijoz va tashuvchilarda **to'lov tizimisiz** sinash — talab bormi, bitimlar tuziladimi, jarayon tushunarli ekanmi.
> Sana: 2026-10-14 · Holat: **taklif, tasdiq kutilmoqda** (❓ belgilari).

---

## 1. Pilot tarkibi

### Kiradi
| Modul | Pilotdagi hajm |
|-------|----------------|
| Ro'yxatdan o'tish | Til (uz/ru) → Telegram kontakt (telefon) → ism → oferta va maxfiylik siyosatiga rozilik |
| Rollar | Mijoz, Tashuvchi (verifikatsiyadan keyin), Admin |
| Kategoriyalar | ❓ **Yo'lovchi + Posilka** (tavsiya). Qolgan 3 tasi admin'da o'chirilgan holda — kod tayyor bo'lishi shart emas |
| Tashuvchi verifikatsiyasi | Hujjat va transport fotosini yuklash → admin tasdiqlaydi/rad etadi/qayta so'raydi → kategoriya bo'yicha ruxsat |
| E'lonlar | Mijoz so'rovi va tashuvchi marshruti; shahar A → shahar B, sana/vaqt, narx, sig'im (o'rindiq yoki kg) |
| Qidiruv | Yo'nalish + sana + kategoriya; filtrlar: narx, reyting, transport turi; saralash — eng yaqin jo'nash, keyin yangilari |
| Takliflar | Taklif, qarshi narx, muddat, tanlash, qolganlari avtomatik yopiladi |
| Bitim | Tasdiqlash → aniq manzil va telefonlar ochiladi → yo'lda → yakunlandi; bekor qilish (sabab yoziladi) |
| Sharhlar | Ikki tomonlama, 1–5, bitta buyurtmaga bitta |
| Bildirishnomalar | Yangi taklif, tanlandingiz, tasdiqlandi, jo'nashga 2 soat qoldi, bekor qilindi, verifikatsiya natijasi, mos yangi e'lon |
| Admin-panel | Foydalanuvchilar, verifikatsiya, e'lonlar/buyurtmalar, bloklash, shikoyatlar, sozlamalar, oddiy statistika, audit log |
| Shikoyat | Buyurtmadan "Muammo bor" → admin ko'rib chiqadi va izoh bilan yopadi (moliyaviy oqibatsiz) |

### Kirmaydi (pilotdan keyin)
Payme/Click, hamyon, komissiya yechish, jarimalar (pul), qaytarishlar, sverka · Hujjat/Mebel/Katta yuk kategoriyalari · Yetkazib berish kodi + SMS · Oraliq nuqtalar va marshrutdan og'ish (OSRM) · Ingliz tili · Bot ichidagi chat.

> Komissiya pilotda **yechilmaydi**, lekin har bir yakunlangan buyurtma uchun `estimated_commission` hisoblanib yoziladi — keyingi biznes-qaror uchun ma'lumot.

---

## 2. Asosiy foydalanuvchi oqimlari

**Mijoz (yo'lovchi):** `/start` → til → kontakt → "Yo'l topish" (Mini App) → yo'nalish + sana → tashuvchi marshrutlari ro'yxati → "Joy band qilish" (narx taklifi bilan) **yoki** "So'rov joylash" → takliflar keladi (botga xabar) → bittasini tanlash → tashuvchi tasdiqlaydi → telefon/manzil ochiladi → safar → "Yetib keldim" → baho.

**Mijoz (posilka):** xuddi shunday, anketada: tavsif, foto (majburiy), soni, og'irligi, o'lchamlari, mo'rtligi, qabul qiluvchi ismi va telefoni.

**Tashuvchi:** "Tashuvchi bo'lish" → hujjatlar + transport → kutish → tasdiqlandi (botga xabar) → "Marshrut joylash" yoki mos so'rovlarga taklif yuborish → mijoz tanlasa — tasdiqlash → "Yo'lga chiqdim" → "Yetkazdim" → baho.

**Admin:** yangi verifikatsiyalar navbati → hujjatlarni ko'rish → tasdiqlash (kategoriyalar bilan) / rad etish (sabab) / qayta yuklash so'rovi.

---

## 3. Holat mashinalari (pilot)

**Listing** (e'lon):
```
DRAFT → PUBLISHED → CLOSED       (sig'im to'ldi yoki mijoz tashuvchini tanladi)
            │──────→ EXPIRED      (jo'nash vaqti o'tdi — fon vazifasi)
            └──────→ CANCELLED    (muallif bekor qildi)
```

**Offer** (taklif):
```
PENDING ─→ ACCEPTED
   ├─────→ COUNTERED (yangi Offer parent_offer_id bilan yaratiladi)
   ├─────→ REJECTED | WITHDRAWN | EXPIRED
   └─────→ AUTO_CLOSED (boshqa taklif qabul qilindi / e'lon yopildi)
```

**Order** (bitim):
```
AWAITING_CONFIRMATION → CONFIRMED → IN_PROGRESS → AWAITING_COMPLETION → COMPLETED
        │                   │             │                 │
        └──→ CANCELLED ←────┘             └──→ DISPUTED ←───┘ → (admin) COMPLETED | CANCELLED
```
- `AWAITING_CONFIRMATION`: tanlangan tomon ❓ 30 daqiqa ichida tasdiqlamasa → CANCELLED, sig'im bo'shatiladi.
- `AWAITING_COMPLETION`: ❓ 12 soat ichida e'tiroz bo'lmasa → avtomatik COMPLETED.
- Har bir o'tish: kim, qachon, sabab → `order_status_history`.

---

## 4. Ma'lumotlar modeli (pilot)

```
users ─┬─< user_roles
       ├── carrier_profiles ──< carrier_permissions (category)
       ├──< vehicles
       ├──< verification_requests ──< documents
       ├──< listings ──< listing_items (posilka birliklari, foto)
       │       └──< offers ──(parent_offer_id)
       ├──< orders (listing_id, offer_id, client_id, carrier_id, price, seats/weight, status)
       │       ├──< order_status_history
       │       ├──< cancellations
       │       ├──< complaints
       │       └──< reviews  UNIQUE(order_id, author_id)
       ├──< notifications
       └──< subscriptions (yo'nalish + kategoriya — mos e'lon xabari uchun)

locations (viloyat/tuman/shahar, PostGIS nuqta)
settings (kalit-qiymat, o'zgarish tarixi bilan) · translations (uz, ru)
admin_users ──< audit_log (faqat INSERT)
```

Muhim cheklovlar:
- `listings.reserved_seats <= listings.total_seats` (CHECK) + band qilishda `SELECT … FOR UPDATE`.
- Narx — `BIGINT` (so'm). Vaqt — UTC, ko'rsatish `Asia/Tashkent`.
- Aniq manzil va telefon API javobida faqat tomon `CONFIRMED`+ buyurtmada ishtirokchi bo'lsa qaytariladi.

---

## 5. Texnik tarkib

| Qism | Tanlov |
|------|--------|
| Bot | aiogram 3, webhook |
| API | FastAPI, SQLAlchemy 2, Alembic, Pydantic |
| Mini App | React + Vite + TypeScript, Telegram WebApp SDK; auth — `initData` HMAC |
| Admin-panel | SQLAdmin (FastAPI ichida, tez) — pilot uchun yetarli; keyinchalik React |
| Fon vazifalar | Taskiq + Redis (muddat tugashi, eslatmalar, bildirishnomalar navbati) |
| DB | PostgreSQL 16 + PostGIS |
| Fayllar | MinIO (private bucket, signed URL) |
| Infra | 1 ta server O'zbekistonda (4 vCPU / 8 GB / 100+ GB SSD), Docker Compose, Caddy/Nginx + TLS |
| Kuzatuv | Sentry, uptime-check, xatolar Telegram admin-guruhiga |
| Backup | Kunlik `pg_dump` + MinIO sinxroni boshqa joyga; tiklash bir marta sinab ko'rilgan |

Repo tuzilmasi (monorepo):
```
sardor_bot/
  backend/      # FastAPI + bot + fon vazifalar + admin (bitta Python paket)
  miniapp/      # React Mini App
  infra/        # docker-compose, Caddyfile, backup skriptlari
  docs/
```

---

## 6. Taxminiy grafik (1–2 dasturchi + Claude)

| Hafta | Ish |
|-------|-----|
| 1–2 | Repo, docker-compose, CI; DB sxema + migratsiyalar; ro'yxatdan o'tish, i18n (uz/ru), locations spravochnigi; Mini App karkasi + auth |
| 3–4 | Tashuvchi verifikatsiyasi + admin-panel (SQLAdmin) |
| 5–7 | E'lonlar (yo'lovchi, posilka), qidiruv, filtrlar, obunalar |
| 8–10 | Takliflar, bitim holatlari, manzil ochilishi, bekor qilish, sharhlar, shikoyatlar, bildirishnomalar |
| 11 | Staging'da to'liq test, konkurentlik testlari, xatolarni tuzatish |
| 12 | Prod server, backup, monitoring, oferta/maxfiylik matnlari → **pilot start** |

---

## 7. Pilotni boshlashdan oldin (to'lovsiz versiya uchun nazorat ro'yxati)

- [ ] Bot nomi, username, logotip, qisqa tavsif (uz/ru)
- [ ] Oferta + maxfiylik siyosati (uz/ru) — yurist ko'rgan; botda rozilik versiyasi va vaqti saqlanadi
- [ ] Server O'zbekistonda, domen + TLS
- [ ] Backup va tiklash sinovi
- [ ] Sentry + uptime alert
- [ ] Pilot yo'nalishlari ❓ (masalan, Toshkent ↔ Samarqand, Toshkent ↔ Farg'ona)
- [ ] 20–50 tashuvchi oldindan jalb qilingan va verifikatsiyadan o'tgan (aks holda mijozlar bo'sh qidiruvni ko'radi)
- [ ] Admin/moderator — kim, ish vaqti
- [ ] Support uchun Telegram akkaunt/guruh
- [ ] Pilot KPI: ro'yxatdan o'tganlar, verifikatsiyadan o'tgan tashuvchilar, e'lonlar, taklif → bitim konversiyasi, yakunlangan buyurtmalar, bekor qilish %, shikoyatlar, o'rtacha baho

---

## 8. Tasdiqlash kerak (❓)

| # | Savol | Tavsiya |
|---|-------|---------|
| P1 | Pilot kategoriyalari | Yo'lovchi + Posilka |
| P2 | Pilot yo'nalishlari | 1–2 ta yirik yo'nalish; qidiruv butun respublika bo'yicha ochiq |
| P3 | Tasdiqlash kutish vaqti | 30 daqiqa |
| P4 | Avto-yakunlash vaqti | 12 soat |
| P5 | Taklif muddati | 2 soat yoki jo'nashdan 1 soat oldin (qaysi biri oldin) |
| P6 | Pilotda tashuvchidan qaysi hujjatlar so'raladi | Haydovchilik guvohnomasi + tex-pasport + transport fotosi (yurist tasdiqlaguncha minimal) |
| P7 | Admin/moderator kim bo'ladi | Buyurtmachi |
