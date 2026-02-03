#!/usr/bin/env python3
"""
Telegram Referal Bot - Simple Working Version
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import List

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean, DateTime, BigInteger, Text, select, update, func
from pydantic_settings import BaseSettings

# ==================== CONFIG ====================
class Config(BaseSettings):
    bot_token: str = "8568085508:AAGC5687wLPiiaSN6RZO8uwk0D3sBWEYszU"
    admin_id: int = 422057508
    admin_username: str = "shohjahon_o5"
    database_url: str = "sqlite+aiosqlite:///bot.db"
    referral_reward: int = 500
    minimum_withdrawal: int = 15000
    sponsor_channels: str = "@shohjahon_shahriyev"
    is_railway: bool = False

    @property
    def sponsor_channels_list(self) -> List[str]:
        if not self.sponsor_channels:
            return []
        return [ch.strip() for ch in self.sponsor_channels.split(",") if ch.strip()]

settings = Config()

# ==================== DATABASE ====================
class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255))
    balance: Mapped[int] = mapped_column(Integer, default=0)
    referral_count: Mapped[int] = mapped_column(Integer, default=0)
    referred_by: Mapped[int] = mapped_column(BigInteger, nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Withdrawal(Base):
    __tablename__ = "withdrawals"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[int] = mapped_column(Integer)
    card_number: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Referral(Base):
    __tablename__ = "referrals"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger)
    referred_id: Mapped[int] = mapped_column(BigInteger)
    reward_given: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# ==================== INIT ====================
engine = create_async_engine(settings.database_url)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ==================== KEYBOARDS ====================
def main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Balans"), KeyboardButton(text="👥 Referallar")],
            [KeyboardButton(text="🔗 Referal havola"), KeyboardButton(text="💸 Pul yechib olish")],
            [KeyboardButton(text="📞 Admin bilan aloqa")]
        ],
        resize_keyboard=True
    )
    return keyboard

def restricted_menu():
    channels = settings.sponsor_channels_list
    if channels:
        channel_url = f"https://t.me/{channels[0].lstrip('@')}"
    else:
        channel_url = "#"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=" Obuna bo'lish ✅", url=channel_url)],
        [InlineKeyboardButton(text=" Obunani tekshirish 🔍", callback_data="check_subscription")]
    ])
    return keyboard

def admin_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Foydalanuvchilar"), KeyboardButton(text="💰 Balansni o'zgartirish")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="⚙️ Sozlamalar")],
            [KeyboardButton(text="📢 Xabar yuborish"), KeyboardButton(text="🔗 Admin referal havolasi")]
        ],
        resize_keyboard=True
    )
    return keyboard

def format_balance(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")

def generate_referral_link(user_id: int, bot_username: str) -> str:
    return f"https://t.me/{bot_username}?start={user_id}"

async def check_subscription(user_id: int, bot: Bot) -> bool:
    if not settings.sponsor_channels_list:
        return True
    
    if settings.is_railway:
        return True
    
    for channel in settings.sponsor_channels_list:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in ['left', 'kicked', 'banned']:
                return False
        except Exception:
            continue
    
    return True

# ==================== HANDLERS ====================
dp = Dispatcher()

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery):
    if await check_subscription(callback.from_user.id, callback.bot):
        await callback.message.delete()
        
        bot_username = (await callback.bot.get_me()).username
        referral_link = generate_referral_link(callback.from_user.id, bot_username)
        
        await callback.bot.send_message(
            callback.from_user.id,
            "🎉 **TABRIKLAYMIZ!**\n\n"
            "✅ Siz muvaffaqiyatli obuna bo'lding!\n"
            "🚀 Endi botning barcha imkoniyatlaridan foydalanishingiz mumkin:\n\n"
            "💰 Balansni ko'rish\n"
            "👥 Referallarni ko'rish\n"
            "🔗 Referal havola olish\n"
            "💸 Pul yechib olish\n\n"
            f"🔗 Sizning referal havolangiz:\n{referral_link}",
            reply_markup=main_menu()
        )
    else:
        await callback.message.edit_text(
            "❌ **Obuna tasdiqlanmadi!**\n\n"
            "🔒 Siz hali ba'zi homiy kanallarga obuna bo'lmagansiz.\n\n"
            "📺 Iltimos, quyidagi tugma orqali obuna bo'ling va qayta tekshiring:",
            reply_markup=restricted_menu()
        )
    await callback.answer("Obuna tekshirildi!")

@dp.message(CommandStart())
async def cmd_start(message: Message):
    referrer_id = None
    if message.text.startswith('/start '):
        try:
            referrer_id = int(message.text.split()[1])
        except (ValueError, IndexError):
            pass

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        is_admin_referral_test = (referrer_id == settings.admin_id and 
                                 message.from_user.id != settings.admin_id and 
                                 user is not None)

        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                referred_by=referrer_id,
                is_admin=(message.from_user.id == settings.admin_id)
            )
            session.add(user)
            await session.commit()

            if referrer_id and referrer_id != message.from_user.id:
                await handle_referral_reward(session, referrer_id, message.from_user.id, message.bot)

        if message.from_user.id == settings.admin_id:
            await message.answer(
                f"👨‍💼 Admin paneliga xush kelibsiz, {message.from_user.first_name}!",
                reply_markup=admin_menu()
            )
            return

        bot_username = (await message.bot.get_me()).username
        referral_link = generate_referral_link(message.from_user.id, bot_username)
        
        is_admin_referral_test = (referrer_id == settings.admin_id and 
                                 message.from_user.id != settings.admin_id and 
                                 user is not None)
        
        if is_admin_referral_test:
            # Admin test rejimi - obuna tekshirish shart emas
            await message.answer(
                f"🎉 Xush kelibsiz, {message.from_user.first_name}!\n\n"
                f"📊 Balans: {format_balance(user.balance)} so'm\n"
                f"👥 Referallar: {user.referral_count} ta\n\n"
                f"🔗 Sizning referal havolangiz:\n{referral_link}\n\n"
                f"Har bir do'stingiz {settings.referral_reward} so'm olib keladi!\n\n"
                f"🧪 **Bu admin test rejimi**",
                reply_markup=main_menu()
            )
        elif await check_subscription(message.from_user.id, message.bot):
            await message.answer(
                f"🎉 Xush kelibsiz, {message.from_user.first_name}!\n\n"
                f"📊 Balans: {format_balance(user.balance)} so'm\n"
                f"👥 Referallar: {user.referral_count} ta\n\n"
                f"🔗 Sizning referal havolangiz:\n{referral_link}\n\n"
                f"Har bir do'stingiz {settings.referral_reward} so'm olib keladi!",
                reply_markup=main_menu()
            )
        else:
            await message.answer(
                "👋 Assalomu alaykum!\n\n"
                "🔒 Botdan to'liq foydalanish uchun homiy kanallarimizga obuna bo'ling!\n\n"
                "📺 Obuna bo'lgandan so'ng barcha funktsiyalar mavjud bo'ladi.",
                reply_markup=restricted_menu()
            )

async def handle_referral_reward(session, referrer_id: int, referred_id: int, bot: Bot):
    result = await session.execute(
        select(Referral).where(
            Referral.referrer_id == referrer_id,
            Referral.referred_id == referred_id
        )
    )
    existing_referral = result.scalar_one_or_none()

    if existing_referral:
        return

    referred_subscribed = await check_subscription(referred_id, bot)
    if not referred_subscribed:
        return

    referrer_subscribed = await check_subscription(referrer_id, bot)
    if not referrer_subscribed:
        return

    referral = Referral(
        referrer_id=referrer_id,
        referred_id=referred_id,
        reward_given=True
    )
    session.add(referral)

    result = await session.execute(
        select(User).where(User.telegram_id == referrer_id)
    )
    referrer = result.scalar_one_or_none()
    
    if referrer:
        referrer.balance += settings.referral_reward
        referrer.referral_count += 1
        
        try:
            await bot.send_message(
                referrer_id,
                f"🎉 Tabriklayman! Yangi referal keldi!\n"
                f"💰 Balansingiz {settings.referral_reward} so'm ko'paydi.\n"
                f"📊 Jami balans: {format_balance(referrer.balance)} so'm"
            )
        except TelegramAPIError:
            pass

@dp.message(F.text == "💰 Balans")
async def cmd_balance(message: Message):
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "🔒 Botdan to'liq foydalanish uchun homiy kanallarimizga obuna bo'ling!\n\n"
            "📺 Obuna bo'lgandan so'ng barcha funktsiyalar mavjud bo'ladi.",
            reply_markup=restricted_menu()
        )
        return
        
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        
        if user:
            await message.answer(
                f"💰 Sizning balansingiz: {format_balance(user.balance)} so'm\n\n"
                f"🎁 Referallar soni: {user.referral_count} ta"
            )

@dp.message(F.text == "👥 Referallar")
async def cmd_referrals(message: Message):
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "🔒 Botdan to'liq foydalanish uchun homiy kanallarimizga obuna bo'ling!\n\n"
            "📺 Obuna bo'lgandan so'ng barcha funktsiyalar mavjud bo'ladi.",
            reply_markup=restricted_menu()
        )
        return
        
    await message.answer("👥 Referallaringiz haqida ma'lumot tez orada qo'shiladi.")

@dp.message(F.text == "🔗 Referal havola")
async def cmd_referral_link(message: Message):
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "🔒 Botdan to'liq foydalanish uchun homiy kanallarimizga obuna bo'ling!\n\n"
            "📺 Obuna bo'lgandan so'ng barcha funktsiyalar mavjud bo'ladi.",
            reply_markup=restricted_menu()
        )
        return
        
    bot_username = (await message.bot.get_me()).username
    referral_link = generate_referral_link(message.from_user.id, bot_username)
    
    await message.answer(
        f"🔗 Sizning referal havolangiz:\n\n"
        f"`{referral_link}`\n\n"
        f"🎁 Har bir referal uchun {format_balance(settings.referral_reward)} so'm bonus!",
        parse_mode="Markdown"
    )

@dp.message(F.text == "💸 Pul yechib olish")
async def cmd_withdraw(message: Message):
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "🔒 Botdan to'liq foydalanish uchun homiy kanallarimizga obuna bo'ling!\n\n"
            "📺 Obuna bo'lgandan so'ng barcha funktsiyalar mavjud bo'ladi.",
            reply_markup=restricted_menu()
        )
        return
        
    await message.answer(
        "💸 Pul yechib olish:\n\n"
        "📞 Admin bilan bog'laning:\n"
        f"@{settings.admin_username}\n\n"
        f"💰 Minimal yechib olish: {format_balance(settings.minimum_withdrawal)} so'm"
    )

@dp.message(F.text == "📞 Admin bilan aloqa")
async def cmd_contact_admin(message: Message):
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "🔒 Botdan to'liq foydalanish uchun homiy kanallarimizga obuna bo'ling!\n\n"
            "📺 Obuna bo'lgandan so'ng barcha funktsiyalar mavjud bo'ladi.",
            reply_markup=restricted_menu()
        )
        return
        
    await message.answer(
        "📞 Admin bilan bog'lanish:\n\n"
        f"@{settings.admin_username}\n\n"
        "📝 Savollaringiz bo'lsa yozing!"
    )

# Admin handlers
@dp.message(F.text == "👥 Foydalanuvchilar")
async def admin_users_list(message: Message):
    if message.from_user.id != settings.admin_id:
        return
    
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "🔒 Botdan to'liq foydalanish uchun homiy kanallarimizga obuna bo'ling!\n\n"
            "📺 Obuna bo'lgandan so'ng barcha funktsiyalar mavjud bo'ladi.",
            reply_markup=restricted_menu()
        )
        return

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(10)
        )
        users = result.scalars().all()

        text = "👥 Oxirgi foydalanuvchilar:\n\n"
        
        for user in users:
            text += f"👤 {user.first_name} (@{user.username or 'none'})\n"
            text += f"💰 Balans: {format_balance(user.balance)} so'm\n"
            text += f"🆔 ID: {user.telegram_id}\n\n"

        await message.answer(text)

@dp.message(F.text == "💰 Balansni o'zgartirish")
async def admin_balance_change(message: Message):
    if message.from_user.id != settings.admin_id:
        return
    
    await message.answer(
        "💰 Balansni o'zgartirish:\n\n"
        "Format: `user_id +/-summa`\n\n"
        "Masalan:\n"
        "123456789 +5000\n"
        "123456789 -3000"
    )

@dp.message(F.text == "📊 Statistika")
async def admin_statistics(message: Message):
    if message.from_user.id != settings.admin_id:
        return
    
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "🔒 Botdan to'liq foydalanish uchun homiy kanallarimizga obuna bo'ling!\n\n"
            "📺 Obuna bo'lgandan so'ng barcha funktsiyalar mavjud bo'ladi.",
            reply_markup=restricted_menu()
        )
        return

    async with async_session_maker() as session:
        user_count_result = await session.execute(select(func.count(User.id)))
        user_count = user_count_result.scalar()

        balance_result = await session.execute(select(func.sum(User.balance)))
        total_balance = balance_result.scalar() or 0

        text = f"📊 **Bot statistikasi:**\n\n"
        text += f"👥 Jami foydalanuvchilar: {user_count} ta\n"
        text += f"💰 Jami balans: {format_balance(total_balance)} so'm\n\n"
        text += f"💸 Minimal yechib olish: {format_balance(settings.minimum_withdrawal)} so'm\n"
        text += f"🎁 Referal mukofoti: {format_balance(settings.referral_reward)} so'm"

        await message.answer(text)

@dp.message(F.text == "⚙️ Sozlamalar")
async def admin_settings(message: Message):
    if message.from_user.id != settings.admin_id:
        return
    
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "🔒 Botdan to'liq foydalanish uchun homiy kanallarimizga obuna bo'ling!\n\n"
            "📺 Obuna bo'lgandan so'ng barcha funktsiyalar mavjud bo'ladi.",
            reply_markup=restricted_menu()
        )
        return
    
    text = f"⚙️ Bot sozlamalari:\n\n"
    text += f"🤖 Admin: @{settings.admin_username}\n"
    text += f"🆔 Admin ID: {settings.admin_id}\n"
    text += f"💰 Referal mukofoti: {settings.referral_reward} so'm\n"
    text += f"💸 Minimal yechib olish: {settings.minimum_withdrawal} so'm\n"
    text += f"📺 Sponsor kanallar: {len(settings.sponsor_channels_list)} ta\n"
    railway_status = "Ha" if settings.is_railway else "Yo'q"
    text += f"🚀 Railway rejimi: {railway_status}"
    
    await message.answer(text)

@dp.message(F.text == "📢 Xabar yuborish")
async def admin_broadcast(message: Message):
    if message.from_user.id != settings.admin_id:
        return
    
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "🔒 Botdan to'liq foydalanish uchun homiy kanallarimizga obuna bo'ling!\n\n"
            "📺 Obuna bo'lgandan so'ng barcha funktsiyalar mavjud bo'ladi.",
            reply_markup=restricted_menu()
        )
        return
    
    await message.answer(
        "📢 Xabar yuborish:\n\n"
        "Yubormoqchi bo'lgan xabaringizni yozing.\n"
        "Xabar barcha foydalanuvchilarga yuboriladi.\n\n"
        "❌ Bekor qilish uchun 'bekor' deb yozing."
    )

@dp.message(F.text == "🔗 Admin referal havolasi")
async def admin_referral_link(message: Message):
    if message.from_user.id != settings.admin_id:
        return
    
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "🔒 Botdan to'liq foydalanish uchun homiy kanallarimizga obuna bo'ling!\n\n"
            "📺 Obuna bo'lgandan so'ng barcha funktsiyalar mavjud bo'ladi.",
            reply_markup=restricted_menu()
        )
        return
    
    bot_username = (await message.bot.get_me()).username
    referral_link = generate_referral_link(settings.admin_id, bot_username)
    
    await message.answer(
        f"🔗 **Admin referal havolasi:**\n\n"
        f"`{referral_link}`\n\n"
        f"🎯 **Test qilish uchun:**\n"
        f"• Bu havolani yangi foydalanuvchi sifatida oching\n"
        f"• Botning ishlashini tekshiring\n"
        f"• Referal mukofoti tizimini sinab ko'ring\n\n"
        f"📊 **Admin ID:** {settings.admin_id}\n"
        f"💰 **Mukofot:** {settings.referral_reward} so'm",
        parse_mode="Markdown"
    )

# Admin broadcast handlers
@dp.message(F.from_user.id == settings.admin_id, F.text & ~F.command)
async def handle_admin_text_broadcast(message: Message):
    message_text = message.text.strip()
    
    if message_text.lower() == 'bekor':
        await message.answer("❌ Xabar yuborish bekor qilindi.")
        return
    
    try:
        async with async_session_maker() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
            
            success_count = 0
            error_count = 0
            
            for user in users:
                try:
                    await message.bot.send_message(
                        user.telegram_id,
                        f"📢 **ADMIN XABARI**\n\n{message_text}"
                    )
                    success_count += 1
                except Exception:
                    error_count += 1
            
            await message.answer(
                f"✅ Xabar yuborildi!\n\n"
                f"📊 Muvaffaqiyatli: {success_count} ta\n"
                f"❌ Xatolik: {error_count} ta\n"
                f"👥 Jami: {len(users)} ta foydalanuvchi"
            )
            
    except Exception:
        await message.answer("❌ Xabar yuborishda xatolik yuz berdi!")

@dp.message(F.text.regexp(r'^\d+ [+-]\d+$'))
async def process_balance_change(message: Message):
    if message.from_user.id != settings.admin_id:
        return

    try:
        parts = message.text.split()
        user_id = int(parts[0])
        operation = parts[1]
        amount = int(operation[1:])

        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.telegram_id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                await message.answer(f"❌ Foydalanuvchi topilmadi: {user_id}")
                return
            
            if operation.startswith('+'):
                user.balance += amount
            else:
                if user.balance < amount:
                    await message.answer(f"❌ Yetarli balans yo'q! Joriy balans: {format_balance(user.balance)} so'm")
                    return
                user.balance -= amount
            
            await session.commit()
            
            await message.answer(
                f"✅ Balans muvaffaqiyatli o'zgartirildi!\n\n"
                f"👤 Foydalanuvchi: {user.first_name}\n"
                f"💰 Miqdor: {operation}{format_balance(amount)} so'm\n"
                f"📊 Yangi balans: {format_balance(user.balance)} so'm"
            )
            
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

# ==================== MAIN ====================
async def main():
    await init_db()
    bot = Bot(token=settings.bot_token)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot to'xtatildi")
    except Exception as e:
        print(f"❌ Xatolik: {e}")
        sys.exit(1)

