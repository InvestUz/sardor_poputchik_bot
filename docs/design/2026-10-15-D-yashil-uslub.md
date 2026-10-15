# D uslub: "Car Booking | Ride Sharing" (Behance) asosida

Manba: https://www.behance.net/gallery/206880945/Car-Booking-Ride-Sharing-Mobile-App-UIUX-Design (muallif: MD Sabbir Hosen).
Foydalanuvchi qarori (2026-10-15): Mini App shu dizayn uslubida bo'lsin. **Faqat uslub tizimi olinadi** (ranglar, shrift, komponent shakllari, joylashuv). Muallifning illyustratsiyalari, "Driven" brendi va rasmlari ko'chirilmaydi — o'rniga o'zimizning ikonka va oddiy SVG kompozitsiyalar.

C variantdagi **funksiyalar saqlanadi** (narx maslahati, ishonch belgilari, faollik, bosqichlar, posilka kodi, Telegram tugmalari). O'zgaradi — faqat ko'rinish.

## Uslub tizimi (manbadan o'lchab olingan)
| Token | Qiymat | Ishlatilishi |
|-------|--------|--------------|
| Asosiy yashil | `#46C96B` | Asosiy tugmalar, faol tab, ikonkalar, havolalar |
| Och yashil | `#D0F2DA` | Ikonka doiralari foni, tanlangan chip foni, ma'lumot bloklari |
| Kulrang fon | `#F2F2F2` | Input va ro'yxat qatorlari foni, statistika plitkalari |
| O'rta kulrang | `#8E8E8E` | Ikkinchi darajali matn, nofaol ikonkalar |
| Qora | `#232323` | Asosiy matn, sarlavhalar |
| Oq | `#FFFFFF` | Ekran foni, bottom-sheet, kartalar |
| Shrift | **Open Sans** (Bold / SemiBold / Regular) — kirill va o'zbek lotinini qo'llaydi | Hamma joyda bitta oila |

Yashil `#46C96B` oq fonda matn uchun kontrasti past (≈2.2:1) — **oq matnli tugma foni** sifatida va katta ikonkalarda ishlatiladi; kichik yashil matn (havolalar) uchun to'qroq `#1F8540` (≈4.7:1).

## Komponentlar
- **Sarlavha (header):** chapda orqaga strelka, o'rtada qalin sarlavha (17–18px). Telegram ichida BackButton native; sarlavha markazda qoladi.
- **Ekran sarlavhasi (auth/bo'sh holat):** markazda qalin 22–24px, ostida kulrang 13px izoh.
- **Input:** kulrang `#F2F2F2` fon, radius 8px, chapda och-yashil doirada yashil ikonka, balandlik 48px, chegara yo'q; fokusda yashil 1.5px chegara.
- **Asosiy tugma:** to'liq kenglik, yashil, oq qalin matn, radius 8px, balandlik 48–52px. Ikkinchi darajali: oq fon + yashil matn yoki shaffof "Not now" uslubida matnli tugma.
- **Ro'yxat qatori / menyu:** kulrang fon, radius 8px, chapda och-yashil doira ichida yashil ikonka, matn, o'ngda chevron yoki radio. Qatorlar orasida 8–10px.
- **Statistika plitkalari:** 3 ta kulrang plitka qatorda: yashil ikonka, qalin raqam, kichik kulrang yozuv (masalan "127 safar · 2 yil · 4.9 reyting").
- **Tablar:** matnli, faolida yashil pastki chiziq (About/Review kabi).
- **Bottom sheet:** oq, yuqori burchaklari 20–24px, tepada kulrang "tutqich" chiziq; kontent ustida turadi.
- **Tanlov plitkalari (chip/tips kabi):** kulrang kvadratsimon plitka; tanlanganida och-yashil fon + yashil chegara.
- **Pastki navigatsiya:** oq panel, 4 ta tab (ikonka + yozuv), faoli yashil — suzuvchi "kapsula" emas.
- **Muvaffaqiyat/bo'sh holat:** markazda katta yashil doira + oq ikonka (illyustratsiya o'rniga), sarlavha, izoh, tugma.
- **"Qayerga?" bloki (bosh ekran):** oq bottom-sheet ichida plitkalar: "Yo'l topish", "E'lon berish", "Posilka", tashuvchi uchun "Buyurtmalar"/"Marshrut".
- **Yo'nalish ko'rinishi:** xarita yo'q (shaharlararo) — o'rniga vertikal "Pickup / Dropoff" bloki: yashil doira-nuqtalar orasida chiziq, yonida shahar nomlari (manbadagi Pickup/Pickoff blokidek) va almashtirish tugmasi.
- **Haydovchi kartasi:** avatar, ism, "Haydovchi", o'ngda yashil doira-tugmalar (qo'ng'iroq, yozish), ostida 3 ustun: narx · raqam · joylar.

## Mavzu
Asosiy — och (oq). Qorong'i mavzu saqlanadi: fon `#121413`, sirt `#1C1F1D`, kulrang qatorlar `#262A27`, matn `#F2F2F2`, yashil `#46C96B` o'zgarmaydi.
