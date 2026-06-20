from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Цены Premium", callback_data="admin_prices")],
        [InlineKeyboardButton(text="👑 Цены Luxe", callback_data="admin_luxe_prices")],
        [InlineKeyboardButton(text="📦 Цена доп. попыток", callback_data="admin_bulk_price")],
        [InlineKeyboardButton(text="👥 Настройки рефералов", callback_data="admin_refs")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin_promos")],
        [InlineKeyboardButton(text="👤 Управление пользователями", callback_data="admin_users")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔗 Добавить сессию", callback_data="admin_add_session")],
        [InlineKeyboardButton(text="📺 Зарегистрировать канал", callback_data="admin_register_channel")],
        [InlineKeyboardButton(text="📋 Зарегистрированные каналы", callback_data="admin_list_channels")],
        [InlineKeyboardButton(text="❌ Выйти из админки", callback_data="back_to_menu")],
    ])


def admin_prices_kb(prices: dict, prefix: str = "admin_edit_price") -> InlineKeyboardMarkup:
    labels = {"1": "1 день", "3": "3 дня", "10": "10 дней", "30": "30 дней"}
    buttons = []
    for days, label in labels.items():
        if days in prices:
            p = prices[days]
            buttons.append([InlineKeyboardButton(
                text=f"✏️ {label}: {p['stars']}⭐",
                callback_data=f"{prefix}_{days}"
            )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_refs_kb(rewards: dict) -> InlineKeyboardMarkup:
    buttons = []
    for refs, days in sorted(rewards.items(), key=lambda x: int(x[0])):
        buttons.append([InlineKeyboardButton(
            text=f"✏️ {refs} рефералов → {days} дн.",
            callback_data=f"admin_edit_ref_{refs}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_promos_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="📋 Список промокодов", callback_data="admin_list_promos")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")],
    ])


def admin_users_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выдать Premium", callback_data="admin_give_premium")],
        [InlineKeyboardButton(text="👑 Выдать Luxe", callback_data="admin_give_luxe")],
        [InlineKeyboardButton(text="❌ Снять подписку", callback_data="admin_revoke_sub")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")],
    ])


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
    ])


def cancel_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel")]
    ])


def channel_menu_kb(channel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Убрать юзернейм", callback_data=f"chan_remove_user_{channel_id}")],
        [InlineKeyboardButton(text="💥 Удалить канал", callback_data=f"chan_delete_{channel_id}")],
        [InlineKeyboardButton(text="🔄 Передать канал", callback_data=f"chan_transfer_{channel_id}")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="admin_list_channels")],
    ])


def channels_list_kb(channels: list) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        uname = ch["channel_username"] or "—"
        title = ch["channel_title"] or str(ch["channel_id"])
        buttons.append([InlineKeyboardButton(
            text=f"📺 {title} (@{uname})",
            callback_data=f"chan_view_{ch['channel_id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
