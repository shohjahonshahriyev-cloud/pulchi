# Telegram Referal Bot

Telegram uchun referal asosida pul mukofotli bot.

## Xususiyatlari

- 🎁 Referal tizimi - har bir yangi foydalanuvchi uchun mukofot
- 💰 Balans tizimi - pul yig'ish va yechib olish
- 📊 Admin paneli - to'liq boshqaruv
- 📱 To'lov tizimlari - Payme, Click, admin orqali
- 🛡️ Himoya - homiy kanallarga obuna tekshiruvi
- 📈 Statistika - bot ishlashi monitoringi

## O'rnatish

1. Repozitoriyani klonirlash:
```bash
git clone <repository-url>
cd telegram-referral-bot
```

2. Virtual muhit yaratish:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. Kutubxonalarni o'rnatish:
```bash
pip install -r requirements.txt
```

4. Konfiguratsiya:
```bash
cp .env.example .env
```

`.env` faylini to'ldiring:
```
BOT_TOKEN=your_bot_token_here
ADMIN_ID=your_admin_id_here
SPONSOR_CHANNELS=@channel1,@channel2
REFERRAL_REWARD=5000
MINIMUM_WITHDRAWAL=10000
```

5. Botni ishga tushirish:
```bash
python bot.py
```

## Bot ishlashi

1. Foydalanuvchi `/start` bosib botga kiradi
2. Agar referal havola orqali kirgan bo'lsa, referer_id saqlanadi
3. Bot foydalanuvchiga shaxsiy referal link beradi
4. Referal orqali kirgan foydalanuvchi:
   - botga start bosishi
   - homiy kanal(lar)ga obuna bo'lishi shart
5. Shartlar bajarilgach:
   - referer balansiga mukofot qo'shiladi
   - bitta foydalanuvchi faqat 1 marta hisoblanadi

## Admin panel

Admin quyidagi imkoniyatlarga ega:
- 👥 Foydalanuvchalar ro'yxati
- 💰 Balanslarni o'zgartirish
- 📋 To'lov so'rovlarini tasdiqlash
- 📺 Homiy kanallarni boshqarish
- ⚙️ Mukofot miqdorini o'zgartirish
- 📊 Statistika

## To'lov tizimlari

- 📱 **Payme** - telefon raqami orqali
- 💳 **Click** - karta raqami orqali
- 👨‍💼 **Admin** - to'g'ridan-to'g'ri admin orqali

## Himoya tizimlari

- Homiy kanalga obuna bo'lmasa bot ishlamaydi
- Fake akkauntlar hisoblanmaydi
- Telegram ID orqali tekshiruv
- 1 user = 1 mukofot

## Database

Bot SQLite database ishlatadi, lekin PostgreSQL ga o'tish mumkin:
```python
# .env faylida
DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname
```

## Qo'shimcha imkoniyatlar

- 🔄 Auto-restart
- 📊 Real-time statistika
- 🔔 Admin bildirishnomalari
- 🌐 Multi-language support (keyingi versiyada)

## Yordam

Agar muammo yuzaga kelsa:
1. Loglarni tekshiring
2. Konfiguratsiyani to'g'ri kiritganingizga ishonch hosil qiling
3. Bot tokenini tekshiring
4. Admin ID ni tekshiring

## Litsenziya

MIT License
