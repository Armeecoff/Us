from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def search_sections_kb(is_premium: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🔒 5 букв" if not is_premium else "5 букв",
                callback_data="search_5" if is_premium else "search_locked_5"
            ),
            InlineKeyboardButton(text="6 букв", callback_data="search_6"),
        ],
        [
            InlineKeyboardButton(
                text="🔒 Фильтр" if not is_premium else "🎭 Фильтр",
                callback_data="search_filter" if is_premium else "search_locked_filter"
            ),
            InlineKeyboardButton(
                text="🔒 Ловушка" if not is_premium else "🪤 Ловушка",
                callback_data="search_trap" if is_premium else "search_locked_trap"
            ),
        ],
    ]
    if is_premium:
        rows.append([
            InlineKeyboardButton(text="📦 Массовый поиск", callback_data="search_bulk")
        ])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def search_6_options_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="• Без цифр", callback_data="search_6_no_digits"),
            InlineKeyboardButton(text="🔍 С цифрами", callback_data="search_6_digits"),
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_search")],
    ])


def search_5_options_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="• Без цифр", callback_data="search_5_no_digits"),
            InlineKeyboardButton(text="🔍 С цифрами", callback_data="search_5_digits"),
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_search")],
    ])


def bulk_options_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="5 букв (без цифр)", callback_data="bulk_5_no"),
            InlineKeyboardButton(text="5 букв (с цифрами)", callback_data="bulk_5_yes"),
        ],
        [
            InlineKeyboardButton(text="6 букв (без цифр)", callback_data="bulk_6_no"),
            InlineKeyboardButton(text="6 букв (с цифрами)", callback_data="bulk_6_yes"),
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_search")],
    ])


def bulk_buy_extra_kb(stars: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"⭐ Докупить 5 попыток — {stars} Stars",
            callback_data="bulk_buy_extra"
        )],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_search")],
    ])


def trap_manage_kb(traps: list) -> InlineKeyboardMarkup:
    buttons = []
    for trap in traps:
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ @{trap['target_username']}",
                callback_data=f"trap_delete_{trap['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="➕ Добавить ловушку", callback_data="trap_add")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="menu_search")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_kb(back_cb: str = "menu_search") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=back_cb)]
    ])
