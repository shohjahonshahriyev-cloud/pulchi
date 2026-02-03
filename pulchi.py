#!/usr/bin/env python3
"""
Telegram Referal Bot - Bitta faylda
"""

import asyncio
import logging
import sys
from pathlib import Path
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
import aiohttp

# ==================== CONFIG ====================
class Settings(BaseSettings):
    bot_token: str = "8568085508:AAGC5687wLPiiaSN6RZO8uwk0D3sBWEYszU"
    admin_id: int = 422057508
    admin_username: str = "shohjahon_o5"  # Admin username
    database_url: str = "sqlite+aiosqlite:///bot.db"
    sponsor_channels: str = ""
    referral_reward: int = 500
    minimum_withdrawal: int = 15000
    payme_token: str = ""
    click_token: str = ""

    @property
    def sponsor_channels_list(self) -> List[str]:
        return [ch.strip() for ch in self.sponsor_channels.split(",") if ch.strip()]

    class Config:
        env_file = ".env"

settings = Settings()

# ==================== DATABASE ====================
engine = create_async_engine(settings.database_url)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str] = mapped_column(String(255), nullable=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    referral_count: Mapped[int] = mapped_column(Integer, default=0)
    referred_by: Mapped[int] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Referral(Base):
    __tablename__ = "referrals"
    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger)
    referred_id: Mapped[int] = mapped_column(BigInteger)
    reward_given: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Withdrawal(Base):
    __tablename__ = "withdrawals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[int] = mapped_column(Integer)
    payment_method: Mapped[str] = mapped_column(String(50))
    payment_details: Mapped[str] = mapped_column(Text, nullable=True)
    card_number: Mapped[str] = mapped_column(String(19), nullable=True)  # Add card_number field
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session():
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

# ==================== KEYBOARDS ====================
def main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Balans"), KeyboardButton(text="👥 Referallar")],
            [KeyboardButton(text="🔗 Referal havola"), KeyboardButton(text="💸 Pul yechib olish")],
            [KeyboardButton(text="📞 Admin bilan aloqa")]
        ],
        resize_keyboard=True,
        keyboard_size=3
    )
    return keyboard

def restricted_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=" Obuna bo'lish ✅", url=f"https://t.me/{settings.sponsor_channels_list[0].lstrip('@')}" if settings.sponsor_channels_list else "#")],
        [InlineKeyboardButton(text=" Obunani tekshirish 🔍", callback_data="check_subscription")]
    ])
    return keyboard

def admin_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Foydalanuvchilar"), KeyboardButton(text="💰 Balanslarni boshqarish")],
            [KeyboardButton(text="📋 To'lov so'rovlari"), KeyboardButton(text="📺 Homiy kanallar")],
            [KeyboardButton(text="⚙️ Sozlamalar"), KeyboardButton(text="📊 Statistika")]
        ],
        resize_keyboard=True
    )
    return keyboard

def referral_link_menu(referral_link: str):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Havolani nusxalash", callback_data=f"copy_link")],
        [InlineKeyboardButton(text="📤 Ulashish", url=f"https://t.me/share/url?url={referral_link}&text=🎉%20Referal%20bot%20orqali%20pul%20toping!%20%F0%9F%92%B0%20Har%20bir%20referal%20uchin%20500%20so'm")]
    ])
    return keyboard

def withdrawal_methods():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="‍💼 Admin orqali", url=f"https://t.me/{settings.admin_username}")]
    ])
    return keyboard

def sponsor_channels():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for channel in settings.sponsor_channels_list:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"📺 {channel}", url=f"https://t.me/{channel.lstrip('@')}")
        ])
    return keyboard

# ==================== UTILS ====================
async def check_subscription(user_id: int, bot: Bot) -> bool:
    """Check if user is subscribed to all sponsor channels"""
    if not settings.sponsor_channels_list:
        return True
    
    for channel in settings.sponsor_channels_list:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in ['left', 'kicked', 'banned']:
                return False
        except Exception as e:
            print(f"Error checking subscription for {channel}: {e}")
            return False
    
    return True

async def send_subscription_warning(user_id: int, bot: Bot):
    """Send warning message to user who left sponsor channel"""
    try:
        await bot.send_message(
            user_id,
            "⚠️ **OGOHLANTIRISH**\n\n"
            "❌ Siz homiy kanallardan birini tark etdingiz!\n\n"
            "📺 Botdan foydalanish davom etishi uchun:\n"
            "• Barcha homiy kanallarga qayta obuna bo'ling\n"
            "• Bot ishlashi to'xtatilguncha vaqt bor\n\n"
            "🔗 Homiy kanallar:\n" + 
            "\n".join([f"• {ch}" for ch in settings.sponsor_channels_list]) +
            "\n\n⏰ Agar tez orada obuna bo'lmasangiz, "
            "bot funksiyalari cheklanishi mumkin!"
        )
    except Exception as e:
        print(f"Error sending warning to {user_id}: {e}")

def generate_referral_link(user_id: int, bot_username: str) -> str:
    return f"https://t.me/{bot_username}?start={user_id}"

def format_balance(amount: int) -> str:
    return f"{amount:,}".replace(',', ' ')

def is_valid_phone_number(phone: str) -> bool:
    phone = phone.replace('+', '').replace(' ', '').replace('-', '')
    return phone.isdigit() and len(phone) == 9 and phone.startswith('9')

def is_valid_card_number(card: str) -> bool:
    card = card.replace(' ', '')
    return card.isdigit() and 16 <= len(card) <= 19

# ==================== HANDLERS ====================
dp = Dispatcher()

# Callback handlers should be registered before message handlers
@dp.callback_query(F.data == "copy_link")
async def copy_referral_link(callback: CallbackQuery):
    bot_username = (await callback.bot.get_me()).username
    referral_link = generate_referral_link(callback.from_user.id, bot_username)
    await callback.message.answer(f"🔗 Havola nusxalandi:\n{referral_link}")
    await callback.answer("Havola nusxalandi!")

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery):
    if await check_subscription(callback.from_user.id, callback.bot):
        # Delete the original message instead of editing it
        await callback.message.delete()
        
        # Send only the congratulations notification
        await callback.bot.send_message(
            callback.from_user.id,
            "🎉 **TABRIKLAYMIZ!**\n\n"
            "✅ Siz muvaffaqiyatli obuna bo'ldingiz!\n"
            "🚀 Endi botning barcha imkoniyatlaridan foydalanishingiz mumkin:\n\n"
            "💰 Balansni ko'rish\n"
            "👥 Referallarni ko'rish\n"
            "🔗 Referal havolani olish\n"
            "💸 Pul yechib olish\n\n"
            "📱 Asosiy menyuga o'tish uchun /start bosing!"
        )
    else:
        await callback.message.edit_text(
            "❌ **Obuna tasdiqlanmadi!**\n\n"
            "🔒 Siz hali ba'zi homiy kanallarga obuna bo'lmagansiz.\n\n"
            "📺 Iltimos, quyidagi tugma orqali obuna bo'ling va qayta tekshiring:",
            reply_markup=restricted_menu()
        )
    await callback.answer("Obuna tekshirildi!")

@dp.callback_query(F.data.startswith("approve_withdrawal:"))
async def approve_withdrawal(callback: CallbackQuery):
    print(f"DEBUG: Approve withdrawal callback received: {callback.data}")
    
    if callback.from_user.id != settings.admin_id:
        await callback.answer("❌ Siz admin emassiz!")
        return

    withdrawal_id = int(callback.data.split(":")[1])
    print(f"DEBUG: Processing approval for withdrawal ID: {withdrawal_id}")
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(Withdrawal).where(Withdrawal.id == withdrawal_id)
        )
        withdrawal = result.scalar_one_or_none()

        if not withdrawal:
            print(f"DEBUG: Withdrawal not found: {withdrawal_id}")
            await callback.answer("❌ To'lov topilmadi!")
            return

        if withdrawal.status != "pending":
            print(f"DEBUG: Withdrawal already processed: {withdrawal.status}")
            await callback.answer("❌ Bu to'lov allaqachon ko'rib chiqilgan!")
            return

        # Update withdrawal status
        withdrawal.status = "approved"
        withdrawal.processed_at = datetime.utcnow()
        await session.commit()
        print(f"DEBUG: Withdrawal approved successfully")

        # Notify user
        try:
            await callback.bot.send_message(
                withdrawal.user_id,
                f"✅ **TO'LOV TASDIQLANDI**\n\n"
                f"🆔 So'rov ID: {withdrawal.id}\n"
                f"💰 Miqdor: {format_balance(withdrawal.amount)} so'm\n"
                f"💳 Karta: {withdrawal.card_number[:4]} **** **** {withdrawal.card_number[-4:]}\n"
                f"📅 Vaqt: {withdrawal.processed_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"🎉 Pul tez orada sizning kartangizga o'tkaziladi!"
            )
            print(f"DEBUG: User notification sent for approval")
        except Exception as e:
            print(f"DEBUG: Failed to notify user: {e}")

        # Update admin message
        await callback.message.edit_text(
            f"✅ **TO'LOV TASDIQLANDI**\n\n"
            f"🆔 So'rov ID: {withdrawal.id}\n"
            f"💰 Miqdor: {format_balance(withdrawal.amount)} so'm\n"
            f"👤 Foydalanuvchi: {withdrawal.user_id}\n"
            f"📅 Vaqt: {withdrawal.processed_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"✅ Pul foydalanuvchiga yuborildi."
        )
        
        await callback.answer("To'lov tasdiqlandi!")

@dp.callback_query(F.data.startswith("reject_withdrawal:"))
async def reject_withdrawal(callback: CallbackQuery):
    print(f"DEBUG: Reject withdrawal callback received: {callback.data}")
    
    if callback.from_user.id != settings.admin_id:
        await callback.answer("❌ Siz admin emassiz!")
        return

    withdrawal_id = int(callback.data.split(":")[1])
    print(f"DEBUG: Processing rejection for withdrawal ID: {withdrawal_id}")
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(Withdrawal).where(Withdrawal.id == withdrawal_id)
        )
        withdrawal = result.scalar_one_or_none()

        if not withdrawal:
            print(f"DEBUG: Withdrawal not found: {withdrawal_id}")
            await callback.answer("❌ To'lov topilmadi!")
            return

        if withdrawal.status != "pending":
            print(f"DEBUG: Withdrawal already processed: {withdrawal.status}")
            await callback.answer("❌ Bu to'lov allaqachon ko'rib chiqilgan!")
            return

        # Update withdrawal status and refund balance
        withdrawal.status = "rejected"
        withdrawal.processed_at = datetime.utcnow()
        
        # Refund to user balance
        user_result = await session.execute(
            select(User).where(User.telegram_id == withdrawal.user_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            user.balance += withdrawal.amount
            print(f"DEBUG: Refunded {withdrawal.amount} to user {withdrawal.user_id}")
        
        await session.commit()
        print(f"DEBUG: Withdrawal rejected successfully")

        # Notify user
        try:
            await callback.bot.send_message(
                withdrawal.user_id,
                f"❌ **TO'LOV RAD ETILDI**\n\n"
                f"🆔 So'rov ID: {withdrawal.id}\n"
                f"💰 Miqdor: {format_balance(withdrawal.amount)} so'm\n"
                f"💰 Balansingizga qaytarildi: {format_balance(withdrawal.amount)} so'm\n"
                f"📅 Vaqt: {withdrawal.processed_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"📞 Admin bilan bog'laning: /admin"
            )
            print(f"DEBUG: User notification sent for rejection")
        except Exception as e:
            print(f"DEBUG: Failed to notify user: {e}")

        # Update admin message
        await callback.message.edit_text(
            f"❌ **TO'LOV RAD ETILDI**\n\n"
            f"🆔 So'rov ID: {withdrawal.id}\n"
            f"💰 Miqdor: {format_balance(withdrawal.amount)} so'm\n"
            f"👤 Foydalanuvchi: {withdrawal.user_id}\n"
            f"💰 Balansga qaytarildi: {format_balance(withdrawal.amount)} so'm\n"
            f"📅 Vaqt: {withdrawal.processed_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"❌ Pul foydalanuvchi balansiga qaytarildi."
        )
        
        await callback.answer("To'lov rad etildi!")

@dp.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session_maker() as session:
        # Parse referral parameter
        referrer_id = None
        if message.text.startswith('/start '):
            try:
                referrer_id = int(message.text.split()[1])
            except (ValueError, IndexError):
                pass

        # Check if user exists
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            # Create new user
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                referred_by=referrer_id,
                is_admin=(message.from_user.id == settings.admin_id)
            )
            session.add(user)
            await session.commit()

            # Handle referral reward
            if referrer_id and referrer_id != message.from_user.id:
                await handle_referral_reward(session, referrer_id, message.from_user.id, message.bot)

        # Check if user is admin and show admin panel
        if message.from_user.id == settings.admin_id:
            await message.answer(
                f"👨‍💼 Admin paneliga xush kelibsiz, {message.from_user.first_name}!",
                reply_markup=admin_menu()
            )
            return

        # Check subscription
        # Welcome message with subscription check
        bot_username = (await message.bot.get_me()).username
        referral_link = generate_referral_link(message.from_user.id, bot_username)
        
        if await check_subscription(message.from_user.id, message.bot):
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
    # Check if referral already processed
    result = await session.execute(
        select(Referral).where(
            Referral.referrer_id == referrer_id,
            Referral.referred_id == referred_id
        )
    )
    existing_referral = result.scalar_one_or_none()

    if existing_referral:
        return

    # Check if referred user is subscribed
    if not await check_subscription(bot, referred_id):
        return

    # Add referral record
    referral = Referral(
        referrer_id=referrer_id,
        referred_id=referred_id,
        reward_given=True
    )
    session.add(referral)

    # Update referrer balance and count
    result = await session.execute(
        select(User).where(User.telegram_id == referrer_id)
    )
    referrer = result.scalar_one_or_none()
    
    # Check if referrer is subscribed before giving reward
    if referrer:
        if await check_subscription(referrer_id, bot):
            referrer.balance += settings.referral_reward
            referrer.referral_count += 1
            
            # Notify referrer
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎉 Tabriklayman! Yangi referal keldi!\n"
                    f"💰 Balansingiz {settings.referral_reward} so'm ko'paydi.\n"
                    f"📊 Jami balans: {format_balance(referrer.balance)} so'm"
                )
            except TelegramAPIError:
                pass
        else:
            # Send warning to referrer
            await send_subscription_warning(referrer_id, bot)
            
            # Notify admin
            try:
                await bot.send_message(
                    settings.admin_id,
                    f"⚠️ Referer mukofot olmadi!\n\n"
                    f"👤 Foydalanuvchi: {referrer.first_name} (@{referrer.username})\n"
                    f"🆔 ID: {referrer_id}\n"
                    f"❌ Sabab: Homiy kanallarga obuna emas"
                )
            except:
                pass

    await session.commit()

@dp.message(F.text == "💰 Balans")
async def show_balance(message: Message):
    # Check subscription first
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "❌ Botdan foydalanish uchun avval barcha homiy kanallarga obuna bo'ling!",
            reply_markup=restricted_menu()
        )
        return
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Siz ro'yxatdan o'tmagansiz. /start bosing.")
            return

        await message.answer(
            f"💰 Sizning balansingiz: {format_balance(user.balance)} so'm\n\n"
            f"👥 Referallar soni: {user.referral_count} ta\n"
            f"💸 Minimal yechib olish: {format_balance(settings.minimum_withdrawal)} so'm"
        )

@dp.message(F.text == "👥 Referallar")
async def show_referrals(message: Message):
    # Check subscription first
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "❌ Botdan foydalanish uchun avval barcha homiy kanallarga obuna bo'ling!",
            reply_markup=restricted_menu()
        )
        return
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Siz ro'yxatdan o'tmagansiz. /start bosing.")
            return

        # Get referrals list
        result = await session.execute(
            select(Referral, User)
            .join(User, Referral.referred_id == User.telegram_id)
            .where(Referral.referrer_id == message.from_user.id)
        )
        referrals = result.all()

        if not referrals:
            await message.answer("👥 Sizda hali referallar yo'q.")
            return

        text = f"👥 Referallaringiz ({len(referrals)} ta):\n\n"
        for referral, referred_user in referrals:
            status = "✅ Mukofot berilgan" if referral.reward_given else "⏳ Kutilmoqda"
            name = referred_user.first_name or "Noma'lum"
            text += f"• {name} - {status}\n"

        await message.answer(text)

@dp.message(F.text == "🔗 Referal havola")
async def show_referral_link(message: Message):
    # Check subscription first
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "❌ Botdan foydalanish uchun avval barcha homiy kanallarga obuna bo'ling!",
            reply_markup=restricted_menu()
        )
        return
    
    bot_username = (await message.bot.get_me()).username
    referral_link = generate_referral_link(message.from_user.id, bot_username)
    await message.answer(
        f"🔗 Sizning referal havolangiz:\n\n{referral_link}\n\n"
        f"📤 Ushbu havolani do'stlaringizga ulashing va har bir kelayotgan referal uchun "
        f"{settings.referral_reward} so'm oling!",
        reply_markup=referral_link_menu(referral_link)
    )

@dp.message(F.text == "💸 Pul yechib olish")
async def request_withdrawal(message: Message):
    # Check subscription first
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "❌ Pul yechib olish uchun avval barcha homiy kanallarga obuna bo'ling!",
            reply_markup=sponsor_channels()
        )
        return
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Siz ro'yxatdan o'tmagansiz. /start bosing.")
            return

        if user.balance < settings.minimum_withdrawal:
            await message.answer(
                f"❌ Minimal yechib olish miqdori {format_balance(settings.minimum_withdrawal)} so'm.\n"
                f"Sizning balansingiz: {format_balance(user.balance)} so'm"
            )
            return

        await message.answer(
            f"💸 **Pul yechib olish**\n\n"
            f"Jami balans: {format_balance(user.balance)} so'm\n\n"
            f"👨‍💼 Admin orqali pul yechib olish uchun quyidagi tugmani bosing:\n\n"
            f"💼 Admin orqali - To'g'ridan-to'g'ri admin bilan bog'lanish\n\n"
            f"📝 Ariza yuborish formati:\n"
            f"💳 Karta raqami (16-19 raqam)\n"
            f"💰 Miqdor (minimal {settings.minimum_withdrawal} so'm)\n\n"
            f"Masalan:\n"
            f"8600123456789012\n"
            f"15000\n\n"
            f"⚠️ Admin bilan bog'lanib, yuqoridagi formatda ariza yuboring!",
            reply_markup=withdrawal_methods()
        )

@dp.message(F.text == "📞 Admin bilan aloqa")
async def contact_admin(message: Message):
    # Check subscription first
    if not await check_subscription(message.from_user.id, message.bot):
        await message.answer(
            "❌ Botdan foydalanish uchun avval barcha homiy kanallarga obuna bo'ling!",
            reply_markup=restricted_menu()
        )
        return
    
    # Create inline keyboard to open chat with admin
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Admin bilan chat ochish", url=f"https://t.me/{settings.admin_username}")]
    ])
    
    await message.answer(
        "📞 Admin bilan bog'lanish:\n\n"
        f"👨‍💼 Admin: @{settings.admin_username}\n"
        "🔽 Tugmani bosib admin bilan to'g'ridan-to'g'ri chat ochishingiz mumkin:\n\n"
        "📝 Yoki admin ga shaxsiy xabar yuboring:",
        reply_markup=keyboard
    )

@dp.message(Command("check_all"))
async def check_all_subscriptions(message: Message):
    """Check all users' subscriptions and notify those who left"""
    if message.from_user.id != settings.admin_id:
        await message.answer("❌ Siz admin emassiz!")
        return
    
    await message.answer("🔄 Barcha foydalanuvchilarning obunasi tekshirilmoqda...")
    
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.is_active == True))
        users = result.scalars().all()
        
        left_users = []
        
        for user in users:
            if not await check_subscription(user.telegram_id, message.bot):
                left_users.append(user)
                
                # Cancel pending withdrawals
                withdrawals_result = await session.execute(
                    select(Withdrawal).where(
                        Withdrawal.user_id == user.telegram_id,
                        Withdrawal.status == "pending"
                    )
                )
                pending_withdrawals = withdrawals_result.scalars().all()
                
                for withdrawal in pending_withdrawals:
                    withdrawal.status = "cancelled"
                    withdrawal.processed_at = datetime.utcnow()
                    user.balance += withdrawal.amount  # Refund balance
                
                # Notify user
                try:
                    await message.bot.send_message(
                        user.telegram_id,
                        "⚠️ **OGOHLANTIRISH**\n\n"
                        "❌ Siz homiy kanallardan birini tark etdingiz!\n\n"
                        "📺 Botdan foydalanish davom etishi uchun:\n"
                        "• Barcha homiy kanallarga qayta obuna bo'ling\n"
                        "• Bot ishlashi to'xtatilguncha vaqt bor\n\n"
                        "🔗 Homiy kanallar:\n" + 
                        "\n".join([f"• {ch}" for ch in settings.sponsor_channels_list]) +
                        "\n\n⏰ Agar tez orada obuna bo'lmasangiz, "
                        "bot funksiyalari cheklanishi mumkin!\n\n"
                        f"💰 {len(pending_withdrawals)} ta pul yechib olish arizasi bekor qilindi "
                        f"va balansingizga qaytarildi!"
                    )
                except Exception as e:
                    print(f"Failed to notify user {user.telegram_id}: {e}")
        
        await session.commit()
        
        # Notify admin
        if left_users:
            await message.answer(
                f"✅ Tekshirish tugadi!\n\n"
                f"📊 {len(left_users)} ta foydalanuvchi kanallarni tark etdi:\n\n"
                + "\n".join([f"• {u.first_name} (@{u.username or 'none'}) - ID: {u.telegram_id}" for u in left_users[:10]])
                + (f"\n\n... va yana {len(left_users) - 10} ta foydalanuvchi" if len(left_users) > 10 else "")
            )
        else:
            await message.answer("✅ Barcha foydalanuvchilar obunada!")

# Balance management handler - PRIORITY OVER WITHDRAWAL
@dp.message(F.text.regexp(r'^\d+ [+-]\d+$'))
async def process_balance_change(message: Message):
    if message.from_user.id != settings.admin_id:
        return

    try:
        print(f"DEBUG: Balance change request: '{message.text}'")
        parts = message.text.split()
        user_id = int(parts[0])
        change_amount = int(parts[1])  # +5000 yoki -3000
        
        print(f"DEBUG: Processing balance change - User: {user_id}, Amount: {change_amount}")
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await message.answer(f"❌ Foydalanuvchi topilmadi: {user_id}")
                return
            
            old_balance = user.balance
            user.balance += change_amount
            await session.commit()
            
            print(f"DEBUG: Balance updated - Old: {old_balance}, New: {user.balance}")
            
            # Notify user about balance change
            try:
                await message.bot.send_message(
                    user_id,
                    f"💰 Balansingiz o'zgartirildi!\n\n"
                    f"Oldingi balans: {format_balance(old_balance)} so'm\n"
                    f"Yangi balans: {format_balance(user.balance)} so'm\n"
                    f"O'zgarish: {'+' if change_amount > 0 else ''}{format_balance(change_amount)} so'm"
                )
                print(f"DEBUG: User notification sent to {user_id}")
            except Exception as e:
                print(f"DEBUG: Failed to notify user: {e}")
            
            await message.answer(
                f"✅ Balans muvaffaqiyatli o'zgartirildi!\n\n"
                f"👤 Foydalanuvchi: {user.first_name} (@{user.username or 'none'})\n"
                f"🆔 ID: {user_id}\n"
                f"💰 Oldingi balans: {format_balance(old_balance)} so'm\n"
                f"💰 Yangi balans: {format_balance(user.balance)} so'm\n"
                f"📈 O'zgarish: {'+' if change_amount > 0 else ''}{format_balance(change_amount)} so'm"
            )
            print(f"DEBUG: Admin confirmation sent")
            
    except (ValueError, IndexError) as e:
        print(f"DEBUG: Error in balance change: {e}")
        await message.answer(
            "❌ Noto'g'ri format!\n\n"
            "To'g'ri format:\n"
            "123456789 +5000\n"
            "123456789 -3000"
        )
    except Exception as e:
        print(f"DEBUG: Unexpected error: {e}")
        await message.answer(f"❌ Xatolik yuz berdi: {e}")

@dp.message(Command("users"))
async def admin_users_list(message: Message):
    if message.from_user.id != settings.admin_id:
        return

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(10)
        )
        users = result.scalars().all()

        if not users:
            await message.answer("👥 Foydalanuvchilar yo'q!")
            return

        text = "👥 Oxirgi 10 foydalanuvchi (ID bilan):\n\n"
        for i, user in enumerate(users, 1):
            text += f"{i}. {user.first_name} (@{user.username or 'none'})\n"
            text += f"   🆔 ID: {user.telegram_id}\n"
            text += f"   💰 Balans: {format_balance(user.balance)} so'm\n"
            text += f"   👥 Referallar: {user.referral_count} ta\n\n"

        await message.answer(text)
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Siz ro'yxatdan o'tmagansiz. /start bosing.")
            return

        if user.balance < settings.minimum_withdrawal:
            await message.answer(
                f"❌ Minimal yechib olish miqdori {format_balance(settings.minimum_withdrawal)} so'm\n"
                f"Sizning balansingiz: {format_balance(user.balance)} so'm"
            )
            return

        await message.answer(
            f"💸 **Pul yechib olish**\n\n"
            f"Jami balans: {format_balance(user.balance)} so'm\n\n"
            f"📋 Ariza yuborish uchun quyidagi formatda yozing:\n\n"
            f"💳 Karta raqami (16-19 raqam)\n"
            f"� Miqdor (minimal {settings.minimum_withdrawal} so'm)\n\n"
            f"Masalan:\n"
            f"8600123456789012\n"
            f"15000\n\n"
            f"⚠️ Arizangiz adminga yuboriladi va tasdiqlanadi!"
        )

# Handle withdrawal requests - SIMPLE VERSION
@dp.message(F.text.regexp(r'.*\d{16,19}.*\d+.*'))
async def handle_withdrawal_request(message: Message):
    """Handle withdrawal request from user - card number and amount"""
    # Skip if this is admin
    if message.from_user.id == settings.admin_id:
        return
    
    # Skip if this is a balance change command
    if message.from_user.id == settings.admin_id:
        parts = message.text.split()
        if len(parts) == 2 and parts[0].isdigit() and (parts[1].startswith('+') or parts[1].startswith('-')):
            return  # Let balance handler handle this
    
    try:
        text = message.text.strip()
        print(f"DEBUG: Withdrawal message: '{text}'")
        
        # Extract card number and amount more flexibly
        lines = text.split('\n')
        
        if len(lines) >= 2:
            card_line = lines[0].strip().replace(' ', '')
            amount_line = lines[1].strip()
        else:
            # Try to split by space if single line
            parts = text.split()
            if len(parts) >= 2:
                # Last part is amount, rest is card number
                amount_line = parts[-1]
                card_line = ''.join(parts[:-1]).replace(' ', '')
            else:
                print(f"DEBUG: Not enough parts in message")
                return
        
        # Validate
        if len(card_line) < 16 or not card_line.isdigit():
            print(f"DEBUG: Invalid card number: {card_line}")
            return
        if not amount_line.isdigit():
            print(f"DEBUG: Invalid amount: {amount_line}")
            return
        
        print(f"DEBUG: Withdrawal request - Card: {card_line}, Amount: {amount_line}")
        await process_admin_withdrawal(message, card_line, int(amount_line))
        
    except Exception as e:
        print(f"DEBUG: Error processing withdrawal: {e}")
        return

async def process_admin_withdrawal(message: Message, card_number: str, amount: int):
    """Process withdrawal request through admin"""
    print(f"DEBUG: Processing withdrawal - User: {message.from_user.id}, Card: {card_number}, Amount: {amount}")
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Siz ro'yxatdan o'tmagansiz. /start bosing.")
            return

        if user.balance < amount:
            await message.answer(
                f"❌ Sizda yetarli balans yo'q!\n"
                f"Balansingiz: {format_balance(user.balance)} so'm\n"
                f"So'ralgan miqdor: {format_balance(amount)} so'm"
            )
            return

        if amount < settings.minimum_withdrawal:
            await message.answer(
                f"❌ Minimal yechib olish miqdori {format_balance(settings.minimum_withdrawal)} so'm"
            )
            return

        # Create withdrawal request
        withdrawal = Withdrawal(
            user_id=message.from_user.id,
            amount=amount,
            card_number=card_number,
            payment_method="admin",
            status="pending"
        )
        session.add(withdrawal)
        
        # Deduct from balance
        user.balance -= amount
        
        await session.commit()
        await session.refresh(withdrawal)
        print(f"DEBUG: Withdrawal created - ID: {withdrawal.id}")

        # Notify user
        await message.answer(
            f"✅ **Ariza yuborildi!**\n\n"
            f"🆔 So'rov ID: {withdrawal.id}\n"
            f"💰 Miqdor: {format_balance(amount)} so'm\n"
            f"💳 Karta: {card_number[:4]} **** **** {card_number[-4:]}\n\n"
            f"⏳ So'rov adminga yuborildi. Tez orada ko'rib chiqiladi."
        )

        # Notify admin with approval buttons
        admin_text = (
            f"🔔 **YANGI TO'LOV SO'ROVI**\n\n"
            f"👤 Foydalanuvchi: {message.from_user.first_name} (@{message.from_user.username})\n"
            f"🆔 User ID: {message.from_user.id}\n"
            f"🆔 So'rov ID: {withdrawal.id}\n"
            f"💰 Miqdor: {format_balance(amount)} so'm\n"
            f"💳 Karta raqami: {card_number}\n"
            f"📅 Vaqt: {withdrawal.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"⚠️ So'rovni ko'rib chiqing va tasdiqlang!"
        )
        
        print(f"DEBUG: Sending notification to admin - ID: {settings.admin_id}")
        try:
            await message.bot.send_message(
                settings.admin_id,
                admin_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_withdrawal:{withdrawal.id}"),
                        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_withdrawal:{withdrawal.id}")
                    ]
                ])
            )
            print(f"DEBUG: Admin notification sent successfully")
        except Exception as e:
            print(f"DEBUG: Admin notification failed: {e}")

        # Notify user
        await message.answer(
            f"✅ **Ariza yuborildi!**\n\n"
            f"🆔 So'rov ID: {withdrawal.id}\n"
            f"💰 Miqdor: {format_balance(amount)} so'm\n"
            f"💳 Karta: {card_number[:4]} **** **** {card_number[-4:]}\n\n"
            f"⏳ So'rov adminga yuborildi. Tez orada ko'rib chiqiladi."
        )

        # Notify admin with approval buttons
        admin_text = (
            f"🔔 **YANGI TO'LOV SO'ROVI**\n\n"
            f"👤 Foydalanuvchi: {message.from_user.first_name} (@{message.from_user.username})\n"
            f"🆔 User ID: {message.from_user.id}\n"
            f"🆔 So'rov ID: {withdrawal.id}\n"
            f"💰 Miqdor: {format_balance(amount)} so'm\n"
            f"💳 Karta raqami: {card_number}\n"
            f"📅 Vaqt: {withdrawal.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"⚠️ So'rovni ko'rib chiqing va tasdiqlang!"
        )
        
        print(f"DEBUG: Sending notification to admin - ID: {settings.admin_id}")
        try:
            await message.bot.send_message(
                settings.admin_id,
                admin_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_withdrawal:{withdrawal.id}"),
                        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_withdrawal:{withdrawal.id}")
                    ]
                ])
            )
            print(f"DEBUG: Admin notification sent successfully")
        except Exception as e:
            print(f"DEBUG: Admin notification failed: {e}")

        # Notify user
        await message.answer(
            f"✅ To'lov so'rovi yuborildi!\n\n"
            f"🆔 So'rov ID: {withdrawal.id}\n"
            f"💰 Miqdor: {format_balance(amount)} so'm\n"
            f"💳 Karta: {card_number[:4]} **** **** {card_number[-4:]}\n\n"
            f"⏳ So'rov adminga yuborildi. Tez orada ko'rib chiqiladi."
        )

        # Notify admin with approval buttons
        admin_text = (
            f"🔔 **YANGI TO'LOV SO'ROVI**\n\n"
            f"👤 Foydalanuvchi: {message.from_user.first_name} (@{message.from_user.username})\n"
            f"🆔 User ID: {message.from_user.id}\n"
            f"🆔 So'rov ID: {withdrawal.id}\n"
            f"💰 Miqdor: {format_balance(amount)} so'm\n"
            f"💳 Karta raqami: {card_number}\n"
            f"📅 Vaqt: {withdrawal.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"⚠️ So'rovni ko'rib chiqing va tasdiqlang!"
        )

        print(f"DEBUG: Sending notification to admin - ID: {settings.admin_id}")
        try:
            await message.bot.send_message(
                settings.admin_id,
                admin_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_withdrawal:{withdrawal.id}"),
                        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_withdrawal:{withdrawal.id}")
                    ]
                ])
            )
            print(f"DEBUG: Admin notification sent successfully")
        except Exception as e:
            print(f"DEBUG: Admin notification failed: {e}")

# Handle admin withdrawal actions
@dp.callback_query(F.data.startswith("approve_withdrawal:"))
async def approve_withdrawal(callback: CallbackQuery):
    print(f"DEBUG: Approve withdrawal callback received: {callback.data}")
    
    if callback.from_user.id != settings.admin_id:
        await callback.answer("❌ Siz admin emassiz!")
        return

    withdrawal_id = int(callback.data.split(":")[1])
    print(f"DEBUG: Processing approval for withdrawal ID: {withdrawal_id}")
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(Withdrawal).where(Withdrawal.id == withdrawal_id)
        )
        withdrawal = result.scalar_one_or_none()

        if not withdrawal:
            print(f"DEBUG: Withdrawal not found: {withdrawal_id}")
            await callback.answer("❌ To'lov topilmadi!")
            return

        if withdrawal.status != "pending":
            print(f"DEBUG: Withdrawal already processed: {withdrawal.status}")
            await callback.answer("❌ Bu to'lov allaqachon ko'rib chiqilgan!")
            return

        # Update withdrawal status
        withdrawal.status = "approved"
        withdrawal.processed_at = datetime.utcnow()
        await session.commit()
        print(f"DEBUG: Withdrawal approved successfully")

        # Notify user
        try:
            await callback.bot.send_message(
                withdrawal.user_id,
                f"✅ **TO'LOV TASDIQLANDI**\n\n"
                f"🆔 So'rov ID: {withdrawal.id}\n"
                f"💰 Miqdor: {format_balance(withdrawal.amount)} so'm\n"
                f"💳 Usul: {withdrawal.payment_method}\n"
                f"📅 Tasdiqlangan vaqt: {withdrawal.processed_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"🎉 Pul 1-3 soat ichida hisobingizga o'tadi!"
            )
            print(f"DEBUG: User notification sent for approval")
        except Exception as e:
            print(f"DEBUG: Failed to notify user: {e}")

        await callback.message.edit_text(
            f"✅ **TO'LOV TASDIQLANDI**\n\n"
            f"🆔 So'rov ID: {withdrawal_id}\n"
            f"💰 Miqdor: {format_balance(withdrawal.amount)} so'm\n"
            f"👤 User ID: {withdrawal.user_id}\n"
            f"📅 Vaqt: {withdrawal.processed_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await callback.answer("To'lov tasdiqlandi!")
        print(f"DEBUG: Approval process completed")

@dp.callback_query(F.data.startswith("reject_withdrawal:"))
async def reject_withdrawal(callback: CallbackQuery):
    print(f"DEBUG: Reject withdrawal callback received: {callback.data}")
    
    if callback.from_user.id != settings.admin_id:
        await callback.answer("❌ Siz admin emassiz!")
        return

    withdrawal_id = int(callback.data.split(":")[1])
    print(f"DEBUG: Processing rejection for withdrawal ID: {withdrawal_id}")
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(Withdrawal).where(Withdrawal.id == withdrawal_id)
        )
        withdrawal = result.scalar_one_or_none()

        if not withdrawal:
            print(f"DEBUG: Withdrawal not found: {withdrawal_id}")
            await callback.answer("❌ To'lov topilmadi!")
            return

        if withdrawal.status != "pending":
            print(f"DEBUG: Withdrawal already processed: {withdrawal.status}")
            await callback.answer("❌ Bu to'lov allaqachon ko'rib chiqilgan!")
            return

        # Update withdrawal status and refund balance
        withdrawal.status = "rejected"
        withdrawal.processed_at = datetime.utcnow()
        
        # Refund to user balance
        user_result = await session.execute(
            select(User).where(User.telegram_id == withdrawal.user_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            user.balance += withdrawal.amount
            print(f"DEBUG: Refunded {withdrawal.amount} to user {withdrawal.user_id}")
        
        await session.commit()
        print(f"DEBUG: Withdrawal rejected successfully")

        # Notify user
        try:
            await callback.bot.send_message(
                withdrawal.user_id,
                f"❌ **TO'LOV RAD ETILDI**\n\n"
                f"🆔 So'rov ID: {withdrawal.id}\n"
                f"💰 Miqdor: {format_balance(withdrawal.amount)} so'm\n"
                f"💰 Balansingizga qaytarildi: {format_balance(withdrawal.amount)} so'm\n"
                f"📅 Vaqt: {withdrawal.processed_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"📞 Admin bilan bog'laning: /admin"
            )
            print(f"DEBUG: User notification sent for rejection")
        except Exception as e:
            print(f"DEBUG: Failed to notify user: {e}")

        await callback.message.edit_text(
            f"❌ **TO'LOV RAD ETILDI**\n\n"
            f"🆔 So'rov ID: {withdrawal_id}\n"
            f"💰 Miqdor: {format_balance(withdrawal.amount)} so'm\n"
            f"👤 User ID: {withdrawal.user_id}\n"
            f"💰 Balansga qaytarildi\n"
            f"📅 Vaqt: {withdrawal.processed_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await callback.answer("To'lov rad etildi!")
        print(f"DEBUG: Rejection process completed")

# Admin handlers
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != settings.admin_id:
        await message.answer("❌ Siz admin emassiz!")
        return

    # Get statistics for admin
    async with async_session_maker() as session:
        total_users = await session.scalar(select(func.count(User.id)))
        pending_withdrawals = await session.scalar(
            select(func.count(Withdrawal.id)).where(Withdrawal.status == "pending")
        )
        
    admin_text = f"👨‍💼 **Admin Panel**\n\n"
    admin_text += f"👥 Jami foydalanuvchilar: {total_users}\n"
    admin_text += f"📋 Kutilayotgan to'lovlar: {pending_withdrawals}\n"
    admin_text += f"🎁 Referal mukofoti: {settings.referral_reward} so'm\n"
    admin_text += f"💸 Minimal yechib olish: {settings.minimum_withdrawal} so'm\n\n"
    admin_text += f"🔹 Admin ID: {settings.admin_id}\n"
    admin_text += f"🔹 Bot: @{(await message.bot.get_me()).username}"
    
    await message.answer(admin_text, reply_markup=admin_menu())

@dp.message(F.text == "👥 Foydalanuvchilar")
async def admin_users(message: Message):
    if message.from_user.id != settings.admin_id:
        return

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(20)
        )
        users = result.scalars().all()

        text = "👥 Oxirgi foydalanuvchilar:\n\n"
        
        for user in users:
            # Escape special characters for markdown
            name = (user.first_name or "Noma'lum").replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
            username = (user.username or "none").replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")
            
            text += f"• {name} (@{username})\n"
            text += f"  🆔 ID: `{user.telegram_id}`\n"
            text += f"  💰 Balans: {format_balance(user.balance)} so'm\n"
            text += f"  👥 Referallar: {user.referral_count} ta\n\n"

        text += "💡 **ID larni nusxalash uchun ustiga bosing!**\n\n"
        text += "🔧 **Balans boshqarish uchun:**\n"
        text += "`USER_ID +MIQDOR` yoki `USER_ID -MIQDOR`\n\n"
        text += "📝 **Masalan:**\n"
        text += "`123456789 +1000`"

        await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "💰 Balanslarni boshqarish")
async def admin_balance_management(message: Message):
    if message.from_user.id != settings.admin_id:
        return

    await message.answer(
        "💰 Balans boshqarish:\n\n"
        "Foydalanuvchi ID va miqdorni kiriting:\n\n"
        "Masalan:\n"
        "123456789 +5000 (balansni oshirish)\n"
        "123456789 -3000 (balansni kamaytirish)\n\n"
        "Yoki foydalanuvchi ro'yxatini ko'rish uchun:\n"
        "/users"
    )

# Balance management handler
@dp.message(F.text.regexp(r'^\d+ [+-]\d+$'))
async def process_balance_change(message: Message):
    if message.from_user.id != settings.admin_id:
        return

    try:
        print(f"DEBUG: Balance change request: '{message.text}'")
        parts = message.text.split()
        user_id = int(parts[0])
        change_amount = int(parts[1])  # +5000 yoki -3000
        
        print(f"DEBUG: Processing balance change - User: {user_id}, Amount: {change_amount}")
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await message.answer(f"❌ Foydalanuvchi topilmadi: {user_id}")
                return
            
            old_balance = user.balance
            user.balance += change_amount
            await session.commit()
            
            print(f"DEBUG: Balance updated - Old: {old_balance}, New: {user.balance}")
            
            # Notify user about balance change
            try:
                await message.bot.send_message(
                    user_id,
                    f"💰 Balansingiz o'zgartirildi!\n\n"
                    f"Oldingi balans: {format_balance(old_balance)} so'm\n"
                    f"Yangi balans: {format_balance(user.balance)} so'm\n"
                    f"O'zgarish: {'+' if change_amount > 0 else ''}{format_balance(change_amount)} so'm"
                )
                print(f"DEBUG: User notification sent to {user_id}")
            except Exception as e:
                print(f"DEBUG: Failed to notify user: {e}")
            
            await message.answer(
                f"✅ Balans muvaffaqiyatli o'zgartirildi!\n\n"
                f"👤 Foydalanuvchi: {user.first_name} (@{user.username or 'none'})\n"
                f"🆔 ID: {user_id}\n"
                f"💰 Oldingi balans: {format_balance(old_balance)} so'm\n"
                f"💰 Yangi balans: {format_balance(user.balance)} so'm\n"
                f"📈 O'zgarish: {'+' if change_amount > 0 else ''}{format_balance(change_amount)} so'm"
            )
            print(f"DEBUG: Admin confirmation sent")
            
    except (ValueError, IndexError) as e:
        print(f"DEBUG: Error in balance change: {e}")
        await message.answer(
            "❌ Noto'g'ri format!\n\n"
            "To'g'ri format:\n"
            "123456789 +5000\n"
            "123456789 -3000"
        )
    except Exception as e:
        print(f"DEBUG: Unexpected error: {e}")
        await message.answer(f"❌ Xatolik yuz berdi: {e}")

@dp.message(Command("users"))
async def admin_users_list(message: Message):
    if message.from_user.id != settings.admin_id:
        return

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(10)
        )
        users = result.scalars().all()

        if not users:
            await message.answer("👥 Foydalanuvchilar yo'q!")
            return

        text = "👥 Oxirgi foydalanuvchilar (ID bilan):\n\n"
        for i, user in enumerate(users, 1):
            text += f"{i}. {user.first_name} (@{user.username or 'none'})\n"
            text += f"   🆔 ID: {user.telegram_id}\n"
            text += f"   💰 Balans: {format_balance(user.balance)} so'm\n"
            text += f"   👥 Referallar: {user.referral_count} ta\n\n"

        await message.answer(text)

@dp.message(F.text == "📺 Homiy kanallar")
async def admin_sponsor_channels(message: Message):
    if message.from_user.id != settings.admin_id:
        return

    current_channels = settings.sponsor_channels_list
    if current_channels:
        text = f"📺 Joriy homiy kanallar:\n\n"
        for i, channel in enumerate(current_channels, 1):
            text += f"{i}. {channel}\n"
        text += f"\nJami: {len(current_channels)} ta kanal\n\n"
        text += "🔧 Kanallarni boshqarish:\n"
        text += "• Kanal qo'shish: /addchannel @kanal_nomi\n"
        text += "• Kanal o'chirish: /removechannel @kanal_nomi\n"
        text += "• Barcha kanallarni o'chirish: /clearchannels"
    else:
        text = "📺 Homiy kanallar yo'q\n\n"
        text += "🔧 Kanal qo'shish uchun:\n"
        text += "/addchannel @kanal_nomi"
    
    await message.answer(text)

@dp.message(Command("addchannel"))
async def add_sponsor_channel(message: Message):
    if message.from_user.id != settings.admin_id:
        await message.answer("❌ Siz admin emassiz!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Noto'g'ri format!\n\n"
            "To'g'ri format:\n"
            "/addchannel @kanal_nomi"
        )
        return

    channel = parts[1].strip()
    if not channel.startswith('@'):
        channel = '@' + channel

    # Update channels list
    current_channels = settings.sponsor_channels_list
    if channel in current_channels:
        await message.answer(f"❌ Kanal allaqachon qo'shilgan: {channel}")
        return

    current_channels.append(channel)
    settings.sponsor_channels = ','.join(current_channels)
    
    # Save to .env file
    await save_to_env('SPONSOR_CHANNELS', settings.sponsor_channels)

    await message.answer(
        f"✅ Kanal muvaffaqiyatli qo'shildi va saqlandi!\n\n"
        f"📺 {channel}\n"
        f"📊 Jami kanallar: {len(current_channels)} ta\n"
        f"💾 Bot qayta ishga tushganda ham eslab qolinadi"
    )

@dp.message(Command("removechannel"))
async def remove_sponsor_channel(message: Message):
    if message.from_user.id != settings.admin_id:
        await message.answer("❌ Siz admin emassiz!")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Noto'g'ri format!\n\n"
            "To'g'ri format:\n"
            "/removechannel @kanal_nomi"
        )
        return

    channel = parts[1].strip()
    if not channel.startswith('@'):
        channel = '@' + channel

    # Update channels list
    current_channels = settings.sponsor_channels_list
    if channel not in current_channels:
        await message.answer(f"❌ Kanal topilmadi: {channel}")
        return

    current_channels.remove(channel)
    settings.sponsor_channels = ','.join(current_channels)
    
    # Save to .env file
    await save_to_env('SPONSOR_CHANNELS', settings.sponsor_channels)

    await message.answer(
        f"✅ Kanal muvaffaqiyatli o'chirildi va saqlandi!\n\n"
        f"📺 {channel}\n"
        f"📊 Qolgan kanallar: {len(current_channels)} ta\n"
        f"💾 Bot qayta ishga tushganda ham eslab qolinadi"
    )

@dp.message(Command("clearchannels"))
async def clear_sponsor_channels(message: Message):
    if message.from_user.id != settings.admin_id:
        await message.answer("❌ Siz admin emassiz!")
        return

    settings.sponsor_channels = ""
    
    # Save to .env file
    await save_to_env('SPONSOR_CHANNELS', "")
    
    await message.answer(
        "✅ Barcha homiy kanallar o'chirildi va saqlandi!\n\n"
        "📺 Joriy kanallar: 0 ta\n"
        "🔧 Yangi kanal qo'shish: /addchannel @kanal_nomi\n"
        "💾 Bot qayta ishga tushganda ham eslab qolinadi"
    )

async def save_to_env(key: str, value: str):
    """Save setting to .env file"""
    import os
    env_file = Path('.env')
    
    # Read existing .env content
    if env_file.exists():
        content = env_file.read_text(encoding='utf-8')
    else:
        content = ""
    
    # Update or add the key
    lines = content.split('\n')
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            updated = True
            break
    
    if not updated:
        lines.append(f"{key}={value}")
    
    # Write back to file
    env_file.write_text('\n'.join(lines), encoding='utf-8')

@dp.message(F.text == "⚙️ Sozlamalar")
async def admin_settings(message: Message):
    if message.from_user.id != settings.admin_id:
        return

    text = "⚙️ Bot sozlamalari:\n\n"
    text += f"🎁 Referal mukofoti: {settings.referral_reward} so'm\n"
    text += f"💸 Minimal yechib olish: {settings.minimum_withdrawal} so'm\n"
    text += f"📺 Homiy kanallar: {len(settings.sponsor_channels_list)} ta\n"
    text += f"👨‍💼 Admin ID: {settings.admin_id}\n"
    
    await message.answer(text)

@dp.message(F.text == "📋 To'lov so'rovlari")
async def admin_withdrawals(message: Message):
    if message.from_user.id != settings.admin_id:
        return

    async with async_session_maker() as session:
        result = await session.execute(
            select(Withdrawal).where(Withdrawal.status == "pending").order_by(Withdrawal.created_at.desc())
        )
        withdrawals = result.scalars().all()

        if not withdrawals:
            await message.answer("📋 Kutilayotgan to'lov so'rovlari yo'q.")
            return

        text = "📋 To'lov so'rovlari:\n\n"
        for withdrawal in withdrawals:
            text += f"ID: {withdrawal.id}\n"
            text += f"User ID: {withdrawal.user_id}\n"
            text += f"Miqdor: {format_balance(withdrawal.amount)} so'm\n"
            text += f"Usul: {withdrawal.payment_method}\n"
            text += f"Status: {withdrawal.status}\n\n"

        await message.answer(text)

@dp.message(F.text == "📊 Statistika")
async def admin_statistics(message: Message):
    if message.from_user.id != settings.admin_id:
        return

    async with async_session_maker() as session:
        # Total users
        total_users = await session.scalar(select(func.count(User.id)))
        
        # Active users (with referrals)
        active_users = await session.scalar(
            select(func.count(User.id)).where(User.referral_count > 0)
        )
        
        # Total withdrawals
        total_withdrawals = await session.scalar(
            select(func.count(Withdrawal.id)).where(Withdrawal.status == "approved")
        )
        
        # Total withdrawn amount
        total_withdrawn = await session.scalar(
            select(func.coalesce(func.sum(Withdrawal.amount), 0)).where(Withdrawal.status == "approved")
        )

        text = "📊 Bot statistikasi:\n\n"
        text += f"👥 Jami foydalanuvchilar: {total_users}\n"
        text += f"🔥 Faol foydalanuvchilar: {active_users}\n"
        text += f"💸 Jami to'lovlar: {total_withdrawals}\n"
        text += f"💰 Jami yechib olingan: {format_balance(total_withdrawn)} so'm\n"
        text += f"🎁 Referal mukofoti: {format_balance(settings.referral_reward)} so'm"

        await message.answer(text)

# ==================== MAIN ====================
async def main():
    await init_db()
    bot = Bot(token=settings.bot_token)
    
    # NO manual registration - let aiogram handle it automatically
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
