from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database import (
    get_user, is_premium, is_luxe, get_premium_until, get_luxe_until,
    use_promo, add_premium_days, get_today_searches, get_api_key
)
from bot.keyboards.profile_kb import profile_kb, cancel_kb
from bot.config import FREE_DAILY_ATTEMPTS

router = Router()


class ProfileStates(StatesGroup):
    waiting_promo = State()


@router.callback_query(F.data == "menu_profile")
async def menu_profile(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = call.from_user.id
    user = await get_user(user_id)
    prem = await is_premium(user_id)
    luxe = await is_luxe(user_id)
    until_l = await get_luxe_until(user_id)
    until_p = await get_premium_until(user_id)
    today_count = await get_today_searches(user_id)

    if luxe and until_l:
        sub_text = f"👑 Luxe до {until_l.strftime('%d.%m.%Y')}"
    elif prem and until_p:
        sub_text = f"💎 Premium до {until_p.strftime('%d.%m.%Y')}"
    else:
        sub_text = "❌ Нет подписки"

    today_text = f"{today_count}/∞" if prem else f"{today_count}/{FREE_DAILY_ATTEMPTS}"

    from datetime import datetime
    try:
        reg = datetime.fromisoformat(user["registered_at"]).strftime("%Y-%m-%d")
    except Exception:
        reg = "—"

    uname = f"@{user['username']}" if user["username"] else "Не установлен"

    text = (
        f"👤 <b>ПРОФИЛЬ</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"• Юзернейм: {uname}\n\n"
        f"↳ Подписка: {sub_text}\n"
        f"• Сегодня: {today_text}\n"
        f"• Всего поисков: {user['total_searches'] or 0}\n"
        f"• Найдено ников: {user['found_count'] or 0}\n"
        f"🏆 Рефералов: {user['referral_count'] or 0}\n\n"
        f"📅 Регистрация: {reg}"
    )
    await call.message.edit_text(text, reply_markup=profile_kb(prem), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "profile_promo")
async def profile_promo(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "🎟 <b>Активация промокода</b>\n\nВведите промокод:",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await state.set_state(ProfileStates.waiting_promo)
    await call.answer()


@router.message(ProfileStates.waiting_promo)
async def process_promo(message: Message, state: FSMContext):
    code = message.text.strip()
    user_id = message.from_user.id
    days, sub_type, status = await use_promo(user_id, code)

    errors = {
        "not_found": "❌ Промокод не найден.",
        "expired": "❌ Промокод исчерпан.",
        "already_used": "❌ Вы уже использовали этот промокод.",
    }
    if status in errors:
        await message.answer(errors[status], reply_markup=cancel_kb())
        return

    await add_premium_days(user_id, days, sub_type or "premium")
    if sub_type == "luxe":
        from bot.database import get_api_key, generate_api_key
        key = await get_api_key(user_id)
        if not key:
            key = await generate_api_key(user_id)

    until = await get_premium_until(user_id)
    await state.clear()
    labels = {1: "1 день", 3: "3 дня", 10: "10 дней", 30: "30 дней"}
    sub_label = "👑 Luxe" if sub_type == "luxe" else "💎 Premium"
    await message.answer(
        f"✅ <b>Промокод активирован!</b>\n\n"
        f"🎁 Получено: <b>{sub_label} на {labels.get(days, f'{days} дней')}</b>\n"
        f"📅 До: {until.strftime('%d.%m.%Y %H:%M') if until else '—'}",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "profile_info")
async def profile_info(call: CallbackQuery):
    from bot.database import is_premium as _prem
    prem = await _prem(call.from_user.id)
    text = (
        "ℹ️ <b>О боте</b>\n\n"
        "⚡️ <b>UqozaSearch</b> — поиск свободных Telegram-юзернеймов\n\n"
        "🔍 <b>Как работает поиск:</b>\n"
        "1. Генерируем случайный юзернейм нужной длины\n"
        "2. Проверяем через Telegram API (Telethon)\n"
        "3. Проверяем на Fragment — не выставлен ли на аукцион\n"
        "4. Если оба теста прошли — показываем вам!\n\n"
        "📊 <b>Рейтинг ника:</b>\n"
        "10/10 — идеальный: только буквы, без повторов\n"
        "7-9/10 — хороший\n"
        "1-6/10 — есть цифры или повторяющиеся символы"
    )
    await call.message.edit_text(text, reply_markup=profile_kb(prem), parse_mode="HTML")
    await call.answer()
