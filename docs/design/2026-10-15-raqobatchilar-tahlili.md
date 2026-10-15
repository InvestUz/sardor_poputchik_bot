# Yo'lchi uchun UX/UI tadqiqoti: yetakchi ilovalar tahlili

> Muallif: design-researcher agenti · 2026-10-15 · Holat: **tavsiya, tanlov kutilmoqda**
> (xulosa) belgisi — manbada tasdiqlanmagan, umumiy pattern bilimiga asoslangan fikr. Ba'zi spot.uz maqolalari reklama ("на правах рекламы").

**Muhim:** Yandex Go 2026-yil mayda O'zbekistonda **"Межгород"** ni ishga tushirdi (23 yo'nalish, 50–340 km). Haydovchi narx beradi, yo'lovchi takliflardan tanlaydi — bevosita raqobatchi.

## 1. Ilovalar bo'yicha patternlar

### inDrive (eng yaqin model)
1. **Narx maydoni ostida rangli indikator** (2026): yashil — narx tavsiyaga yaqin, takliflar tez; sariq — takliflar kam bo'lishi mumkin. → Yo'nalish bo'yicha tavsiya oralig'i ("Toshkent–Samarqand: odatda 150–200 ming") + rang.
2. **Jonli kutish holati**: yaqin haydovchilar soni, "N ta ko'rdi". → "12 ta tashuvchi bu yo'nalishda · 3 tasi ko'rdi".
3. **Taklif kartasi**: ism, mashina, raqam, reyting, safarlar soni, vaqt, narx.
4. **Verifikatsiya holati taklif tanlash ekranida** (2026) — faqat profilda emas.
5. **Bekor qilish sababi + tezkor tuzatish**: xato manzil/narx bo'lsa qayta yaratmasdan o'zgartirish.
6. Mijoz qarshi taklif bera olmaydi (uchinchi tomon manbasi). Bizda bor — ustunlik, lekin 1–2 raund bilan cheklash.
7. **"Суперводитель"** (~15% haydovchi) — pilotdan keyin "Ishonchli tashuvchi".

### Yandex Go (Межгород, Delivery)
1. Bosh ekranda alohida intercity kirish nuqtasi → ikkita teng karta: "Yo'lovchi" / "Posilka".
2. **Joylar soni yoki butun salon** segmentli tanlovi.
3. Bron qoidasi aniq; sana uchun **"Bugun / Ertaga / Indinga"** chiplari.
4. "Xavfsizlik" bo'limi → arzon variant: "Safarni yaqiningizga yuborish".
5. **Aktiv buyurtma bosh ekranning tepasida** (2023 redizayn, xaritasiz).
6. Kamchilik: tafsilotlar "haydovchi bilan kelishing" — bizda taklif ichida strukturalangan bo'lsin.

### BlaBlaCar
1. Qidiruv: Qayerdan / Qayerga / Sana / Yo'lovchilar + almashtirish tugmasi + so'nggi qidiruvlar chiplari (xulosa).
2. Instant yoki so'rov orqali bron — "tasdiq kutilmoqda" taxminiy javob vaqti bilan.
3. Verifikatsiya checklisti: ✓ Telefon · ✓ Guvohnoma · ✓ Texpasport.
4. Ikki tomonlama reyting, sharhlar bron oldidan ko'rinadi → profilda oxirgi 3 sharh.
5. Super Driver.

### Fasten va mahalliy ilovalar
- **Fasten**: 2024-yil avgust, Toshkent, Yandex loyihasi, yorqin yoshlar brendi; 2025–26 holati noma'lum; intercity yo'q.
- **MyTaxi**: ishonchli UX manbasi topilmadi.
- **Ways.uz**: intercity, narxni yo'lovchi belgilaydi — model bozorda sinalgan, yetakchi yo'q.
- **Uzum Market**: topshirish uchun SMS kod → foydalanuvchilar "topshirish kodi"ga o'rgangan.
- Telegram guruhlaridagi e'lon tili: "Toshkent–Farg'ona, 2 joy, ertaga 6:00" → kartalar shu tartibda; narx `180 000 so'm`.

### Wildberries
1. Qisqa chiziqli status zanjiri (≤6 qadam, bitta fe'l).
2. QR/kod bilan topshirish.
3. Yashirin ma'lumotni ochiq tushuntirish ("Tasdiqlagach ko'rinadi").
4. Zich, reklamali kataloglar — bizga mos emas.

### Telegram Mini App imkoniyatlari (rasmiy hujjat)
MainButton/SecondaryButton (`showProgress`, `hasShineEffect`), BackButton, HapticFeedback (`impactOccurred`, `notificationOccurred`, `selectionChanged`), themeParams, safe-area insetlar (`--tg-safe-area-inset-*`, `--tg-content-safe-area-inset-*`), `requestContact()`, `enableClosingConfirmation()`, `showPopup()` (destructive), CloudStorage (qoralamalar), past darajali Androidda animatsiyani kamaytirish.

## 2. Taqqoslash jadvali

| Pattern | inDrive | Yandex Go | BlaBlaCar | Mahalliy | WB | Yo'lchi uchun |
|---|---|---|---|---|---|---|
| Mijoz o'z narxini kiritadi | ✓ + indikator | ✗ | ✗ | Ways.uz ✓ | — | Saqlash + tavsiya oralig'i |
| Takliflar ro'yxati | ✓ | ✓ | — | — | — | Narx katta, reyting, safarlar, mashina, verifikatsiya, vaqt |
| Qarshi taklif | haydovchida | ✗ | ✗ | ? | — | Ikkala tomonda, ≤2 raund |
| Jonli kutish | ✓ | — | — | — | — | Hisoblagich + javob vaqti |
| Joylar / butun salon | ✓ | ✓ | ✓ | — | — | Segmentli tanlov |
| Verifikatsiya kartada | ✓ | sug'urta | ✓ qalqon | — | — | Kartada belgi, profilda checklist |
| Elita darajasi | ✓ | — | ✓ | — | — | Pilotdan keyin |
| Status zanjiri | — | bosh ekranda | ✓ | — | ✓ | Stepper + bosh ekranda pin |
| Topshirish kodi | — | — | — | SMS kod | QR | Posilka uchun 4 xonali kod |
| Safarni ulashish | — | ✓ | — | — | — | Pilotdan keyin |
| Bekor qilish sababi | ✓ tuzatish bilan | — | — | — | — | Avval "o'zgartirish" taklifi |

## 3. Uchta vizual yo'nalish

**A. Hozirgi editorial uslubni saqlash** — ish yo'q, brend kuchli; lekin outline harflar kichik ekranda va katta font sozlamasida o'qilmaydi, mono UPPERCASE yorliqlar uzun o'zbek/rus so'zlarida kengayadi, keksa haydovchilarda ishonch kamayishi mumkin (xulosa).

**B. Utility mass-market (Yandex Go/inDrive kabi)** — tanish, o'qilishi oson; lekin brend yo'qoladi, Yandex Go'dan farq qolmaydi. Mehnat: o'rta-yuqori.

**C. Gibrid ✅ TAVSIYA** — editorial uslub faqat **brend yuzalarida** (bosh ekran sarlavhasi, onboarding, bo'sh holatlar, "rahmat" ekrani). **Vazifa ekranlari** (forma, takliflar, status, profil) utilitar: body 16–17px, yorliqlar 13–14px sentence case (mono emas), narx katta tabular raqam, tap-zona ≥48px, semantik status ranglari + ikonka + matn, asosiy harakat — Telegram MainButton. `.surface-brand` / `.surface-task` tokenlari bilan qat'iy chegaralanadi. Mehnat: 3–5 kun (baho).

## 4. Top-10 o'zgarish

1. **Taklif kartasi**: narx 24–28px, reyting, safarlar soni, mashina, "✓ Tasdiqlangan", jo'nash vaqti; narx bo'yicha saralash. (inDrive, Yandex Go)
2. **Narx tavsiya oralig'i + rangli indikator** (admin yo'nalish bo'yicha kiritadi). (inDrive)
3. **Vazifa ekranlarida tipografika** (variant C). (Telegram qoidalari)
4. **Asosiy CTA → Telegram MainButton/SecondaryButton**, `showProgress`, haptic. (Telegram)
5. **Status stepper + bosh ekranda aktiv safar kartasi**. (WB, Yandex Go)
6. **"Tasdiq kutilmoqda" ekranida jonli kontekst** va "Narxni oshirish / Sanani o'zgartirish". (inDrive, BlaBlaCar)
7. **Joylar / Butun salon** tanlovi, **Bugun / Ertaga / Indinga** chiplari. (Yandex Go, BlaBlaCar)
8. **Ishonch bloki** profilda: verifikatsiya checklisti, safarlar soni, oxirgi 3 sharh. (BlaBlaCar, inDrive)
9. **Posilka topshirish kodi** (4 xonali, qabul qiluvchiga). (Uzum, WB)
10. **Onboarding va himoya**: `requestContact()`, tilni avto-tanlash, CloudStorage qoralama, `enableClosingConfirmation()`, bekor qilish `showPopup` orqali. (Telegram, inDrive)

Pilotdan keyin: "Ishonchli tashuvchi" darajasi, "Safarni yaqiningizga yuborish".

## 5. Manbalar
- https://core.telegram.org/bots/webapps
- https://algerie-eco.com/?p=327194 (inDrive 2026 yangilanishi)
- https://digitalbusiness.kz/2026-06-24/10-tisyach-marshrutov-v-god-i-2-5-mln-turisticheskih-poezdok-rukovoditel-indrive-mezhgorod-nazval-glavnie-tsifri-i-prioriteti-servisa/
- https://apps.apple.com/cy/app/id780125801 (inDrive)
- https://www.spot.uz/ru/2021/09/28/indriver/
- https://the-reese.beswifty.com/blog/mastering-indrive-your-guide-to-booking-rides-1764803268
- https://www.spot.uz/ru/2026/05/06/yandex-go/ (reklama)
- https://voyage.uz/guides/transport-yandex-go/
- https://www.iphones.ru/iNotes/prilozhenie-yandeks-go-na-ios-poluchilo-novyy-dizayn-teper-bez-karty-07-04-2023
- https://www.sostav.ru/publication/yandeks-go-obnovil-brend-70410.html
- https://inbusiness.kz/ru/news/poezdki-mezhdu-gorodami-novaya-usluga-ot-yandeks-go/
- https://economist.kg/transport/2026/05/21/v-iandeks-go-poiavilsia-servis-mezhgorod-dlia-poezdok-mezhdu-gorodami/
- https://antyweb.pl/super-driver-blablacar
- https://www.sharetribe.com/create/how-to-build-website-like-blablacar/
- https://www.spot.uz/ru/2024/08/27/fasten/ (reklama)
- https://apps.apple.com/ml/app/ways-uz/id1580534890
- https://kun.uz/news/2025/07/11/bir-yarim-yilda-28-ta-topshirish-punkti-ochildi-uzum-market-tarmogi-tez-osish-davrini-boshdan-kechirmoqda
- https://www.spot.uz/oz/2023/04/25/aliexpress-to-uzum/
- https://selsup.ru/blog/lenta-zakazov-wildberries/
- https://selsup.ru/blog/wildberries-testiruet-smart-vydachu-zakazov-qr-kod-vmesto-ocheredej-v-pvz/
- https://podrobno.uz/cat/obchestvo/mintrans-opublikoval-tseny-na-proezd-mezhdu-tashkentom-i-gorodami-ferganskoy-doliny-vyshe-stoimost-p/

Ochiq bo'shliqlar: inDrive taklif taymeri, BlaBlaCar ichki dizayn tizimi, Uzum status nomlari, MyTaxi UX — ilovalarda qo'lda tekshirish kerak.
