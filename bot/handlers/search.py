import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database import (
    get_user, is_premium, is_luxe, get_today_searches, increment_search,
    increment_found, save_found_username, add_trap, get_user_traps, delete_trap
)
from bot.config import FREE_DAILY_ATTEMPTS
from bot.keyboards.search_kb import (
    search_sections_kb, search_6_options_kb, search_5_options_kb,
    trap_manage_kb, cancel_kb
)
from bot.utils.username_checker import find_free_username

router = Router()

TRAP_INTERVAL_FREE = 1800      # 30 мин
TRAP_INTERVAL_PREMIUM_MIN = 900  # 15 мин
TRAP_INTERVAL_LUXE_MIN = 600     # 10 мин


class SearchStates(StatesGroup):
    waiting_mask = State()
    waiting_trap_username = State()
    waiting_trap_interval = State()
    waiting_rating_length = State()


async def get_attempts(user_id: int):
    prem = await is_premium(user_id)
    if prem:
        return True, 999, 999
    used = await get_today_searches(user_id)
    remaining = FREE_DAILY_ATTEMPTS - used
    return remaining > 0, remaining, FREE_DAILY_ATTEMPTS


def trap_interval_kb(is_premium_user: bool, is_luxe_user: bool) -> InlineKeyboardMarkup:
    buttons = []
    if is_luxe_user:
        buttons.append([InlineKeyboardButton(text="⚡️ 10 мин (Luxe)", callback_data="trap_interval_600")])
        buttons.append([InlineKeyboardButton(text="🔥 15 мин (Premium)", callback_data="trap_interval_900")])
        buttons.append([InlineKeyboardButton(text="🕐 30 мин", callback_data="trap_interval_1800")])
    elif is_premium_user:
        buttons.append([InlineKeyboardButton(text="🔥 15 мин (Premium)", callback_data="trap_interval_900")])
        buttons.append([InlineKeyboardButton(text="🕐 30 мин", callback_data="trap_interval_1800")])
    else:
        buttons.append([InlineKeyboardButton(text="🕐 30 мин (по умолчанию)", callback_data="trap_interval_1800")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="search_trap")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "menu_search")
async def menu_search(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = call.from_user.id
    prem = await is_premium(user_id)
    can, remaining, total = await get_attempts(user_id)

    attempts_text = "♾️ Безлимитный поиск" if prem else f"🔗 Осталось попыток сегодня: {remaining}"

    await call.message.edit_text(
        "💎 <b>ПОИСК ЮЗЕРНЕЙМА</b>\n\n"
        "✅ Каждый найденный ник проходит двойную проверку:\n"
        "• Telegram API — не занят профилем, каналом или ботом\n"
        "• Fragment — не выставлен на аукцион или продажу\n\n"
        f"{attempts_text}\n\n"
        "Выберите раздел 👇",
        reply_markup=search_sections_kb(prem),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.in_({"search_locked_5", "search_locked_filter", "search_locked_trap"}))
async def search_locked(call: CallbackQuery):
    await call.answer("🔒 Только для Premium!", show_alert=True)


@router.callback_query(F.data == "search_6")
async def search_6(call: CallbackQuery):
    can, remaining, total = await get_attempts(call.from_user.id)
    prem = await is_premium(call.from_user.id)
    if not can:
        await call.answer("❌ Попытки исчерпаны! Купите Premium.", show_alert=True)
        return
    attempts_text = "♾️ Осталось: безлимит" if prem else f"🎯 Осталось: {remaining}"
    await call.message.edit_text(
        f"💎 <b>Поиск 6 букв</b>\n\nНайти юз с цифрами или без?\n\n{attempts_text}",
        reply_markup=search_6_options_kb(), parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "search_5")
async def search_5(call: CallbackQuery):
    can, remaining, _ = await get_attempts(call.from_user.id)
    if not can:
        await call.answer("❌ Попытки исчерпаны!", show_alert=True)
        return
    await call.message.edit_text(
        "💎 <b>Поиск 5 букв (Premium)</b>\n\nНайти юз с цифрами или без?\n\n♾️ Осталось: безлимит",
        reply_markup=search_5_options_kb(), parse_mode="HTML"
    )
    await call.answer()


async def do_search(call: CallbackQuery, length: int, with_digits: bool, min_rating: int = 1):
    user_id = call.from_user.id
    can, remaining, total = await get_attempts(user_id)
    if not can:
        await call.answer("❌ Попытки исчерпаны! Купите Premium.", show_alert=True)
        return

    digits_text = "с цифрами" if with_digits else "без цифр"
    rating_text = f", рейтинг {min_rating}+" if min_rating > 1 else ""
    await call.message.edit_text(
        f"🔍 <b>Ищу {length}-буквенный ник ({digits_text}{rating_text})...</b>\n\n"
        "⏳ Двойная проверка: Telegram API + Fragment",
        parse_mode="HTML"
    )
    await call.answer()

    await increment_search(user_id)
    result = await find_free_username(length, with_digits, min_rating=min_rating)

    prem = await is_premium(user_id)
    if result:
        username, rating = result
        await increment_found(user_id)
        await save_found_username(user_id, username, length, rating)
        used = await get_today_searches(user_id)
        remaining_new = "♾️ безлимит" if prem else str(FREE_DAILY_ATTEMPTS - used)
        stars_str = "⭐" * rating + "☆" * (10 - rating)
        await call.message.edit_text(
            f"✅ <b>Найден свободный ник!</b>\n\n"
            f"📛 <code>@{username}</code>\n"
            f"🔤 Длина: {len(username)} символов\n"
            f"📊 Рейтинг: {rating}/10 {stars_str}\n\n"
            f"✅ Проверен в Telegram API\n"
            f"✅ Проверен в Fragment\n\n"
            f"🎯 Осталось попыток: {remaining_new}\n"
            f"👆 t.me/{username}",
            reply_markup=search_sections_kb(prem),
            parse_mode="HTML"
        )
    else:
        await call.message.edit_text(
            "❌ <b>Не удалось найти свободный ник</b>\n\nПопробуйте ещё раз.",
            reply_markup=search_sections_kb(prem),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "search_6_no_digits")
async def s6nd(call: CallbackQuery): await do_search(call, 6, False)

@router.callback_query(F.data == "search_6_digits")
async def s6d(call: CallbackQuery): await do_search(call, 6, True)

@router.callback_query(F.data == "search_5_no_digits")
async def s5nd(call: CallbackQuery): await do_search(call, 5, False)

@router.callback_query(F.data == "search_5_digits")
async def s5d(call: CallbackQuery): await do_search(call, 5, True)


@router.callback_query(F.data == "search_filter")
async def search_filter(call: CallbackQuery, state: FSMContext):
    can, remaining, _ = await get_attempts(call.from_user.id)
    if not can:
        await call.answer("❌ Попытки исчерпаны!", show_alert=True)
        return
    await call.message.edit_text(
        "🎭 <b>Поиск по маске</b>\n\n"
        "Используйте <code>?</code> для любого символа:\n"
        "<code>pro???</code> → proXXX\n"
        "<code>a?b?c?</code> → aXbXcX\n\n"
        "📏 Длина: 5–32 символа",
        reply_markup=cancel_kb("menu_search"), parse_mode="HTML"
    )
    await state.set_state(SearchStates.waiting_mask)
    await call.answer()


@router.message(SearchStates.waiting_mask)
async def process_mask(message: Message, state: FSMContext):
    from bot.utils.username_checker import validate_mask, apply_mask
    mask = message.text.strip()
    if not validate_mask(mask):
        await message.answer(
            "❌ Неверный формат маски!\n"
            "• Длина 5–32 символа\n"
            "• Только буквы, цифры и <code>?</code>\n"
            "• Первый символ — буква или <code>?</code>",
            reply_markup=cancel_kb("menu_search"), parse_mode="HTML"
        ); return

    await state.clear()
    msg = await message.answer(
        f"🔍 <b>Ищу ник по маске</b> <code>{mask}</code>...\n\n"
        "⏳ Двойная проверка: Telegram API + Fragment",
        parse_mode="HTML"
    )
    user_id = message.from_user.id
    await increment_search(user_id)
    result = await find_free_username(len(mask), mask=mask)
    prem = await is_premium(user_id)

    if result:
        uname, rating = result
        await increment_found(user_id)
        await save_found_username(user_id, uname, len(mask), rating)
        stars_str = "⭐" * rating + "☆" * (10 - rating)
        await msg.edit_text(
            f"✅ <b>Найден свободный ник!</b>\n\n"
            f"📛 <code>@{uname}</code>\n"
            f"🎭 Маска: <code>{mask}</code>\n"
            f"📊 Рейтинг: {rating}/10 {stars_str}\n\n"
            f"✅ Telegram API + Fragment\n\n"
            f"👆 t.me/{uname}",
            reply_markup=search_sections_kb(prem), parse_mode="HTML"
        )
    else:
        await msg.edit_text(
            "❌ <b>Не удалось найти ник по маске</b>\n\nПопробуйте другую маску.",
            reply_markup=search_sections_kb(prem), parse_mode="HTML"
        )


@router.callback_query(F.data == "search_trap")
async def search_trap(call: CallbackQuery):
    user_id = call.from_user.id
    traps = await get_user_traps(user_id)
    text = "🪤 <b>Ловушка на ник</b>\n\nУведомлю когда ник освободится.\n\n"
    if traps:
        text += f"Активных: <b>{len(traps)}</b>\n"
        for t in traps:
            interval_min = (t["check_interval"] or 1800) // 60
            text += f"• @{t['target_username']} (каждые {interval_min} мин)\n"
    else:
        text += "Нет активных ловушек."
    await call.message.edit_text(text, reply_markup=trap_manage_kb(traps), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "trap_add")
async def trap_add(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "🪤 Введите юзернейм для ловушки (без @):",
        reply_markup=cancel_kb("search_trap")
    )
    await state.set_state(SearchStates.waiting_trap_username)
    await call.answer()


@router.message(SearchStates.waiting_trap_username)
async def process_trap_username(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@").lower()
    if not (5 <= len(username) <= 32) or not all(c.isalnum() or c == "_" for c in username):
        await message.answer(
            "❌ Юзернейм 5–32 символа (буквы, цифры, _):",
            reply_markup=cancel_kb("search_trap")
        ); return
    await state.update_data(trap_username=username)
    user_id = message.from_user.id
    luxe = await is_luxe(user_id)
    prem = await is_premium(user_id)
    await message.answer(
        f"⏱ <b>Как часто проверять @{username}?</b>\n\n"
        + ("👑 Luxe: до 10 мин\n💎 Premium: до 15 мин\n" if luxe else
           "💎 Premium: до 15 мин\n" if prem else ""),
        reply_markup=trap_interval_kb(prem, luxe),
        parse_mode="HTML"
    )
    await state.set_state(SearchStates.waiting_trap_interval)


@router.callback_query(SearchStates.waiting_trap_interval, F.data.startswith("trap_interval_"))
async def process_trap_interval(call: CallbackQuery, state: FSMContext):
    interval = int(call.data.split("_")[-1])
    user_id = call.from_user.id
    luxe = await is_luxe(user_id)
    prem = await is_premium(user_id)

    min_interval = TRAP_INTERVAL_LUXE_MIN if luxe else (TRAP_INTERVAL_PREMIUM_MIN if prem else TRAP_INTERVAL_FREE)
    if interval < min_interval:
        interval = min_interval

    data = await state.get_data()
    username = data.get("trap_username", "")
    await state.clear()
    await add_trap(user_id, username, check_interval=interval)
    interval_min = interval // 60
    await call.message.edit_text(
        f"✅ <b>Ловушка установлена!</b>\n\n"
        f"Слежу за: @{username}\n"
        f"🕐 Интервал проверки: каждые <b>{interval_min} мин</b>",
        reply_markup=cancel_kb("search_trap"), parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("trap_delete_"))
async def trap_delete(call: CallbackQuery):
    trap_id = int(call.data.split("_")[-1])
    await delete_trap(trap_id)
    await call.answer("✅ Ловушка удалена")
    traps = await get_user_traps(call.from_user.id)
    text = "🪤 <b>Ловушка на ник</b>\n\n"
    if traps:
        text += f"Активных: <b>{len(traps)}</b>\n"
        for t in traps:
            interval_min = (t["check_interval"] or 1800) // 60
            text += f"• @{t['target_username']} (каждые {interval_min} мин)\n"
    else:
        text += "Нет активных ловушек."
    await call.message.edit_text(text, reply_markup=trap_manage_kb(traps), parse_mode="HTML")
