from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def premium_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Купить Premium", callback_data="buy_sub_premium")],
        [InlineKeyboardButton(text="👑 Купить Luxe", callback_data="buy_sub_luxe")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")],
    ])


def sub_prices_kb(prices: dict, sub_type: str) -> InlineKeyboardMarkup:
    labels = {"1": "1 день", "3": "3 дня", "10": "10 дней", "30": "30 дней"}
    buttons = []
    for days, label in labels.items():
        if days in prices:
            p = prices[days]
            buttons.append([
                InlineKeyboardButton(
                    text=f"⭐ {label} — {p['stars']} Stars / {p['rub']}₽",
                    callback_data=f"buy_{sub_type}_{days}"
                )
            ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu_premium")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
