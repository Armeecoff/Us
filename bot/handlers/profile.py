from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database import (
    get_user, is_premium, is_luxe, get_premium_until, get_luxe_until,
    use_promo, add_premium_days, get_today_searches, get_api_key,
    get_user_stats   # новый импорт
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

    # Получаем основные данные пользователя (username, registered_at)
    user = await get_user(user_id)
    # Получаем расширенную статистику
    stats = await get_user_stats(user_id)

    prem = await is_premium(user_id)
    luxe = await is_luxe(user_id)
    until_l = await get_luxe_until(user_id)
    until_p = await get_premium_until(user_id)

    if luxe and until_l:
        sub_text = f"👑 Luxe до {until_l.strftime('%d.%m.%Y')}"
    elif prem and until_p:
        sub_text = f"💎 Premium до {until_p.strftime('%d.%m.%Y')}"
    else:
        sub_text = "❌ Нет подписки"

    # Определяем лимит на сегодня (для отображения)
    if prem:
        today_text = f"{stats['today_searches']}/∞"
    else:
        today_text = f"{stats['today_searches']}/{FREE_DAILY_ATTEMPTS}"

    from datetime import datetime
    try:
        reg = datetime.fromisoformat(user["registered_at"]).strftime("%Y-%m-%d")
    except Exception:
        reg = "—"

    uname = f"@{user['username']}" if user["username"] else "Не установлен"

    # Формируем текст с новой статистикой
    text = (
        f"👤 <b>ПРОФИЛЬ</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"• Юзернейм: {uname}\n\n"
        f"↳ Подписка: {sub_text}\n"
        f"• Сегодня: {today_text} (найдено: {stats['today_found']})\n"
        f"• Всего поисков: {stats['total_searches']}\n"
        f"• Найдено ников: {stats['total_found']}\n"
        f"• Средний рейтинг: {stats['avg_rating']:.1f}\n"
        f"• Последняя активность: {stats['last_active'] or 'нет'}\n\n"
        f"🏆 Рефералов: {stats['referrals']}\n"
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
        key = await get_api_key(user_id)
        if not key:
            from bot.database import generate_api_key
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
    prem = await is_premium(call.from_user.id)
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
