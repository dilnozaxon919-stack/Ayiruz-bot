import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)

dp = Dispatcher()


menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🔄 Ayirboshlash"),
            KeyboardButton(text="📦 E'lon berish")
        ],
        [
            KeyboardButton(text="🛒 Market"),
            KeyboardButton(text="📋 Mening e'lonlarim")
        ],
        [
            KeyboardButton(text="👤 Profil"),
            KeyboardButton(text="🏆 Reyting")
        ],
        [
            KeyboardButton(text="🌐 Til o'zgartirish")
        ]
    ],
    resize_keyboard=True
)


@dp.message(Command("start"))
async def start(message: Message):

    await message.answer(
        "Assalomu alaykum 👋\n\n"
        "Ayir.uz platformasiga xush kelibsiz 🚀\n\n"
        "Tilni tanlang:",
    )


@dp.message(F.text == "🇺🇿 O'zbek")
async def uz(message: Message):

    await message.answer(
        "Ayir.uz tayyor ✅\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=menu
    )


@dp.message(F.text == "🔄 Ayirboshlash")
async def exchange(message: Message):

    await message.answer(
        "🔄 Ayirboshlash bo‘limi\n\n"
        "Tez orada xavfsiz savdo tizimi ishlaydi."
    )


@dp.message(F.text == "📦 E'lon berish")
async def listing(message: Message):

    await message.answer(
        "📦 E'lon berish\n\n"
        "Siz mahsulot yoki aktiv joylashingiz mumkin."
    )


@dp.message(F.text == "🛒 Market")
async def market(message: Message):

    await message.answer(
        "🛒 Market\n\n"
        "Telegram Premium, Stars va Gift bo‘limlari."
    )


@dp.message(F.text == "👤 Profil")
async def profile(message: Message):

    await message.answer(
        "👤 Profil\n\n"
        "Reyting va savdolar tarixi."
    )


async def main():

    print("Ayir.uz bot ishga tushdi")

    await dp.start_polling(bot)


if name == "main":
    asyncio.run(main())
