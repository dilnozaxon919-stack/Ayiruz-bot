from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="👥 Referallarim"), KeyboardButton(text="💰 Hisobim")],
        [KeyboardButton(text="🙍 Profil"), KeyboardButton(text="💸 Chiqarib olish")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="⚙️ Admin")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def subscribe_keyboard(channels) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        link = ch["chat_id"]
        if not str(link).startswith("http") and not str(link).startswith("@"):
            link = f"https://t.me/{link.lstrip('@')}"
        elif str(link).startswith("@"):
            link = f"https://t.me/{link.lstrip('@')}"
        buttons.append([InlineKeyboardButton(text=f"📢 {ch['title'] or ch['chat_id']}", url=link)])
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_menu() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="➕ Majburiy kanal qo'shish", callback_data="admin_add_channel")],
        [InlineKeyboardButton(text="📋 Kanallar ro'yxati / o'chirish", callback_data="admin_list_channels")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def channels_remove_keyboard(channels) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ {ch['title'] or ch['chat_id']}",
                callback_data=f"admin_remove_channel:{ch['id']}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def withdraw_decision_keyboard(withdrawal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ To'landi", callback_data=f"wd_approve:{withdrawal_id}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"wd_reject:{withdrawal_id}"),
            ]
        ]
    )
