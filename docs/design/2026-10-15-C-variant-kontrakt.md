# C variant — API kontrakti va vazifalar taqsimoti

Tanlangan: **C (aralash)** — 2026-10-15. Manba: [raqobatchilar tahlili](2026-10-15-raqobatchilar-tahlili.md), maket: https://claude.ai/artifact/QoKhux68FCKiFFTsTwvUeW

Backend va Mini App parallel ishlaydi; quyidagi kontrakt ikkalasi uchun yagona haqiqat manbai.

## API o'zgarishlari (backend-engineer)

**A. `user_public` (taklif, e'lon muallifi, buyurtma kontragenti)** — yangi maydonlar:
- `trips: int` — foydalanuvchi ishtirok etgan `COMPLETED` buyurtmalar soni (tashuvchi uchun — tashuvchi sifatida).
- `verified: bool` — tashuvchi profili `APPROVED`.

**B. `GET /api/users/{id}`** — ishonch bloki:
```json
{"id":2,"name":"Karim","rating":4.9,"rating_count":31,"trips":127,"verified":true,
 "member_since":"2026-10-01T...","checks":{"phone":true,"driver_license":true,"tech_passport":true,"vehicle_photo":true},
 "reviews":[{"rating":5,"text":"...","author":"Aziz","created_at":"..."}]}
```
`checks.*` (telefondan tashqari) faqat profil `APPROVED` bo'lsa va shu turdagi hujjat bo'lsa `true`. `reviews` — yashirilmagan oxirgi 3 ta.

**C. `GET /api/price-hint?category=&from_location_id=&to_location_id=&seats=1`**
```json
{"min":150000,"max":200000,"typical":175000,"distance_km":312,"source":"distance"}
```
- Agar so'nggi 90 kunda shu yo'nalish+toifada ≥5 e'lon bo'lsa — narxlar (1 o'rindiq/1 posilka uchun) p25..p75 dan, `source:"history"`.
- Aks holda masofa: haversine × 1.25 (yo'l koeffitsienti) × tarif. Sozlamalar: `price_per_km_passenger` (standart 550 so'm/km), `price_per_km_parcel` (250). min = 0.85×, max = 1.15×. PASSENGER uchun `seats` ga ko'paytiriladi.
- Hammasi 5 000 so'mga yaxlitlanadi.

**D. `GET /api/listings/{id}/activity`** (faqat muallif):
```json
{"carriers_on_route":8,"viewed":2}
```
- `viewed` — e'lonni ochgan noyob foydalanuvchilar (muallifdan tashqari). Yangi jadval `listing_views(listing_id, user_id, UNIQUE)`; `GET /api/listings/{id}` muallif bo'lmagan foydalanuvchi uchun yozadi.
- `carriers_on_route` — shu toifada ruxsati bor, `APPROVED` tashuvchilar soni, ularning shu yo'nalishga obunasi bor YOKI so'nggi 30 kunda shu yo'nalishda marshruti bo'lgan.

**E. Yo'lovchi so'rovi:** `whole_car: bool` (details'da saqlanadi va qaytariladi).

**F. Buyurtma ko'rinishi (`GET /api/orders/{id}`)** — yangi maydonlar:
- `timeline: [{"status":"CONFIRMED","at":"..."}]` — har bir holatga birinchi o'tilgan vaqt (tarixdan).
- `delivery_code: "4821" | null` — faqat **mijozga**, faqat posilka (PASSENGER emas) va holat CONFIRMED/IN_PROGRESS/AWAITING_COMPLETION/DISPUTED bo'lsa.
- `needs_code: bool` — tashuvchiga: "deliver" uchun kod kerakmi.
- `code_attempts_left: int | null` — tashuvchiga.

**G. Topshirish kodi (posilka):**
- Buyurtma CONFIRMED bo'lganda 4 xonali kod yaratiladi (`secrets`), mijozga bot xabari `order.delivery_code` ("Posilka topshirish kodi: {code}. Uni faqat qabul qiluvchiga ayting.").
- `POST /api/orders/{id}/deliver` body `{"code":"4821"}` — posilka uchun majburiy. Xato kod → `invalid_code` (params: `attempts_left`); 5 xatodan keyin → `code_locked` (shikoyat orqali hal qilinadi). Kodsiz → `code_required`. Bot "deliver" tez tugmasi posilka uchun `code_required` qaytaradi.
- Admin buyurtma sahifasida kod va urinishlar soni ko'rinadi.

**Yangi xato kodlari:** `invalid_code`, `code_locked`, `code_required` — ikkala i18n'ga.

## Mini App o'zgarishlari (miniapp-engineer)
1. **Ikki yuza:** brend yuzalari (Home hero, PageHead, bo'sh holatlar) — hozirgi editorial. Vazifa ekranlari — utilitar: matn 16–17px, yorliqlar 13–14px qalin, oddiy registr (mono/UPPERCASE emas), tugmalar ≥48px, statuslar rang + matn.
2. **Taklif kartasi** (maketdagi C): oq karta, narx 22–26px tabular, `✓ Tasdiqlangan` / `Yangi` belgisi, `★ reyting · N ta safar`, mashina · jo'nash vaqti. Kontragent ismiga bosilsa — ishonch bloki (B).
3. **Narx maslahati** (C) — e'lon yaratish, taklif formasi, qarshi narx: "Odatda 150 000–200 000 so'm"; narx < min → sariq ogohlantirish, oraliqda → yashil, > max → neytral.
4. **Telegram MainButton / SecondaryButton** asosiy harakatlar uchun (e'lon qilish, taklif yuborish, buyurtma harakati), `showProgress`, haptic; Telegram'dan tashqarida — sahifadagi tugma.
5. **Buyurtma:** vertikal bosqichlar vaqtlari bilan (`timeline`), "Keyingi qadam" matni (rol va holatga qarab), mijozga topshirish kodi, tashuvchiga "deliver" da kod kiritish.
6. **Jonli faollik** — muallifning faol e'lonida (D), har 20 soniyada yangilanadi.
7. **Chiplar:** sana "Bugun / Ertaga / Indinga" + boshqa sana; yo'lovchi so'rovida joylar "1 2 3 4 · Butun salon" (`whole_car`).
8. **Ishonch bloki** sahifasi `/users/:id` (B).
9. **Bosh ekran:** faol buyurtma (eng yaqin) eng tepada karta bo'lib turadi.
10. **Himoya:** e'lon formasi qoralamasi (Telegram CloudStorage, bo'lmasa localStorage), forma to'ldirilayotganda `enableClosingConfirmation`, bekor qilish tasdig'i `showPopup` (destructive).
