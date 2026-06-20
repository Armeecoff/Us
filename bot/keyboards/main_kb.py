from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import ADMIN_IDS


def main_menu_kb(user_id: int = 0, is_luxe: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="🔍 Поиск", callback_data="menu_search"),
            InlineKeyboardButton(text="💎 Премиум", callback_data="menu_premium"),
        ],
        [
            InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"),
            InlineKeyboardButton(text="👥 Рефералы", callback_data="menu_referrals"),
        ],
    ]
    if is_luxe or user_id in ADMIN_IDS:
        rows.append([InlineKeyboardButton(text="🌐 API Luxe", callback_data="menu_api_info")])
    if user_id in ADMIN_IDS:
        rows.append([InlineKeyboardButton(text="🔧 Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
    ])
