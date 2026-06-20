from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def profile_kb(is_premium: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🎟 Промокод", callback_data="profile_promo")],
    ]
    if is_premium:
        rows.append([InlineKeyboardButton(text="📋 История ников", callback_data="profile_history")])
    rows.append([InlineKeyboardButton(text="ℹ️ Информация", callback_data="profile_info")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu_profile")]
    ])
