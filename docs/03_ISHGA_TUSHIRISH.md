# Ishga tushirish qo'llanmasi (pilot)

Bu hujjat — kodni serverga joylash, botni ulash va pilotni boshlash uchun qadam-baqadam yo'riqnoma.

---

## 1. Tizim tarkibi

| Qism | Qayerda | Vazifasi |
|------|---------|----------|
| Bot | `backend/app/bot/` | Ro'yxatdan o'tish (til → telefon → oferta), menyu, bildirishnomalar, tez tugmalar (tasdiqlash, yo'lga chiqdim, yakunlash, taklifni qabul qilish) |
| API | `backend/app/api/` | Mini App uchun REST API (`/api/...`), Telegram `initData` imzosi bilan himoyalangan |
| Mini App | `miniapp/` | E'lon berish, qidiruv, takliflar, buyurtmalar, profil, tashuvchi arizasi |
| Admin-panel | `backend/app/admin/` → `https://DOMEN/admin/` | Tashuvchilarni tekshirish, foydalanuvchilar, e'lonlar, buyurtmalar, shikoyatlar, sharhlar, sozlamalar, audit, statistika |
| Fon vazifalar | `backend/app/services/jobs.py` | Har daqiqada: muddati o'tgan e'lon/taklif, tasdiqlanmagan buyurtmalarni bekor qilish, avto-yakunlash, eslatmalar |
| Ma'lumotlar bazasi | PostgreSQL 16 | Barcha ma'lumotlar; migratsiyalar `backend/migrations/` |

Hammasi **bitta Docker konteynerda** ishlaydi (+ PostgreSQL + Caddy). 100–500 foydalanuvchi uchun bitta server yetarli.

---

## 2. Serverga qo'yiladigan talablar

- **O'zbekistondagi** server (shaxsiy ma'lumotlarni lokalizatsiya qilish talabi): 2–4 vCPU, 4–8 GB RAM, 60+ GB SSD, Ubuntu 22.04/24.04.
- Domen (masalan `yolchi.uz`) va uning A-yozuvi server IP manziliga.
- 80 va 443 portlar ochiq.
- Docker + Docker Compose o'rnatilgan.

---

## 3. Telegram tomonida tayyorgarlik

1. **@BotFather** → `/newbot` → nom va username → **token**ni saqlang.
2. `/setdescription`, `/setabouttext`, `/setuserpic` — uz/ru tavsif va logotip.
3. `/setjoingroups` → Disable (bot faqat shaxsiy chatda ishlaydi; admin guruhi bundan mustasno — quyida).
4. Moderatorlar uchun **yopiq Telegram guruh** oching, botni unga qo'shing, guruh ID'sini oling (masalan, @RawDataBot orqali) → `ADMIN_CHAT_ID`. Yangi tashuvchi arizalari va shikoyatlar shu guruhga keladi.
5. Mini App menyu tugmasi va webhook **avtomatik** o'rnatiladi (dastur ishga tushganda).

---

## 4. Serverga joylash

```bash
sudo mkdir -p /opt/yolchi && sudo chown $USER /opt/yolchi
git clone <repo-url> /opt/yolchi
cd /opt/yolchi/infra
cp .env.prod.example .env
nano .env        # DOMAIN, POSTGRES_PASSWORD, BOT_TOKEN, WEBHOOK_SECRET, SESSION_SECRET, ADMIN_CHAT_ID
docker compose up -d --build
docker compose logs -f app      # "webhook set" chiqishi kerak
```

Tasodifiy maxfiy kalitlar uchun: `openssl rand -hex 32`.

**Birinchi admin**ni yaratish (parol interaktiv so'raladi, kamida 10 belgi):

```bash
docker compose exec app python -m app.cli create-admin sardor SUPERADMIN
```

Rollar: `SUPERADMIN` (hammasi), `MODERATOR` (tashuvchi tekshiruvi, foydalanuvchilar, e'lonlar, sharhlar), `SUPPORT` (buyurtmalar, shikoyatlar, foydalanuvchilar).

Tekshirish:
- `https://DOMEN/healthz` → `{"ok": true}`
- `https://DOMEN/admin/` → login sahifasi
- Botga `/start` → til tanlash chiqadi

---

## 5. Zaxira nusxa (backup) — majburiy

```bash
chmod +x /opt/yolchi/infra/backup.sh /opt/yolchi/infra/restore.sh
crontab -e
# har kuni 03:15 da:
15 3 * * * /opt/yolchi/infra/backup.sh >> /var/log/yolchi-backup.log 2>&1
```

- Nusxalar `/var/backups/yolchi` ga yoziladi, 14 kun saqlanadi.
- **Boshqa joyga nusxalash** (`backup.sh` oxiridagi `rsync` qatorini to'ldiring) — server buzilsa ham ma'lumot qolishi uchun.
- Pilotdan oldin **tiklashni bir marta sinab ko'ring** (alohida test serverda): `./restore.sh /var/backups/yolchi/db-....dump /var/backups/yolchi/files-....tgz`.

---

## 6. Yangilash (yangi versiya chiqarish)

```bash
cd /opt/yolchi && git pull
cd infra && ./backup.sh && docker compose up -d --build
```

Migratsiyalar konteyner ishga tushganda avtomatik qo'llanadi (`alembic upgrade head`).

---

## 7. Lokal ishlab chiqish

```bash
cd backend
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"     # Linux/Mac: .venv/bin/pip
cp .env.example .env
.venv/Scripts/python -m pytest -q                                   # testlar
cd ../miniapp && npm install && npm run build
cd ../backend && .venv/Scripts/python run_dev.py                     # http://localhost:8000
```

Telegramsiz sinash (faqat `DEBUG=true`):

```bash
.venv/Scripts/python -m app.cli dev-user 111 Aziz
# brauzerda: http://localhost:8000/app/?dev=111
```

Botni lokal sinash uchun `.env` da `BOT_MODE=polling` va test bot tokenini qo'ying. Mini App tugmalari faqat `https` manzil bilan ishlaydi — buning uchun ngrok/cloudflared tunnel va `PUBLIC_URL=https://...` kerak.

---

## 8. Admin-panelda pilotdan oldin sozlanadigan narsalar

`/admin/settings`:

| Sozlama | Standart | Izoh |
|---------|----------|------|
| `enabled_categories` | PASSENGER, PARCEL | Pilot toifalari |
| `offer_ttl_minutes` | 120 | Taklif muddati |
| `confirm_timeout_minutes` | 30 | Tashuvchi tasdiqlashi uchun vaqt |
| `auto_complete_hours` | 12 | Javob bo'lmasa avto-yakunlash |
| `reminder_before_minutes` | 120 | Jo'nashdan oldin eslatma |
| `required_documents` | DRIVER_LICENSE, TECH_PASSPORT, VEHICLE_PHOTO | Tashuvchidan so'raladigan hujjatlar |
| `commission_percent` | 10 | Pilotda **yechilmaydi**, faqat statistika |
| `support_contact` | @support | Yordam uchun akkaunt — **albatta o'zgartiring** |
| `terms_version` | 1 | Oferta matni o'zgarsa oshiring |

**Oferta matni**: `backend/app/web/templates/terms_uz.html` va `terms_ru.html` — hozir namunaviy matn. Yurist ko'rib chiqqan yakuniy matn bilan almashtiring.

---

## 9. Kundalik operatsion ishlar (runbook)

| Vaziyat | Nima qilish |
|---------|-------------|
| Yangi tashuvchi arizasi | Admin guruhga xabar keladi → `/admin/verifications` → hujjatlarni ko'rish → tasdiqlash (toifalar bilan) / rad etish / qayta yuklash |
| Shikoyat | Admin guruhga xabar → `/admin/complaints` → buyurtma sahifasi → tarix, narx kelishuvi, bekor qilishlarni ko'rish → qaror (yakunlash yoki bekor qilish) + izoh |
| Qoidabuzar foydalanuvchi | `/admin/users/<id>` → bloklash (sabab bilan) |
| Noto'g'ri e'lon | `/admin/listings/<id>` → olib tashlash (sabab muallifga boradi) |
| Bot javob bermayapti | `docker compose ps`, `docker compose logs --tail=200 app`, `https://DOMEN/healthz` |
| Server qayta yuklandi | Konteynerlar `restart: unless-stopped` — o'zi ko'tariladi |
| Ma'lumot yo'qoldi | `restore.sh` (5-bo'lim) |

---

## 10. Pilot oldidan nazorat ro'yxati

- [ ] Server O'zbekistonda, domen + HTTPS ishlayapti
- [ ] `.env` dagi barcha maxfiy kalitlar tasodifiy, `DEBUG=false`
- [ ] Admin guruh ulangan, test ariza xabari kelgan
- [ ] Kamida 2 ta admin akkaunt (SUPERADMIN + MODERATOR), kuchli parollar
- [ ] `support_contact` sozlangan
- [ ] Oferta va maxfiylik siyosati yuristdan o'tgan va almashtirilgan
- [ ] Backup cron ishlayapti + off-site nusxa + tiklash sinovi o'tkazilgan
- [ ] 20–50 tashuvchi oldindan ro'yxatdan o'tgan va tasdiqlangan
- [ ] Jamoa ichida to'liq sikl sinovi: e'lon → taklif → qarshi narx → tasdiq → yo'lda → yakun → baho (uz va ru tillarida)
- [ ] Uptime monitoring (masalan, UptimeRobot `https://DOMEN/healthz` ga)
