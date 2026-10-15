# Telegram yuk/yo'lovchi tashish platformasi — metodologiya, joriy etish rejasi va prod'gacha nazorat ro'yxati

> Manba: `ТЗ_Telegram_платформа_перевозок.docx` (v0.1, dastlabki).
> Hujjat holati: **taklif**. Har bir qaror belgilanadi: ✅ TZ'da kelishilgan · 💡 taklif (tasdiq kerak) · ❓ ochiq savol (qaror qilinmaguncha modulni boshlab bo'lmaydi).
> Sana: 2026-10-14

---

## ✅ Qabul qilingan qarorlar (2026-10-14)

| # | Qaror | Oqibati |
|---|-------|---------|
| D1 | **Bot + Telegram Mini App** gibridi | Mini App (React) — anketalar, qidiruv, takliflar, hamyon; bot — kirish, bildirishnomalar, tez tugmalar |
| D2 | MVP'da **faqat tashuvchi balansini onlayn to'ldirish** (Payme/Click) | Mijoz tashuvchiga naqd/karta orqali to'g'ridan-to'g'ri to'laydi; platforma mijoz pulini ushlamaydi → L3 xavfi MVP uchun olib tashlanadi. `PAYMENT_PENDING`/`REFUND_PENDING` faqat balans to'ldirish va jarima/qaytarishlarga tegishli |
| D3 | **Python stek**: aiogram 3 + FastAPI + SQLAlchemy 2/Alembic + PostgreSQL/PostGIS + Redis + Taskiq/Celery | §4.2 Variant A |
| D4 | **Jamoa: 1–2 dasturchi + Claude** | §9.4 dagi qisqartirilgan reja amal qiladi: ketma-ket bosqichlar, MVP qisqartirilgan |
| D5 | **Yuklama: 100–500** (foydalanuvchi/buyurtma, 1-yil) | Kichik yuklama → bitta server (4 vCPU / 8 GB, O'zbekistonda), PostgreSQL shu serverda, Docker Compose. Kubernetes, alohida navbat-klasteri, replikatsiya kerak emas |
| D6 | **Tillar: o'zbek (lotin) + rus** | Ingliz tili pilotdan chiqarildi; i18n tuzilmasi saqlanadi — keyin qo'shish faqat tarjima fayli |
| D7 | **Pilot to'lov tizimisiz** | Payme/Click, hamyon, komissiya yechish, jarimalar — pilotdan keyin (R2). Pilotda platforma tashuvchilar uchun **bepul**; komissiya faqat hisoblab statistikaga yoziladi (keyingi biznes-model uchun ma'lumot) |

---

## 0. Qisqa xulosa (1 daqiqada o'qish uchun)

1. TZ funksional jihatdan yaxshi yozilgan, lekin **prod'ga chiqishni to'xtatib qo'yadigan 3 ta blok** hal qilinmagan: **(a) pul oqimining yuridik modeli**, **(b) shaxsiy ma'lumotlarni O'zbekistonda saqlash talabi**, **(c) tashuvchi hujjatlari/litsenziyalar matritsasi**. Bular texnik emas, biznes-yuridik savollar — ishlab chiqish bilan parallel, lekin **birinchi navbatda** boshlanishi kerak.
2. UX bo'yicha asosiy texnik qaror: **sof bot (inline tugmalar) emas, "Bot + Telegram Mini App" gibridi**. Foto, o'lchamlar, manzil, filtrlar, xarita, ro'yxat/sortirovka — bularni faqat chat-tugmalar bilan qilish foydalanuvchi uchun azob va 5 ta kategoriya × ~10 maydon = juda uzun dialog.
3. Arxitektura: **modulli monolit** (mikroservis emas), PostgreSQL + PostGIS, Redis, fon vazifalar navbati, S3-mos fayl ombori, alohida web admin-panel.
4. MVP onlayn to'lov bo'yicha tavsiya: **1-bosqichda platforma mijoz pulini ushlab turmaydi** — mijoz tashuvchiga naqd/o'z kartasi orqali to'laydi, platforma esa faqat **tashuvchi balansini onlayn to'ldirish** (Payme/Click) va komissiyani balansdan yechish bilan ishlaydi. Mijozdan onlayn to'lov qabul qilib, tashuvchiga o'tkazish (escrow/agent sxemasi) — 2-bosqich, yuridik model tasdiqlangandan keyin.
5. Taxminiy muddat: **Discovery 3–4 hafta + ishlab chiqish ~16–18 hafta + pilot 3–4 hafta ≈ 6 oy**, 5–6 kishilik jamoa bilan (§9).

---

## 1. TZ tahlili: nima aniq, nima noaniq, nima ziddiyatli

### 1.1. Aniq (ishlashga tayyor)
- Rollar: Mehmon, Mijoz, Tashuvchi, Qabul qiluvchi, Admin (+ Moliya admini — taklif).
- 5 kategoriya: Yo'lovchi, Hujjat/xat, Posilka, Mebel/shaxsiy buyum, Katta yuk.
- Narx savdosi: muallif boshlang'ich narxni beradi → tashuvchilar taklif/qarshi narx → mijoz bittasini tanlaydi → qolganlari yopiladi → narx qotiriladi.
- Aniq manzil va kontaktlar faqat CONFIRMED'dan keyin ochiladi.
- Komissiya = yakuniy narx × % / 100, tashuvchining ichki balansidan, buyurtma bajarilgandan keyin yechiladi; balans yetmasa — yangi buyurtma bloklanadi.
- Nizo ochilsa — moliyaviy yopilish to'xtatiladi.
- Bir martalik yetkazib berish kodi, bruteforce himoyasi.
- Moliyaviy yozuvlar o'chirilmaydi, tuzatish — faqat korrektirovka yozuvi bilan.
- 3 til, matnlar markazlashgan holda saqlanadi.

### 1.2. TZ'dagi texnik kamchiliklar va ziddiyatlar (tuzatishni taklif qilaman)

| # | Muammo | Nega xavfli | Taklif |
|---|--------|-------------|--------|
| T1 | `PAYMENT_PENDING`, `REFUND_PENDING` buyurtma statuslari ro'yxatiga aralashtirilgan | Buyurtma bir vaqtda `IN_PROGRESS` va "to'lov kutilmoqda" bo'lishi mumkin — bitta status maydoni buni ifodalay olmaydi | 💡 **Alohida holat mashinalari**: `Listing` (e'lon), `Offer` (taklif), `Order` (bitim), `Payment` (to'lov), `Dispute` (nizo). Buyurtmada `payment_status` va `dispute_status` alohida maydon |
| T2 | `PUBLISHED`/`NEGOTIATING` e'longa tegishli, `CONFIRMED…COMPLETED` esa bitimga | Tashuvchi marshruti (masalan, 4 o'rindiq) **bir nechta** mijoz bilan bir nechta bitimga aylanadi — "bitta e'lon = bitta buyurtma" modeli ishlamaydi | 💡 `Listing` (1) → (N) `Order`. Sig'im (o'rindiq, kg, m³) e'londa saqlanadi, har bir bitim undan "band qiladi" |
| T3 | "Bajarilish tasdig'i bo'lmasa" holati aniqlanmagan | Buyurtma `AWAITING_COMPLETION`da abadiy qotib qoladi, komissiya yechilmaydi | 💡 Taymer: X soat ichida mijoz javob bermasa — avto-`COMPLETED` (yetkazishda kod kiritilgan bo'lsa) yoki adminga eskalatsiya |
| T4 | Komissiya **bajarilgandan keyin** yechiladi, mijoz esa tashuvchiga **naqd** to'laydi | Tashuvchi balansini 0 ga tushirib, pulni olib, komissiyani to'lamasligi mumkin; yoki kontakt ochilgandan keyin platformadan tashqarida kelishib olishadi | 💡 CONFIRMED paytida komissiyani balansda **rezerv (hold)** qilish; bajarilganda rezervni yechish; bekor bo'lsa — rezervni bo'shatish |
| T5 | "Qabul qiluvchi" roli bor, lekin u botdan foydalanmasligi mumkin | Telegram bot foydalanuvchi `/start` bosmaguncha unga xabar yubora olmaydi | 💡 Kodni qabul qiluvchiga **SMS** (Eskiz.uz / Playmobile) + agar u botda bo'lsa — Telegram orqali. Muqobil: kodni yuboruvchi o'zi qabul qiluvchiga beradi |
| T6 | "Telefonni tasdiqlash" | SMS-OTP qimmat va ortiqcha | 💡 Telegram `request_contact` tugmasi — telefon Telegram tomonidan tasdiqlangan; serverda `contact.user_id == from.id` tekshiruvi majburiy |
| T7 | Valyuta, vaqt zonasi ko'rsatilmagan | Pul summasi float'da saqlansa — yaxlitlash xatolari | 💡 UZS, **butun son (BIGINT, so'm)**; vaqt — UTC'da saqlash, `Asia/Tashkent` da ko'rsatish |
| T8 | O'zbek tili: lotin yoki kirill? | Matnlar hajmi 2 baravar oshishi mumkin | ❓ (tavsiya: MVP — faqat lotin) |
| T9 | Platformadan tashqarida kelishish (disintermediation) xavfi aytilmagan | Komissiya modeli yemiriladi | 💡 Kontaktlar faqat CONFIRMED'dan keyin; chat-ichki maskalangan aloqa (bot orqali xabar almashish) 2-bosqichda; reyting va kafolat faqat platforma ichidagi bitimlarga |
| T10 | Yo'lovchi tashish — litsenziyalanadigan faoliyat bo'lishi mumkin | Platforma "taksi dispetcherlik xizmati" deb baholanishi mumkin | ❓ Yurist xulosasi (§2) |

---

## 2. Yuridik va biznes-blokerlar (kod yozishdan OLDIN yoki parallel boshlash shart)

Bular ko'pincha ishlab chiqishdan **uzoqroq** davom etadi (merchant ulanishi 2–6 hafta, yuridik shaxs/bank — bir necha hafta).

| # | Masala | Nima qilish kerak | Kim | Kritik yo'l? |
|---|--------|-------------------|-----|--------------|
| L1 | **Yuridik shaxs** | MChJ/YaTT, bank hisob raqami, soliq rejimi | Buyurtmachi | ✅ Ha (to'lov provayderi shusiz ulanmaydi) |
| L2 | **Shaxsiy ma'lumotlar** | "Shaxsiy ma'lumotlar to'g'risida"gi qonun (ZRU-547) va 2021-yilgi o'zgartishlar: O'zbekiston fuqarolarining shaxsiy ma'lumotlari **O'zbekiston hududidagi serverlarda** qayta ishlanishi/saqlanishi va bazalar davlat reyestrida ro'yxatdan o'tkazilishi talab etiladi. → **Prod hosting O'zbekistonda** (UZCLOUD, Uztelecom DC va h.k.) | Yurist + DevOps | ✅ Ha — hosting tanlovi shunga bog'liq |
| L3 | **Pul oqimi modeli** | Platforma mijoz pulini qabul qilib tashuvchiga o'tkazadimi (agent/escrow)? Bu to'lov tashkiloti litsenziyasi/agent shartnomasi masalasi. MVP tavsiya — §0.4 | Yurist + Buyurtmachi | ✅ Ha |
| L4 | **Fiskalizatsiya** | Platforma komissiyasi uchun fiskal chek (IKPU/MXIK kodi). Payme/Click fiskalizatsiyani qo'llab-quvvatlaydi — merchant shartnomasida aniqlash | Buxgalter | Ha |
| L5 | **Tashuvchi hujjatlari matritsasi** | Kategoriya bo'yicha: pasport/ID, haydovchilik guvohnomasi (toifa), tex-pasport, sug'urta, (yo'lovchi uchun) litsenziya? | Yurist | Ha (moderatsiya moduli shunga bog'liq) |
| L6 | **Taqiqlangan buyumlar ro'yxati** | Xavfli yuklar, dori, pul, qurol va h.k. | Yurist | O'rtacha |
| L7 | **Hujjatlar to'plami** | Ommaviy oferta (foydalanish shartlari), maxfiylik siyosati, bekor qilish/jarima qoidalari, nizolar reglamenti — 3 tilda | Yurist | ✅ Ha (launch'dan oldin) |
| L8 | **Javobgarlik chegarasi** | Yuk yo'qolsa/buzilsa platforma javobgarmi? Vositachi sifatida pozitsiya | Yurist | Ha |

---

## 3. Ishlash metodologiyasi

### 3.1. Umumiy yondashuv
- **Bosqichli-iterativ (Scrum-lite)**: 2 haftalik sprintlar, har sprint oxirida staging'da demo.
- Har bir bosqich **vertikal kesim** bilan tugaydi — ya'ni "ishlaydigan funksiya bot + backend + admin'da", qatlamlarga ajratib emas.
- **"Qaror kerak" darvozasi**: ❓ belgili savol hal bo'lmaguncha unga bog'liq modul sprintga olinmaydi (TZ ham shuni talab qiladi). Hal bo'lmagan savollar uchun sozlanadigan parametr (admin settings) qilib qo'yiladi — kod o'zgarmaydi.
- **Hujjatlashtirish**: ADR (Architecture Decision Record) — har bir muhim qaror alohida qisqa fayl (`docs/adr/`). Domen lug'ati (`CONTEXT.md`) — "Listing", "Offer", "Order" kabi atamalar hamma uchun bir xil ma'noda.

### 3.2. Bosqichlar (TZ'dagi 6 bosqich, aniqlashtirilgan)

| Bosqich | Davomiyligi | Natija (Definition of Done) |
|---------|-------------|-----------------------------|
| **0. Discovery / Loyihalash** | 3–4 hafta | Barcha ❓ savollarga qaror; ERD; holat mashinalari diagrammasi; Mini App + bot UX prototipi (Figma); API kontrakt (OpenAPI); yuridik ishlar boshlangan; infratuzilma tanlangan; backlog baholangan |
| **1. Asos** | 3 hafta | Repo, CI/CD, dev/staging muhitlar; ro'yxatdan o'tish (til → kontakt), profil, rollar, i18n, kategoriyalar spravochnigi, shahar/tuman spravochnigi, admin-panel karkasi + RBAC, audit log |
| **2. Tashuvchi verifikatsiyasi** | 2 hafta | Hujjat yuklash, transport, admin moderatsiyasi, kategoriya bo'yicha ruxsatlar, qayta yuklash so'rovi, ruxsatni bekor qilish |
| **3. E'lonlar va qidiruv** | 4 hafta | 5 kategoriya anketalari (Mini App), tashuvchi marshrutlari + oraliq nuqtalar, filtrlar, matching, sortirovka, muddati o'tganlarni yashirish, "mos e'lon" bildirishnomalari, obunalar |
| **4. Bitim sikli** | 4 hafta | Takliflar/qarshi narx, taklif muddati, tanlash, sig'imni band qilish (race-condition'siz), manzil ochilishi, statuslar, bir martalik kod, bekor qilish, reyting/sharhlar |
| **5. Moliya** | 4 hafta | Hamyon + ledger (ikki tomonlama yozuv), Payme/Click orqali to'ldirish, komissiya rezerv/yechish, idempotentlik, jarimalar, nizolar, qaytarishlar, sverka, moliyaviy hisobotlar |
| **6. Hardening + pilot** | 3–4 hafta | Yuklama testlari, xavfsizlik testi, backup'dan tiklash mashqi, monitoring, cheklangan pilot (1–2 yo'nalish), xatolarni tuzatish, launch |

> Bosqichlar 2–5 qisman parallel ketadi (backend/frontend bo'linishi). Bosqich 0 dagi yuridik ishlar butun loyiha davomida parallel.

### 3.3. Sifat qoidalari (har bir sprint uchun Definition of Done)
- Server tomonda ruxsat tekshiruvi (bot/Mini App'ga ishonilmaydi).
- Har bir holat o'tishi — unit test bilan yopilgan (ruxsat etilgan va **taqiqlangan** o'tishlar).
- Moliyaviy kod — integratsion testlar: qayta yuborilgan webhook, parallel so'rovlar, tarmoq uzilishi.
- 3 tildagi matnlar to'liq (CI'da tarjima kalitlari to'liqligini tekshiruvchi skript).
- Code review (kamida 1 kishi), migratsiyalar orqaga qaytariladigan.
- Staging'da demo qilingan.

---

## 4. Taklif etilayotgan arxitektura

### 4.1. Komponentlar

```
            ┌──────────────┐        ┌───────────────────┐
 Telegram ─▶│  Bot (webhook)│        │  Mini App (React)  │◀── Telegram WebApp
            └──────┬───────┘        └─────────┬─────────┘
                   │ (ichki chaqiruv)          │ HTTPS + initData imzo tekshiruvi
                   ▼                           ▼
            ┌─────────────────────────────────────────┐
            │      Backend — modulli monolit (API)     │
            │  users · verification · listings ·       │
            │  matching · offers · orders · wallet/    │
            │  ledger · payments · disputes · reviews ·│
            │  notifications · i18n · audit · settings │
            └───┬──────────┬──────────┬──────────┬────┘
                │          │          │          │
         PostgreSQL+   Redis      Navbat       S3-mos ombor
          PostGIS   (kesh, lock,  (fon         (foto, hujjat —
                    rate-limit)   vazifalar)    shifrlangan, private)
                │
   Tashqi: Payme/Click · SMS (Eskiz) · Xarita/routing · Sentry
            ┌──────────────┐
            │ Admin-panel  │ (alohida web, RBAC, 2FA, IP-cheklov)
            └──────────────┘
```

### 4.2. Texnologik stek (tavsiya; jamoa tajribasiga qarab o'zgaradi)

| Qatlam | Variant A (Python) — tavsiya | Variant B (Node/TS) |
|--------|------------------------------|---------------------|
| Bot | aiogram 3 | grammY |
| Backend API | FastAPI + SQLAlchemy 2 + Alembic | NestJS + Prisma/TypeORM |
| Fon vazifalar | Celery / Taskiq + Redis (yoki RabbitMQ) | BullMQ |
| DB | PostgreSQL 16 + PostGIS | (bir xil) |
| Mini App | React + Vite + TypeScript + `@telegram-apps/sdk` | (bir xil) |
| Admin-panel | React (Refine yoki React-Admin) | (bir xil) |
| Fayllar | MinIO (O'zbekistondagi serverda) | (bir xil) |
| Routing | OSRM yoki Valhalla (OSM O'zbekiston ekstrakti, o'z serverida) | (bir xil) |
| Monitoring | Sentry, Prometheus + Grafana, Loki | (bir xil) |
| Deploy | Docker Compose (MVP) → keyinchalik k8s kerak bo'lsa | (bir xil) |

**Nega modulli monolit**: jamoa kichik, tranzaksion yaxlitlik (buyurtma + hamyon + ledger bitta DB-tranzaksiyada) muhim. Mikroservislar MVP uchun faqat murakkablik qo'shadi.

### 4.3. Xarita va matching (TZ'dagi ❓ "kartografik provayder")

| Provayder | O'zbekistonda sifat | Narx/litsenziya | Izoh |
|-----------|---------------------|-----------------|------|
| Yandex Maps API | Eng yaxshi qamrov | Tijoriy foydalanish uchun pullik litsenziya, routing API cheklovlari | Geokoding uchun kuchli |
| 2GIS API | Shaharlarda juda yaxshi | Pullik, kelishuv asosida | Shahar ichidagi manzillar uchun |
| Google Maps | O'rtacha | So'rov bo'yicha pullik | — |
| OSM + OSRM/Valhalla (self-hosted) | Shaharlararo yo'llar uchun yetarli | Bepul (faqat server) | Og'ish (detour) hisoblash uchun ideal |

💡 **Tavsiya (MVP):**
1. **O'z spravochnigi**: 14 hudud + tumanlar + aholi punktlari koordinatalari bilan (bir martalik import). Mijoz shahar/tumanni ro'yxatdan tanlaydi — geokodingsiz.
2. **Aniq manzil**: Telegram'da "joylashuvni yuborish" (lokatsiya pin) + matnli manzil. Geokoding API'ga ehtiyoj minimal.
3. **Og'ish hisoblash**: self-hosted OSRM. Formula: `detour = d(A,P) + d(P,Q) + d(Q,B) − d(A,B)`, bu yerda A→B — tashuvchi marshruti, P→Q — mijoz so'rovi. Shaharlar orasidagi masofalar matritsasi oldindan hisoblanib keshlanadi → qidiruv < 1 soniya.
4. Matching qat'iy filtrlar (SQL) → keyin reyting/og'ish/vaqt bo'yicha skor (ranjirlash).

### 4.4. Ma'lumotlar modeli (asosiy jadvallar)

TZ'dagi ro'yxat + aniqlashtirishlar:

- `users` (telegram_id, phone, lang, status, created_at) · `user_roles`
- `carrier_profiles` · `carrier_category_permissions` (kategoriya bo'yicha ruxsat, kim/qachon berdi)
- `verification_requests` · `documents` (fayl kaliti, turi, holati, muddati) · `document_requirements` (kategoriya × hujjat turi — admin sozlaydi)
- `vehicles` (turi, o'rindiqlar, yuk ko'tarish kg, kuzov o'lchamlari)
- `locations` (hudud/tuman/shahar, PostGIS nuqta) · `distance_matrix`
- `listings` (turi: `CLIENT_REQUEST` | `CARRIER_ROUTE`, kategoriya, holat, vaqt oynasi, narx, sig'im, yashirin aniq manzil) · `listing_route_points` · `listing_items` (yuk birliklari: o'lcham, og'irlik, foto)
- `offers` (narx, muallif, `parent_offer_id` — qarshi taklif zanjiri, `expires_at`, holat)
- `orders` (listing_id, client_id, carrier_id, **qotirilgan narx**, **qotirilgan komissiya %** — T7/§20 talabi, holat, payment_status) · `order_status_history`
- `delivery_codes` (kod **hash**, urinishlar soni, `expires_at`, `used_at`)
- `wallets` · `ledger_entries` (ikki tomonlama, `idempotency_key UNIQUE`, `reason`, `order_id`) · `commission_holds`
- `payments` (provider, `provider_txn_id UNIQUE`, holat, raw payload) · `refunds`
- `cancellations` (kim, sabab, vaqt, buyurtma holati, jarima) · `penalty_rules` · `user_violations`
- `disputes` · `dispute_evidence` · `dispute_decisions`
- `reviews` (`UNIQUE(order_id, author_id)`) 
- `notifications` · `notification_preferences` · `subscriptions` (mos e'lonlar uchun)
- `translations` (kalit × til) · `settings` (versiyalangan — o'zgarish tarixi bilan)
- `admin_users` · `admin_roles` · `audit_log` (append-only)

### 4.5. Ma'lumotlar yaxlitligi — qanday ta'minlanadi (TZ §20)

| Talab | Texnik yechim |
|-------|---------------|
| Bitta so'rovda ikki tasdiqlangan tashuvchi yo'q | Partial unique index: `UNIQUE(listing_id) WHERE status IN (confirmed…)` (bitta ijrochili kategoriyalar uchun) |
| Sig'imni ikki marta band qilish yo'q | `SELECT … FOR UPDATE` listing qatorida + `CHECK (reserved_seats <= total_seats)` |
| Takroriy to'lov balansni ikki marta oshirmaydi | `payments.provider_txn_id UNIQUE` + ledger `idempotency_key UNIQUE` + bitta tranzaksiyada |
| Takroriy yopish komissiyani ikki marta yechmaydi | Ledger `idempotency_key = 'commission:' || order_id` |
| Komissiya o'zgarishi eski buyurtmalarga ta'sir qilmaydi | Buyurtmada `commission_rate` CONFIRMED paytida nusxalanadi |
| Moliyaviy yozuvlar o'chirilmaydi | Ledger/audit — faqat INSERT (DB-rol darajasida UPDATE/DELETE taqiqlangan); soft-delete |
| Holat o'tishlari faqat serverda | Holat mashinasi — bitta modulda, jadval ko'rinishida; har o'tish `order_status_history` ga yoziladi |
| Muddati o'tgan e'lonlar yashirin | Qidiruv so'rovida `expires_at > now()` + fon vazifasi statusni `EXPIRED`ga o'tkazadi |

### 4.6. Holat mashinalari (taklif — Discovery'da tasdiqlanadi)

**Listing:** `DRAFT → PUBLISHED → (NEGOTIATING) → CLOSED | EXPIRED | CANCELLED`

**Offer:** `PENDING → COUNTERED → ACCEPTED | REJECTED | EXPIRED | WITHDRAWN | AUTO_CLOSED` (boshqasi tanlanganda)

**Order:**
```
AWAITING_CONFIRMATION → CONFIRMED → IN_PROGRESS → AWAITING_COMPLETION → COMPLETED
        │                  │             │                 │
        └──► CANCELLED ◄───┘             └──► DISPUTED ◄───┘ ──► (admin qarori) → COMPLETED | CANCELLED | REFUNDED
```
**Payment:** `CREATED → PENDING → SUCCEEDED | FAILED | EXPIRED`; `SUCCEEDED → REFUND_PENDING → REFUNDED`

---

## 5. UX qarori: Bot vs Mini App

| Funksiya | Sof bot | Mini App |
|----------|---------|----------|
| Til tanlash, kontakt ulashish, menyu | ✅ | — |
| Bildirishnomalar, tez harakatlar ("Taklifni qabul qilish", "Boshladim", kod kiritish) | ✅ | — |
| 5 kategoriya anketasi (o'lchamlar, bir nechta foto, yuk birliklari) | ❌ juda uzun dialog | ✅ |
| Qidiruv, filtrlar, sortirovka, pagination | ❌ noqulay | ✅ |
| Xarita, marshrut nuqtalari | ❌ | ✅ |
| Takliflarni solishtirish | ⚠️ | ✅ |

💡 **Tavsiya: gibrid.** Bot — kirish nuqtasi, bildirishnomalar va tez tugmalar; Mini App — anketalar, qidiruv, takliflar, profil, hamyon. Mini App so'rovlari serverda `initData` HMAC imzosi orqali autentifikatsiya qilinadi.

---

## 6. Xavfsizlik (TZ §18.2 → aniq choralar)

- **Autentifikatsiya**: bot — Telegram `from.id`; Mini App — `initData` imzosi + `auth_date` muddati; admin — login + 2FA (TOTP), IP allowlist yoki VPN.
- **RBAC** admin uchun: `SUPER_ADMIN`, `MODERATOR` (hujjatlar), `SUPPORT` (buyurtma/nizo), `FINANCE` (moliya), `VIEWER`. Har bir kritik harakat — `audit_log`.
- **Webhooklar**: Payme (Basic auth + IP), Click (sign_string MD5 tekshiruvi), Telegram (`secret_token` header). Faqat server-server tasdig'i to'lov hisoblanadi (TZ §11.4).
- **Bir martalik kod**: 6 raqam, DB'da hash, ≤5 urinish, keyin bloklash + adminga signal; muddat (masalan, 72 soat).
- **Rate limiting** (Redis): xabarlar, taklif yuborish, kod kiritish, to'ldirish so'rovlari.
- **Fayllar**: faqat rasm/PDF, hajm limiti, MIME tekshiruvi, EXIF (GPS) tozalash, private bucket, faqat qisqa muddatli signed URL orqali ochish; hujjatlar shifrlangan.
- **Loglar**: telefon/manzil/pasport/to'lov ma'lumotlari maskalanadi.
- **Sirlar**: `.env` repo'da emas; prod'da secret manager yoki hech bo'lmaganda faqat serverdagi cheklangan fayl.
- **Firibgarlikka qarshi**: yangi tashuvchiga limit (masalan, birinchi N buyurtma), ko'p bekor qilish → avtomatik cheklov, bir nechta akkaunt (bitta telefon/qurilma) aniqlash.

---

## 7. Bildirishnomalar va Telegram cheklovlari

- Telegram limiti: ~30 xabar/soniya umumiy, bitta chatga ~1 xabar/soniya → **barcha xabarlar navbat orqali**, token-bucket bilan.
- Foydalanuvchi botni bloklasa (403) — belgilash, qayta yubormaslik.
- "Yangi mos e'lon" xabarlari — spam bo'lmasligi uchun: obuna + kunlik limit + dayjest rejimi.
- Muhim hodisalar (CONFIRMED, kod, nizo, to'lov) — majburiy; marketing/dayjest — o'chirib qo'yiladigan.

---

## 8. Test strategiyasi

| Daraja | Nima | Vosita |
|--------|------|--------|
| Unit | Holat mashinalari, komissiya hisobi, jarima qoidalari, matching filtrlari | pytest / jest |
| Integratsion | DB + navbat + to'lov webhook simulyatsiyasi (qayta yuborish, tartibsiz kelish) | testcontainers |
| Konkurentlik | 2 mijoz bir o'rindiqqa bir vaqtda; 2 webhook bir vaqtda | parallel testlar |
| E2E | Bot dialoglari va Mini App asosiy oqimlari | Playwright (Mini App), bot uchun test-bot + staging |
| Yuklama | Kutilayotgan RPS × 3 | k6 / Locust |
| Xavfsizlik | OWASP Top-10, IDOR (boshqaning buyurtmasini ochish), webhook soxtalashtirish | qo'lda + ZAP |
| Tiklash | Backup'dan to'liq tiklash mashqi | runbook |
| UAT | Buyurtmachi + 5–10 haqiqiy tashuvchi bilan | staging |

TZ §21 qabul mezonlari → har biri test-keys sifatida yoziladi (traceability matritsa).

---

## 9. Jamoa, muddat va byudjet omillari

### 9.1. Minimal jamoa
| Rol | Bandlik |
|-----|---------|
| PM / biznes-analitik | 1 (Discovery'da to'liq, keyin 50%) |
| Backend dasturchi | 2 |
| Frontend (Mini App + admin) | 1–2 |
| QA | 1 (3-bosqichdan) |
| DevOps | 0.3–0.5 |
| UX/UI dizayner | 0.5 (Discovery + 1–3-bosqich) |
| Yurist, buxgalter | autsors, kerakli paytda |

### 9.2. Taxminiy grafik (5–6 kishilik jamoa)
```
Hafta:        1-4    5-7    8-9   10-13  14-17  18-21  22-25
Discovery     ████
Asos                 ███
Verifikatsiya              ██
E'lon/qidiruv              ████████
Bitim sikli                       ████████
Moliya                                   ████████
Hardening                                       ██████
Pilot                                                 ████
Yuridik/merchant ████████████████████████████████ (parallel)
```

### 9.4. Qisqartirilgan reja: 1–2 dasturchi + Claude (D4 — amaldagi reja)

**Tamoyil:** avval eng tor "to'liq sikl"ni prod'ga chiqarish, keyin kengaytirish. Har bir release haqiqiy foydalanuvchilarda sinaladi.

| Release | Tarkib | Taxminiy muddat |
|---------|--------|-----------------|
| **R0 — Discovery** | Ochiq savollar, ERD, holat mashinalari, Mini App ekranlari (oddiy wireframe), repo + CI + staging; yuridik/merchant parallel boshlanadi | 3 hafta |
| **R1 — "Yo'lovchi + Posilka" yadrosi** | Ro'yxatdan o'tish, 3 til (uz-lotin/ru/en), tashuvchi verifikatsiyasi (admin), **faqat 2 kategoriya**: Yo'lovchi va Posilka; e'lon/marshrut, shahar bo'yicha qidiruv (og'ishsiz), takliflar/qarshi narx, tanlash, manzil ochilishi, statuslar, bekor qilish (jarimasiz — faqat sabab va hisob), sharhlar, minimal admin-panel | 8–10 hafta |
| **R2 — Moliya** | Hamyon + ledger, Payme/Click orqali to'ldirish, komissiya rezerv/yechish, balans yetmasa bloklash, sverka, nizolar (admin qarori bilan) | 5–6 hafta |
| **Pilot** | 1–2 yo'nalish, 20–50 tashuvchi, cheklangan launch | 3–4 hafta (R3 bilan parallel) |
| **R3 — Kengaytirish** | Qolgan 3 kategoriya (Hujjat, Mebel, Katta yuk), yetkazib berish kodi + SMS, oraliq nuqtalar va og'ish (OSRM), jarimalar jadvali, obuna-bildirishnomalar, statistika | 6–8 hafta |

**Jami: ~6–7 oyda to'liq MVP, birinchi pilot ~4–5-oyda.**

> **Yangilanish (D7):** to'lov pilotdan chiqarilgani uchun tartib o'zgaradi: **R0 → R1 → Pilot (≈ 3-oy oxiri) → R2 Moliya + R3 Kengaytirish**. Pilotning aniq tarkibi — [02_PILOT_SPEC.md](02_PILOT_SPEC.md).

Nimani qisqartirmaymiz (prod uchun majburiy): server tomonda ruxsatlar, holat mashinasi testlari, ledger idempotentligi, backup + tiklash, Sentry, admin audit log.

Nimani oddiylashtiramiz: admin-panel — tayyor karkas (masalan, SQLAdmin yoki React-Admin) bilan; deploy — bitta server + Docker Compose; monitoring — Sentry + uptime-check + Telegram-alert; matching R1'da — "shahar A → shahar B + vaqt oynasi", og'ish R3'da.

**Ish taqsimoti (2 dasturchi bo'lsa):** 1-dasturchi — backend + bot + moliya; 2-dasturchi — Mini App + admin-panel. Claude — kod generatsiyasi, testlar, review, hujjatlar, migratsiyalar.

### 9.3. Doimiy xarajatlar (oylik, aniqlash kerak)
- Hosting O'zbekistonda (VPS/cloud: app, DB, backup, routing serveri)
- SMS (qabul qiluvchi kodi uchun) — har SMS pullik
- Xarita API (agar Yandex/2GIS tanlansa)
- To'lov provayderi komissiyasi (to'ldirishdan %)
- Sentry/monitoring (bepul tarif yetishi mumkin)
- Domen + TLS

---

## 10. Prod'ga chiqish nazorat ro'yxati (Go-Live Checklist)

### Biznes va yuridik
- [ ] Yuridik shaxs, bank hisobi
- [ ] Payme/Click merchant shartnomalari, prod kalitlar, fiskalizatsiya (IKPU)
- [ ] Oferta, maxfiylik siyosati, jarima/bekor qilish qoidalari, taqiqlangan buyumlar — 3 tilda, botda qabul qilish (versiya + vaqt saqlanadi)
- [ ] Shaxsiy ma'lumotlar bazasi reyestrga kiritilgan
- [ ] Komissiya %, minimal balans, jarima summalari, muddatlar — admin sozlamalarida
- [ ] Qo'llab-quvvatlash kanali (support bot/akkaunt), ish vaqti, javob SLA

### Infratuzilma
- [ ] Prod serverlar O'zbekistonda; staging prod'ga o'xshash
- [ ] Domen, TLS, Telegram webhook `secret_token` bilan
- [ ] PostgreSQL: kunlik to'liq backup + WAL (PITR), backup boshqa joyda; **tiklash mashqi o'tkazilgan**
- [ ] Fayl ombori backup'i
- [ ] CI/CD: test → staging → qo'lda tasdiq → prod; migratsiyalarni orqaga qaytarish rejasi
- [ ] Monitoring: Sentry, metrikalar (xato %, javob vaqti, navbat uzunligi, webhook xatolari), uptime-check, alertlar Telegram'ga
- [ ] Loglar markazlashgan, shaxsiy ma'lumotlar maskalangan

### Xavfsizlik
- [ ] Admin 2FA + RBAC, ortiqcha huquqlar yo'q
- [ ] Barcha sirlar repo'dan tashqarida, prod kalitlari faqat prod'da
- [ ] Webhook imzolari tekshiriladi; soxta webhook testi o'tgan
- [ ] Rate-limit, kod bruteforce testi
- [ ] IDOR testi (boshqa foydalanuvchi buyurtmasi/hujjatiga kirish)

### Sifat
- [ ] TZ §21 dagi barcha qabul mezonlari — yashil
- [ ] Yuklama testi: kutilgan yuklama × 3 da TZ §18.1 vaqtlari bajariladi
- [ ] 3 til — to'liq tarjima, ona tilida so'zlashuvchi tekshirgan
- [ ] Pilot natijalari tahlil qilingan, kritik xatolar yopilgan

### Operatsion
- [ ] Runbook'lar: to'lov tushmadi; bot ishlamayapti; DB tiklash; nizo jarayoni; tashuvchini bloklash
- [ ] Moderatorlar va support o'qitilgan, admin-panel qo'llanmasi
- [ ] Moliyaviy sverka jarayoni (kunlik, provayder hisoboti bilan)
- [ ] Launch rejasi: avval 1–2 yo'nalish (masalan, Toshkent ↔ Samarqand), keyin butun respublika
- [ ] KPI'lar: ro'yxatdan o'tganlar, tasdiqlangan tashuvchilar, e'lon→bitim konversiyasi, bekor qilish %, nizolar %, komissiya tushumi

---

## 11. Barcha ochiq savollar (yagona ro'yxat, tavsiyalar bilan)

### TZ'ning o'zidagi savollar (§24)
| # | Savol | Mening tavsiyam |
|---|-------|-----------------|
| Q1 | Komissiya foizi | Admin sozlamasida; boshlanishiga 5–10% oralig'ida bozor tahlili bilan; buyurtmada qotiriladi |
| Q2 | Balansni to'ldirish usullari, minimal qoldiq | Payme + Click; minimal qoldiq = kutilayotgan komissiya (rezerv modeli, T4) |
| Q3 | To'lov provayderi | Payme + Click (ikkalasi ham bozorda keng; Telegram Payments orqali ham ulanish imkoniyatini tekshirish) |
| Q4 | Jarimalar | Discovery'da jadval: rol × holat × jo'nashgacha vaqt. MVP: ogohlantirish + vaqtinchalik cheklov, pul jarimasi — balansdan |
| Q5 | Tashuvchi hujjatlari | Yurist bilan matritsa (L5); tizimda — sozlanadigan |
| Q6 | Xarita API, ruxsat etilgan og'ish | §4.3: o'z spravochnik + OSRM; og'ish — kategoriya bo'yicha sozlanadigan (masalan, 10–30 km) |
| Q7 | Qabul qiluvchi ssenariysi | Alohida qabul qiluvchi (ism + telefon), kod SMS orqali (T5) |
| Q8 | Bajarilish tasdig'i bo'lmasa | Kod bilan yetkazilgan bo'lsa — 24 soatdan keyin avto-COMPLETED; yo'lovchi — 12 soatdan keyin avto; e'tiroz bo'lsa — nizo |
| Q9 | Komissiya bazasi | Ikkala tomon oxirgi tasdiqlagan narx ✅ (TZ taklifi bilan rozi) |
| Q10 | Kutilayotgan yuklama | ✅ 100–500 (D5) |
| Q11 | Admin-panel | Alohida web-panel ✅ |
| Q12 | Ma'lumotlarni saqlash muddatlari | Yurist bilan; moliyaviy yozuvlar — soliq talablari bo'yicha (odatda 5 yil) |

### Qo'shimcha savollar (TZ'da yo'q, lekin hal qilish kerak)
| # | Savol | Tavsiya |
|---|-------|---------|
| Q13 | UX: sof bot yoki Bot + Mini App? | ✅ Hal qilindi — gibrid (D1) |
| Q14 | Jamoa qaysi stekni biladi? | ✅ Hal qilindi — Python (D3) |
| Q15 | MVP'da mijoz onlayn to'laydimi yoki faqat tashuvchi balansini to'ldiradimi? | ✅ Hal qilindi — faqat balans to'ldirish (D2) |
| Q16 | O'zbek tili: lotin / kirill / ikkalasi? | ✅ O'zbek (lotin) + rus (D6) |
| Q17 | Taklif muddati | Sozlanadigan; standart 2 soat yoki jo'nashdan 1 soat oldin — qaysi biri oldin bo'lsa |
| Q18 | E'lon muddati | Jo'nash vaqti o'tgach avtomatik EXPIRED |
| Q19 | Yo'lovchi tashishda bitta e'londa bir nechta mijoz (o'rindiqlar bo'yicha)? | Ha (T2) |
| Q20 | Posilkada bitta tashuvchi bir nechta yuk olishi mumkinmi (sig'im — kg/m³)? | Ha, sig'im bo'yicha |
| Q21 | Tomonlar o'rtasida bot ichida chat kerakmi? | MVP'da yo'q (kontaktlar CONFIRMED'dan keyin ochiladi); 2-bosqichda maskalangan chat |
| Q22 | Tashuvchi jismoniy shaxsmi yoki faqat YaTT/kompaniya? | Yuridik javobga bog'liq (L5, L10) |
| Q23 | Admin-panel tillari | Rus + o'zbek |
| Q24 | Brend nomi, bot username, domen | Buyurtmachi |
| Q25 | Pilot uchun yo'nalishlar va dastlabki tashuvchilarni kim jalb qiladi? | Buyurtmachi (marketplace "tovuq-tuxum" muammosi — tashuvchilarni launch'dan oldin jalb qilish kerak) |
| Q26 | Reyting shkalasi | 1–5 ✅ |
| Q27 | Mavjud kod/dizayn bormi yoki noldan? | Hozir repo bo'sh — noldan |

---

## 12. Keyingi qadamlar (taklif)

1. Ushbu hujjatdagi Q13–Q16 va Q10 ga javob olish (texnik qarorlar shunga bog'liq).
2. Yurist bilan uchrashuv: L2, L3, L5, L7, L10.
3. Payme va Click'ga merchant arizasi (eng uzoq jarayon).
4. Discovery boshlash: ERD + holat mashinalari + Figma prototip + OpenAPI.
5. Repo skeleti: monorepo (`bot/`, `backend/`, `miniapp/`, `admin/`, `infra/`, `docs/`), CI, docker-compose, staging.
