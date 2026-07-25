import asyncio
import logging

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiohttp import web

import config
import db
import keyboards as kb

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("uc_bot")

router = Router()


# ---------------- FSM holatlar ----------------

class Withdraw(StatesGroup):
    amount = State()
    pubg_id = State()


class AdminAddChannel(StatesGroup):
    waiting_channel = State()


class AdminAddAdmin(StatesGroup):
    waiting_user_id = State()


# ---------------- Yordamchi funksiyalar ----------------

def is_super_admin(user_id: int) -> bool:
    """Faqat .env / Render Environment Variables orqali belgilangan bosh adminlar."""
    return user_id in config.ADMIN_IDS


async def is_admin(user_id: int) -> bool:
    """Super admin yoki bosh admin tomonidan tayinlangan oddiy admin."""
    if is_super_admin(user_id):
        return True
    return await db.is_db_admin(user_id)


async def get_not_joined_channels(bot: Bot, user_id: int):
    channels = await db.list_channels()
    not_joined = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["chat_id"], user_id=user_id)
            if member.status in ("left", "kicked"):
                not_joined.append(ch)
        except TelegramBadRequest:
            # bot o'sha kanalda admin emas yoki chat_id noto'g'ri — xavfsizlik uchun talab qilinmaydi deb hisoblanadi
            log.warning("Kanal tekshirib bo'lmadi: %s", ch["chat_id"])
    return not_joined


async def send_subscribe_prompt(message: Message, not_joined):
    await message.answer(
        "❗️ Botdan foydalanish uchun quyidagi kanal(lar)ga a'zo bo'ling, so'ng "
        "\"✅ Tekshirish\" tugmasini bosing:",
        reply_markup=kb.subscribe_keyboard(not_joined),
    )


# ---------------- /start ----------------

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name or ""

    ref_id = None
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].strip().isdigit():
        ref_id = int(args[1].strip())

    await db.create_user_if_not_exists(user_id, username, full_name, ref_id)

    not_joined = await get_not_joined_channels(message.bot, user_id)
    if not_joined:
        await send_subscribe_prompt(message, not_joined)
        return

    referrer_id = await db.mark_verified_and_reward(user_id, config.REFERRAL_BONUS)
    if referrer_id:
        try:
            await message.bot.send_message(
                referrer_id,
                f"🎉 Sizning referal havolangiz orqali yangi foydalanuvchi qo'shildi!\n"
                f"+{config.REFERRAL_BONUS} UC hisobingizga qo'shildi.",
            )
        except TelegramBadRequest:
            pass

    await message.answer(
        "🎮 Xush kelibsiz! Bu bot orqali do'stlaringizni taklif qilib UC ishlashingiz mumkin.\n\n"
        f"— Har bir taklif qilingan do'stingiz uchun: {config.REFERRAL_BONUS} UC\n"
        f"— Eng kam chiqarib olish miqdori: {config.MIN_WITHDRAW} UC\n\n"
        "Quyidagi menyudan foydalaning 👇",
        reply_markup=kb.main_menu(await is_admin(user_id)),
    )


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(call: CallbackQuery):
    user_id = call.from_user.id
    not_joined = await get_not_joined_channels(call.bot, user_id)
    if not_joined:
        await call.answer("❌ Hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
        return

    await call.message.delete()
    referrer_id = await db.mark_verified_and_reward(user_id, config.REFERRAL_BONUS)
    if referrer_id:
        try:
            await call.bot.send_message(
                referrer_id,
                f"🎉 Sizning referal havolangiz orqali yangi foydalanuvchi qo'shildi!\n"
                f"+{config.REFERRAL_BONUS} UC hisobingizga qo'shildi.",
            )
        except TelegramBadRequest:
            pass

    await call.message.answer(
        "✅ Rahmat! Endi botdan to'liq foydalanishingiz mumkin.",
        reply_markup=kb.main_menu(await is_admin(user_id)),
    )
    await call.answer()


# ---------------- Har bir xabarda majburiy obunani tekshirish ----------------

async def ensure_subscribed(message: Message) -> bool:
    not_joined = await get_not_joined_channels(message.bot, message.from_user.id)
    if not_joined:
        await send_subscribe_prompt(message, not_joined)
        return False
    return True


# ---------------- Referallarim ----------------

@router.message(F.text == "👥 Referallarim")
async def menu_referrals(message: Message):
    if not await ensure_subscribed(message):
        return
    user = await db.get_user(message.from_user.id)
    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
    ref_count = user["ref_count"] if user else 0
    earned = ref_count * config.REFERRAL_BONUS
    await message.answer(
        "👥 <b>Referallarim</b>\n\n"
        f"🔗 Sizning havolangiz:\n{link}\n\n"
        f"👤 Taklif qilinganlar soni: <b>{ref_count}</b>\n"
        f"💎 Referaldan ishlangan: <b>{earned} UC</b>",
        parse_mode="HTML",
    )


# ---------------- Hisobim ----------------

@router.message(F.text == "💰 Hisobim")
async def menu_balance(message: Message):
    if not await ensure_subscribed(message):
        return
    balance = await db.get_balance(message.from_user.id)
    await message.answer(
        f"💰 <b>Hisobingiz</b>\n\nJoriy balans: <b>{balance} UC</b>\n"
        f"Eng kam chiqarib olish: {config.MIN_WITHDRAW} UC",
        parse_mode="HTML",
    )


# ---------------- Profil ----------------

@router.message(F.text == "🙍 Profil")
async def menu_profile(message: Message):
    if not await ensure_subscribed(message):
        return
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Ma'lumot topilmadi, /start bosing.")
        return
    await message.answer(
        "🙍 <b>Profil</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"👤 Username: @{user['username'] or '—'}\n"
        f"💰 Balans: {user['balance']} UC\n"
        f"👥 Referallar soni: {user['ref_count']}\n"
        f"📅 Ro'yxatdan o'tgan: {user['created_at'].strftime('%d.%m.%Y')}",
        parse_mode="HTML",
    )


# ---------------- Chiqarib olish ----------------

@router.message(F.text == "💸 Chiqarib olish")
async def menu_withdraw_start(message: Message, state: FSMContext):
    if not await ensure_subscribed(message):
        return
    balance = await db.get_balance(message.from_user.id)
    if balance < config.MIN_WITHDRAW:
        await message.answer(
            f"❌ Chiqarib olish uchun kamida {config.MIN_WITHDRAW} UC kerak.\n"
            f"Sizning joriy balansingiz: {balance} UC."
        )
        return
    await message.answer(
        f"💸 Chiqarib olmoqchi bo'lgan UC miqdorini kiriting.\n"
        f"(Balansingiz: {balance} UC, eng kami: {config.MIN_WITHDRAW} UC)"
    )
    await state.set_state(Withdraw.amount)


@router.message(Withdraw.amount)
async def withdraw_amount(message: Message, state: FSMContext):
    text = (message.text or "").replace(",", ".").strip()
    try:
        amount = float(text)
    except ValueError:
        await message.answer("❌ Faqat son kiriting. Masalan: 30")
        return

    balance = await db.get_balance(message.from_user.id)
    if amount < config.MIN_WITHDRAW:
        await message.answer(f"❌ Eng kam miqdor {config.MIN_WITHDRAW} UC. Qaytadan kiriting:")
        return
    if amount > balance:
        await message.answer(
            f"❌ Balansingizda yetarli mablag' yo'q. Joriy balans: {balance} UC. Qaytadan kiriting:"
        )
        return

    await state.update_data(amount=amount)
    await message.answer("🎮 Endi PUBG Mobile ID raqamingizni yuboring:")
    await state.set_state(Withdraw.pubg_id)


@router.message(Withdraw.pubg_id)
async def withdraw_pubg_id(message: Message, state: FSMContext):
    pubg_id = (message.text or "").strip()
    if not pubg_id or not pubg_id.isdigit():
        await message.answer("❌ PUBG ID faqat raqamlardan iborat bo'lishi kerak. Qaytadan yuboring:")
        return

    data = await state.get_data()
    amount = data["amount"]
    user_id = message.from_user.id

    balance = await db.get_balance(user_id)
    if amount > balance:
        await message.answer("❌ Balansingiz o'zgargan, so'rovni qaytadan yuboring.")
        await state.clear()
        return

    # mablag'ni darhol ushlab qolamiz (admin rad etsa qaytariladi)
    await db.change_balance(user_id, -amount)
    withdrawal_id = await db.create_withdrawal(user_id, amount, pubg_id)
    await state.clear()

    await message.answer(
        "⏳ So'rovingiz qabul qilindi va jarayonda. Tez orada UC hisobingizga (PUBG ID) o'tkaziladi.",
        reply_markup=kb.main_menu(await is_admin(user_id)),
    )

    username = f"@{message.from_user.username}" if message.from_user.username else "—"
    for admin_id in config.ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                "💸 <b>Yangi chiqarib olish so'rovi</b>\n\n"
                f"🆔 So'rov raqami: #{withdrawal_id}\n"
                f"👤 Foydalanuvchi: {username} (<code>{user_id}</code>)\n"
                f"💎 Miqdor: {amount} UC\n"
                f"🎮 PUBG ID: <code>{pubg_id}</code>",
                parse_mode="HTML",
                reply_markup=kb.withdraw_decision_keyboard(withdrawal_id),
            )
        except TelegramBadRequest:
            pass


@router.callback_query(F.data.startswith("wd_approve:"))
async def wd_approve(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        await call.answer("Sizga ruxsat yo'q.", show_alert=True)
        return
    withdrawal_id = int(call.data.split(":")[1])
    wd = await db.get_withdrawal(withdrawal_id)
    if not wd or wd["status"] != "pending":
        await call.answer("Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    await db.set_withdrawal_status(withdrawal_id, "approved")
    await call.message.edit_text(call.message.text + "\n\n✅ TO'LANDI", reply_markup=None)
    try:
        await call.bot.send_message(
            wd["user_id"],
            f"✅ So'rovingiz (#{withdrawal_id}, {wd['amount']} UC) tasdiqlandi va UC hisobingizga o'tkazildi!",
        )
    except TelegramBadRequest:
        pass
    await call.answer("Tasdiqlandi ✅")


@router.callback_query(F.data.startswith("wd_reject:"))
async def wd_reject(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        await call.answer("Sizga ruxsat yo'q.", show_alert=True)
        return
    withdrawal_id = int(call.data.split(":")[1])
    wd = await db.get_withdrawal(withdrawal_id)
    if not wd or wd["status"] != "pending":
        await call.answer("Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    await db.set_withdrawal_status(withdrawal_id, "rejected")
    await db.change_balance(wd["user_id"], float(wd["amount"]))  # mablag' qaytariladi
    await call.message.edit_text(call.message.text + "\n\n❌ BEKOR QILINDI (mablag' qaytarildi)", reply_markup=None)
    try:
        await call.bot.send_message(
            wd["user_id"],
            f"❌ So'rovingiz (#{withdrawal_id}, {wd['amount']} UC) bekor qilindi. Mablag' hisobingizga qaytarildi.",
        )
    except TelegramBadRequest:
        pass
    await call.answer("Bekor qilindi ❌")


# ---------------- Admin panel ----------------

@router.message(F.text == "⚙️ Admin")
async def menu_admin(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer(
        "⚙️ <b>Admin panel</b>", parse_mode="HTML",
        reply_markup=kb.admin_menu(is_super_admin(message.from_user.id)),
    )


@router.callback_query(F.data == "admin_back")
async def admin_back(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return
    await call.message.edit_text(
        "⚙️ <b>Admin panel</b>", parse_mode="HTML",
        reply_markup=kb.admin_menu(is_super_admin(call.from_user.id)),
    )
    await call.answer()


@router.callback_query(F.data == "admin_add_channel")
async def admin_add_channel(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return
    await call.message.answer(
        "➕ Majburiy obuna qilinadigan kanalni yuboring.\n\n"
        "Kanal <b>username</b>i (masalan <code>@mening_kanalim</code>) yoki "
        "kanal <b>ID</b>si (masalan <code>-1001234567890</code>) shaklida yuboring.\n\n"
        "❗️ Bot o'sha kanalda <b>admin</b> bo'lishi shart, aks holda obunani tekshira olmaydi.",
        parse_mode="HTML",
    )
    await state.set_state(AdminAddChannel.waiting_channel)
    await call.answer()


@router.message(AdminAddChannel.waiting_channel)
async def admin_add_channel_save(message: Message, state: FSMContext):
    chat_id = message.text.strip()
    try:
        chat = await message.bot.get_chat(chat_id)
        title = chat.title or chat.username or chat_id
    except TelegramBadRequest:
        await message.answer(
            "❌ Kanal topilmadi yoki bot u yerda admin emas. Qaytadan urinib ko'ring, "
            "yoki botni o'sha kanalga admin qilib qo'shing."
        )
        return

    await db.add_channel(chat_id, title)
    await state.clear()
    await message.answer(
        f"✅ Kanal qo'shildi: {title}",
        reply_markup=kb.admin_menu(is_super_admin(message.from_user.id)),
    )


@router.callback_query(F.data == "admin_list_channels")
async def admin_list_channels(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return
    channels = await db.list_channels()
    if not channels:
        await call.message.edit_text(
            "📋 Hozircha majburiy kanallar yo'q.",
            reply_markup=kb.admin_menu(is_super_admin(call.from_user.id)),
        )
        await call.answer()
        return
    await call.message.edit_text(
        "📋 Majburiy kanallar ro'yxati (o'chirish uchun bosing):",
        reply_markup=kb.channels_remove_keyboard(channels),
    )
    await call.answer()


@router.callback_query(F.data.startswith("admin_remove_channel:"))
async def admin_remove_channel(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return
    channel_id = int(call.data.split(":")[1])
    await db.remove_channel(channel_id)
    channels = await db.list_channels()
    if not channels:
        await call.message.edit_text(
            "📋 Hozircha majburiy kanallar yo'q.",
            reply_markup=kb.admin_menu(is_super_admin(call.from_user.id)),
        )
    else:
        await call.message.edit_text(
            "📋 Majburiy kanallar ro'yxati (o'chirish uchun bosing):",
            reply_markup=kb.channels_remove_keyboard(channels),
        )
    await call.answer("O'chirildi ✅")


@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return
    stats = await db.get_stats()
    await call.message.answer(
        "📊 <b>Statistika</b>\n\n"
        f"👤 Jami foydalanuvchilar: {stats['total_users']}\n"
        f"💸 To'langan (tasdiqlangan): {stats['total_paid']} UC\n"
        f"⏳ Kutilayotgan so'rovlar: {stats['pending']}",
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "admin_add_admin")
async def admin_add_admin(call: CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        await call.answer("Bu faqat bosh adminlarga ruxsat etilgan.", show_alert=True)
        return
    await call.message.answer(
        "👑 Admin qilib tayinlamoqchi bo'lgan foydalanuvchining Telegram ID raqamini yuboring.\n"
        "(ID'ni bilish uchun @userinfobot'dan foydalanish mumkin)"
    )
    await state.set_state(AdminAddAdmin.waiting_user_id)
    await call.answer()


@router.message(AdminAddAdmin.waiting_user_id)
async def admin_add_admin_save(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("❌ Faqat raqamlardan iborat Telegram ID yuboring. Qaytadan urinib ko'ring:")
        return

    new_admin_id = int(text)
    if is_super_admin(new_admin_id):
        await message.answer("Bu foydalanuvchi allaqachon bosh admin.")
        await state.clear()
        return

    await db.add_admin(new_admin_id, added_by=message.from_user.id)
    await state.clear()
    await message.answer(
        f"✅ <code>{new_admin_id}</code> endi admin.",
        parse_mode="HTML",
        reply_markup=kb.admin_menu(is_super_admin(message.from_user.id)),
    )
    try:
        await message.bot.send_message(new_admin_id, "👑 Sizga botda admin huquqi berildi!")
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "admin_list_admins")
async def admin_list_admins(call: CallbackQuery):
    if not is_super_admin(call.from_user.id):
        await call.answer("Bu faqat bosh adminlarga ruxsat etilgan.", show_alert=True)
        return
    admins = await db.list_admins()
    if not admins:
        await call.message.edit_text(
            "🗑 Hozircha tayinlangan qo'shimcha adminlar yo'q.",
            reply_markup=kb.admin_menu(True),
        )
        await call.answer()
        return
    await call.message.edit_text(
        "🗑 Tayinlangan adminlar ro'yxati (o'chirish uchun bosing):",
        reply_markup=kb.admins_remove_keyboard(admins),
    )
    await call.answer()


@router.callback_query(F.data.startswith("admin_remove_admin:"))
async def admin_remove_admin(call: CallbackQuery):
    if not is_super_admin(call.from_user.id):
        await call.answer("Bu faqat bosh adminlarga ruxsat etilgan.", show_alert=True)
        return
    target_id = int(call.data.split(":")[1])
    await db.remove_admin(target_id)
    admins = await db.list_admins()
    if not admins:
        await call.message.edit_text(
            "🗑 Hozircha tayinlangan qo'shimcha adminlar yo'q.",
            reply_markup=kb.admin_menu(True),
        )
    else:
        await call.message.edit_text(
            "🗑 Tayinlangan adminlar ro'yxati (o'chirish uchun bosing):",
            reply_markup=kb.admins_remove_keyboard(admins),
        )
    try:
        await call.bot.send_message(target_id, "❌ Sizning admin huquqingiz bekor qilindi.")
    except TelegramBadRequest:
        pass
    await call.answer("O'chirildi ✅")


# ---------------- Render uchun oddiy web server (UptimeRobot shu yerga ping yuboradi) ----------------

async def handle_ping(request):
    return web.Response(text="Bot ishlab turibdi ✅")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=config.PORT)
    await site.start()
    log.info("Web server %s portda ishga tushdi", config.PORT)


# ---------------- Ishga tushirish ----------------

async def main():
    if not config.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi! Render'da Environment Variable qo'ying.")
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL topilmadi! Supabase ulanish manzilini qo'ying.")

    await db.init_db()
    log.info("Baza tayyor.")

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await start_web_server()

    await bot.delete_webhook(drop_pending_updates=True)
    log.info("Bot polling boshlanmoqda...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
