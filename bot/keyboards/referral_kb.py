from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def referral_kb(bot_username: str, user_id: int) -> InlineKeyboardMarkup:
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Поделиться ссылкой", url=f"https://t.me/share/url?url={ref_link}&text=Ищи свободные Telegram-ники!")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")],
    ])
