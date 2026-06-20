from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import ADMIN_IDS, API_ID, API_HASH, SESSIONS_DIR
from bot.database import (
    get_setting, set_setting, get_all_users, get_all_promos,
    create_promo, add_premium_days, revoke_premium, find_user_by_identifier,
    get_registered_channels, get_registered_channel, delete_registered_channel,
    add_registered_channel, update_registered_channel_username
)
from bot.keyboards.admin_kb import (
    admin_main_kb, admin_prices_kb, admin_refs_kb, admin_promos_kb,
    admin_users_kb, admin_back_kb, cancel_admin_kb,
    channel_menu_kb, channels_list_kb
)

router = Router()


class AdminStates(StatesGroup):
    edit_price_stars = State()
    edit_price_rub = State()
    edit_ref_days = State()
    create_promo_code = State()
    create_promo_days = State()
    create_promo_uses = State()
    create_promo_type = State()
    broadcast_text = State()
    give_premium_user = State()
    give_premium_days = State()
    revoke_sub_user = State()
    bulk_price_stars = State()
    bulk_price_rub = State()
    add_session_phone = State()
    add_session_code = State()
    add_session_pass = State()
    register_channel_username = State()
    channel_transfer_owner = State()


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def admin_home_text() -> str:
    users = await get_all_users()
    premium_count = sum(
        1 for u in users
        if u["premium_until"] and _is_active(u["premium_until"])
    )
    luxe_count = sum(
        1 for u in users
        if u["luxe_until"] and _is_active(u["luxe_until"])
    )
    from bot.utils.session_manager import session_count
    channels = await get_registered_channels()
    return (
        f"🔧 <b>Панель администратора</b>\n\n"
        f"👥 Пользователей: <b>{len(users)}</b>\n"
        f"💎 Premium: <b>{premium_count}</b>\n"
        f"👑 Luxe: <b>{luxe_count}</b>\n"
        f"🔗 Сессий: <b>{session_count()}</b>\n"
        f"📺 Каналов: <b>{len(channels)}</b>"
    )


def _is_active(dt_str: str) -> bool:
    from datetime import datetime
    try:
        return datetime.fromisoformat(dt_str) > datetime.now()
    except Exception:
        return False


# ─── Entry points ─────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    if not is_admin(message.from_user.id):
        return
    text = await admin_home_text()
    await message.answer(text, reply_markup=admin_main_kb(), parse_mode="HTML")


@router.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    await state.clear()
    text = await admin_home_text()
    await call.message.edit_text(text, reply_markup=admin_main_kb(), parse_mode="HTML")
    await call.answer()


# ─── Prices ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_prices")
async def admin_prices(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    prices = await get_setting("premium_prices")
    await call.message.edit_text("💰 <b>Цены Premium</b>", reply_markup=admin_prices_kb(prices, "admin_edit_price"), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "admin_luxe_prices")
async def admin_luxe_prices(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    prices = await get_setting("luxe_prices")
    await call.message.edit_text("👑 <b>Цены Luxe</b>", reply_markup=admin_prices_kb(prices, "admin_edit_luxe"), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("admin_edit_price_") | F.data.startswith("admin_edit_luxe_"))
async def admin_edit_price_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    parts = call.data.split("_")
    sub_type = "luxe" if "luxe" in call.data else "premium"
    days = parts[-1]
    key = "luxe_prices" if sub_type == "luxe" else "premium_prices"
    prices = await get_setting(key)
    cur = prices.get(days, {})
    await state.update_data(editing_days=days, editing_key=key)
    labels = {"1": "1 день", "3": "3 дня", "10": "10 дней", "30": "30 дней"}
    await call.message.edit_text(
        f"✏️ <b>{labels.get(days)}</b> ({sub_type})\n"
        f"Текущая: {cur.get('stars','?')}⭐ / {cur.get('rub','?')}₽\n\n"
        "Введите новую цену в Stars:",
        reply_markup=cancel_admin_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.edit_price_stars)
    await call.answer()


@router.message(AdminStates.edit_price_stars)
async def admin_edit_stars(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        stars = int(message.text.strip())
        assert stars > 0
    except Exception:
        await message.answer("❌ Введите число Stars > 0:", reply_markup=cancel_admin_kb()); return
    await state.update_data(new_stars=stars)
    await message.answer("Теперь введите цену в рублях ₽:", reply_markup=cancel_admin_kb())
    await state.set_state(AdminStates.edit_price_rub)


@router.message(AdminStates.edit_price_rub)
async def admin_edit_rub(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        rub = int(message.text.strip())
        assert rub > 0
    except Exception:
        await message.answer("❌ Введите число ₽ > 0:", reply_markup=cancel_admin_kb()); return
    data = await state.get_data()
    prices = await get_setting(data["editing_key"])
    prices[data["editing_days"]] = {"stars": data["new_stars"], "rub": rub}
    await set_setting(data["editing_key"], prices)
    await state.clear()
    await message.answer(
        f"✅ Цена обновлена: {data['new_stars']}⭐ / {rub}₽",
        reply_markup=admin_prices_kb(prices, "admin_edit_price" if "premium" in data["editing_key"] else "admin_edit_luxe"),
        parse_mode="HTML"
    )


# ─── Bulk extra price ──────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_bulk_price")
async def admin_bulk_price(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    cur = await get_setting("bulk_extra_price") or {}
    await call.message.edit_text(
        f"📦 <b>Цена доп. попыток массового поиска</b>\n\n"
        f"Текущая: {cur.get('stars','?')}⭐ / {cur.get('rub','?')}₽ за 5 попыток\n\n"
        "Введите новую цену в Stars:",
        reply_markup=cancel_admin_kb(), parse_mode="HTML"
    )
    await state.update_data(editing_key="bulk_extra_price")
    await state.set_state(AdminStates.bulk_price_stars)
    await call.answer()


@router.message(AdminStates.bulk_price_stars)
async def admin_bulk_stars(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        stars = int(message.text.strip()); assert stars > 0
    except Exception:
        await message.answer("❌ Введите число > 0:", reply_markup=cancel_admin_kb()); return
    await state.update_data(new_stars=stars)
    await message.answer("Введите цену в рублях ₽:", reply_markup=cancel_admin_kb())
    await state.set_state(AdminStates.bulk_price_rub)


@router.message(AdminStates.bulk_price_rub)
async def admin_bulk_rub(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        rub = int(message.text.strip()); assert rub > 0
    except Exception:
        await message.answer("❌ Введите число > 0:", reply_markup=cancel_admin_kb()); return
    data = await state.get_data()
    await set_setting("bulk_extra_price", {"stars": data["new_stars"], "rub": rub})
    await state.clear()
    await message.answer(f"✅ Цена обновлена: {data['new_stars']}⭐ / {rub}₽ за 5 попыток", reply_markup=admin_back_kb())


# ─── Referrals ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_refs")
async def admin_refs(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    rewards = await get_setting("referral_rewards")
    await call.message.edit_text("👥 <b>Настройки рефералов</b>", reply_markup=admin_refs_kb(rewards), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("admin_edit_ref_"))
async def admin_edit_ref_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    refs = call.data.split("_")[-1]
    rewards = await get_setting("referral_rewards")
    await state.update_data(editing_refs=refs)
    await call.message.edit_text(
        f"✏️ <b>{refs} рефералов → {rewards.get(refs,'?')} дн.</b>\n\nВведите новое кол-во дней:",
        reply_markup=cancel_admin_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.edit_ref_days)
    await call.answer()


@router.message(AdminStates.edit_ref_days)
async def admin_edit_ref_days(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        days = int(message.text.strip()); assert days > 0
    except Exception:
        await message.answer("❌ Введите число дней > 0:", reply_markup=cancel_admin_kb()); return
    data = await state.get_data()
    rewards = await get_setting("referral_rewards")
    rewards[data["editing_refs"]] = days
    await set_setting("referral_rewards", rewards)
    await state.clear()
    await message.answer(f"✅ Обновлено: {data['editing_refs']} рефералов → {days} дн.", reply_markup=admin_refs_kb(rewards), parse_mode="HTML")


# ─── Promo codes ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_promos")
async def admin_promos(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    await call.message.edit_text("🎟 <b>Промокоды</b>", reply_markup=admin_promos_kb(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "admin_create_promo")
async def admin_create_promo_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    await call.message.edit_text("➕ Введите код промокода (латиница/цифры):", reply_markup=cancel_admin_kb())
    await state.set_state(AdminStates.create_promo_code)
    await call.answer()


@router.message(AdminStates.create_promo_code)
async def admin_promo_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    code = message.text.strip().upper()
    if not code.isalnum() or len(code) < 3:
        await message.answer("❌ Только буквы/цифры, мин. 3 символа:", reply_markup=cancel_admin_kb()); return
    await state.update_data(new_code=code)
    await message.answer(
        f"Код: <b>{code}</b>\n\nТип подписки? Введите <b>premium</b> или <b>luxe</b>:",
        reply_markup=cancel_admin_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.create_promo_type)


@router.message(AdminStates.create_promo_type)
async def admin_promo_type(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    sub_type = message.text.strip().lower()
    if sub_type not in ("premium", "luxe"):
        await message.answer("❌ Введите «premium» или «luxe»:", reply_markup=cancel_admin_kb()); return
    await state.update_data(new_sub_type=sub_type)
    await message.answer(f"Тип: <b>{sub_type}</b>\n\nВведите кол-во дней:", reply_markup=cancel_admin_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.create_promo_days)


@router.message(AdminStates.create_promo_days)
async def admin_promo_days(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        days = int(message.text.strip()); assert days > 0
    except Exception:
        await message.answer("❌ Введите число дней > 0:", reply_markup=cancel_admin_kb()); return
    await state.update_data(new_days=days)
    await message.answer(f"Дней: <b>{days}</b>\n\nМакс. кол-во использований:", reply_markup=cancel_admin_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.create_promo_uses)


@router.message(AdminStates.create_promo_uses)
async def admin_promo_uses(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        uses = int(message.text.strip()); assert uses > 0
    except Exception:
        await message.answer("❌ Введите число > 0:", reply_markup=cancel_admin_kb()); return
    data = await state.get_data()
    try:
        await create_promo(data["new_code"], data["new_days"], uses, data.get("new_sub_type", "premium"))
        await state.clear()
        await message.answer(
            f"✅ <b>Промокод создан!</b>\n\n"
            f"🎟 Код: <code>{data['new_code']}</code>\n"
            f"Тип: {data.get('new_sub_type','premium')}\n"
            f"Дней: {data['new_days']}\n"
            f"Использований: {uses}",
            reply_markup=admin_promos_kb(), parse_mode="HTML"
        )
    except Exception:
        await message.answer("❌ Промокод уже существует.", reply_markup=cancel_admin_kb())
        await state.clear()


@router.callback_query(F.data == "admin_list_promos")
async def admin_list_promos(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    promos = await get_all_promos()
    if not promos:
        text = "📋 <b>Промокодов нет.</b>"
    else:
        lines = [f"🎟 <code>{p['code']}</code> [{p.get('sub_type','prem')}] — {p['days']} дн. ({p['used_count']}/{p['max_uses']})" for p in promos]
        text = "📋 <b>Промокоды:</b>\n\n" + "\n".join(lines)
    await call.message.edit_text(text, reply_markup=admin_promos_kb(), parse_mode="HTML")
    await call.answer()


# ─── User management ──────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_users")
async def admin_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    await call.message.edit_text("👤 <b>Управление пользователями</b>", reply_markup=admin_users_kb(), parse_mode="HTML")
    await call.answer()


async def _ask_user_identifier(call: CallbackQuery, state: FSMContext, action: str, next_state):
    await state.update_data(give_action=action)
    await call.message.edit_text(
        f"{'✅ Выдача' if 'give' in action else '❌ Снятие'} подписки\n\n"
        "Введите ID или @username пользователя:",
        reply_markup=cancel_admin_kb()
    )
    await state.set_state(next_state)
    await call.answer()


@router.callback_query(F.data == "admin_give_premium")
async def admin_give_premium(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    await _ask_user_identifier(call, state, "give_premium", AdminStates.give_premium_user)


@router.callback_query(F.data == "admin_give_luxe")
async def admin_give_luxe(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    await _ask_user_identifier(call, state, "give_luxe", AdminStates.give_premium_user)


@router.message(AdminStates.give_premium_user)
async def admin_give_user(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    user = await find_user_by_identifier(message.text.strip())
    if not user:
        await message.answer("❌ Пользователь не найден. Попробуйте снова:", reply_markup=cancel_admin_kb()); return
    data = await state.get_data()
    await state.update_data(target_user_id=user["user_id"])
    uname = f"@{user['username']}" if user['username'] else str(user['user_id'])
    await message.answer(
        f"Пользователь: <b>{uname}</b> (ID: {user['user_id']})\n\nВведите кол-во дней:",
        reply_markup=cancel_admin_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.give_premium_days)


@router.message(AdminStates.give_premium_days)
async def admin_give_days(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        days = int(message.text.strip()); assert days > 0
    except Exception:
        await message.answer("❌ Введите число дней > 0:", reply_markup=cancel_admin_kb()); return
    data = await state.get_data()
    action = data.get("give_action", "give_premium")
    sub_type = "luxe" if "luxe" in action else "premium"
    uid = data["target_user_id"]
    await add_premium_days(uid, days, sub_type)
    if sub_type == "luxe":
        from bot.database import get_api_key, generate_api_key as gen_key
        key = await get_api_key(uid)
        if not key:
            await gen_key(uid)
    await state.clear()
    try:
        sub_label = "👑 Luxe" if sub_type == "luxe" else "💎 Premium"
        await message.bot.send_message(
            uid,
            f"🎁 Администратор выдал вам <b>{sub_label} на {days} дней</b>!",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await message.answer(f"✅ Выдано {days} дней {sub_type} пользователю {uid}", reply_markup=admin_users_kb())


@router.callback_query(F.data == "admin_revoke_sub")
async def admin_revoke_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    await call.message.edit_text("❌ Введите ID или @username для снятия подписки:", reply_markup=cancel_admin_kb())
    await state.set_state(AdminStates.revoke_sub_user)
    await call.answer()


@router.message(AdminStates.revoke_sub_user)
async def admin_revoke_user(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    user = await find_user_by_identifier(message.text.strip())
    if not user:
        await message.answer("❌ Пользователь не найден:", reply_markup=cancel_admin_kb()); return
    await revoke_premium(user["user_id"])
    await state.clear()
    try:
        await message.bot.send_message(user["user_id"], "❌ Ваша подписка была снята администратором.")
    except Exception:
        pass
    uname = f"@{user['username']}" if user['username'] else str(user['user_id'])
    await message.answer(f"✅ Подписка снята у пользователя {uname}", reply_markup=admin_users_kb())


# ─── Stats ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    users = await get_all_users()
    premium_count = sum(1 for u in users if u["premium_until"] and _is_active(u["premium_until"]))
    luxe_count = sum(1 for u in users if u["luxe_until"] and _is_active(u["luxe_until"]))
    total_searches = sum(u["total_searches"] or 0 for u in users)
    total_found = sum(u["found_count"] or 0 for u in users)
    from bot.utils.session_manager import session_count
    await call.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <b>{len(users)}</b>\n"
        f"💎 Premium: <b>{premium_count}</b>\n"
        f"👑 Luxe: <b>{luxe_count}</b>\n"
        f"🔍 Всего поисков: <b>{total_searches}</b>\n"
        f"✅ Найдено ников: <b>{total_found}</b>\n"
        f"🔗 Telethon сессий: <b>{session_count()}</b>",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )
    await call.answer()


# ─── Broadcast ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    await call.message.edit_text("📢 Введите текст рассылки (поддерживается HTML):", reply_markup=cancel_admin_kb())
    await state.set_state(AdminStates.broadcast_text)
    await call.answer()


@router.message(AdminStates.broadcast_text)
async def admin_broadcast_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.clear()
    text = message.text or ""
    users = await get_all_users()
    success = failed = 0
    status_msg = await message.answer(f"📢 Рассылка... 0/{len(users)}")
    for i, user in enumerate(users):
        try:
            await message.bot.send_message(user["user_id"], text, parse_mode="HTML")
            success += 1
        except Exception:
            failed += 1
        if (i + 1) % 25 == 0:
            try:
                await status_msg.edit_text(f"📢 Рассылка... {i+1}/{len(users)}")
            except Exception:
                pass
    await status_msg.edit_text(f"✅ Рассылка завершена!\n✅ Успешно: {success}\n❌ Ошибки: {failed}")


# ─── Add session ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_add_session")
async def admin_add_session(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    from bot.utils.session_manager import session_count
    await call.message.edit_text(
        f"🔗 <b>Добавить Telegram-сессию</b>\n\n"
        f"Сейчас загружено сессий: <b>{session_count()}</b>\n\n"
        "Введите номер телефона в международном формате:\n"
        "<code>+79991234567</code>",
        reply_markup=cancel_admin_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.add_session_phone)
    await call.answer()


@router.message(AdminStates.add_session_phone)
async def admin_session_phone(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    phone = message.text.strip()
    if not phone.startswith("+") or len(phone) < 10:
        await message.answer("❌ Введите номер в формате +79991234567:", reply_markup=cancel_admin_kb())
        return
    msg = await message.answer("📲 Отправляю код на номер...")
    try:
        from bot.utils.session_manager import start_login
        await start_login(phone, API_ID, API_HASH, SESSIONS_DIR)
        await state.update_data(session_phone=phone)
        await msg.edit_text(
            f"✅ Код отправлен на <b>{phone}</b>\n\n"
            "Введите код из Telegram (формат: <code>12345</code> или <code>1 2 3 4 5</code>):",
            reply_markup=cancel_admin_kb(), parse_mode="HTML"
        )
        await state.set_state(AdminStates.add_session_code)
    except Exception as e:
        await msg.edit_text(
            f"❌ Ошибка отправки кода:\n<code>{e}</code>\n\nПроверьте номер и повторите.",
            reply_markup=cancel_admin_kb(), parse_mode="HTML"
        )
        await state.clear()


@router.message(AdminStates.add_session_code)
async def admin_session_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    code = message.text.strip().replace(" ", "")
    data = await state.get_data()
    phone = data.get("session_phone", "")
    msg = await message.answer("🔐 Проверяю код...")
    try:
        from bot.utils.session_manager import finish_login
        from telethon.errors import SessionPasswordNeededError
        result = await finish_login(phone, code)
        if result is True:
            await state.clear()
            from bot.utils.session_manager import session_count
            await msg.edit_text(
                f"✅ <b>Сессия успешно добавлена!</b>\n\nВсего сессий: <b>{session_count()}</b>",
                reply_markup=admin_back_kb(), parse_mode="HTML"
            )
        elif result == "2fa":
            await state.update_data(session_phone=phone)
            await msg.edit_text(
                "🔒 Аккаунт защищён двухфакторной аутентификацией.\n\nВведите пароль 2FA:",
                reply_markup=cancel_admin_kb()
            )
            await state.set_state(AdminStates.add_session_pass)
        else:
            await msg.edit_text(
                "❌ Неверный код или истёк срок. Попробуйте снова /admin",
                reply_markup=admin_back_kb()
            )
            await state.clear()
    except Exception as e:
        await msg.edit_text(
            f"❌ Ошибка: <code>{e}</code>",
            reply_markup=cancel_admin_kb(), parse_mode="HTML"
        )
        await state.clear()


@router.message(AdminStates.add_session_pass)
async def admin_session_pass(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    password = message.text.strip()
    data = await state.get_data()
    phone = data.get("session_phone", "")
    msg = await message.answer("🔐 Проверяю пароль...")
    try:
        from bot.utils.session_manager import finish_login_2fa
        result = await finish_login_2fa(phone, password)
        if result:
            await state.clear()
            from bot.utils.session_manager import session_count
            await msg.edit_text(
                f"✅ <b>Сессия добавлена (2FA)!</b>\n\nВсего сессий: <b>{session_count()}</b>",
                reply_markup=admin_back_kb(), parse_mode="HTML"
            )
        else:
            await msg.edit_text(
                "❌ Неверный пароль 2FA.",
                reply_markup=cancel_admin_kb()
            )
            await state.clear()
    except Exception as e:
        await msg.edit_text(
            f"❌ Ошибка: <code>{e}</code>",
            reply_markup=cancel_admin_kb(), parse_mode="HTML"
        )
        await state.clear()


# ─── Register channel ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_register_channel")
async def admin_register_channel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    from bot.utils.session_manager import session_count, has_sessions
    if not has_sessions():
        await call.answer("❌ Нет загруженных сессий!", show_alert=True); return
    await call.message.edit_text(
        "📺 <b>Зарегистрировать канал</b>\n\n"
        "Введите желаемый юзернейм канала (без @):\n"
        "<i>Бот создаст новый канал с этим именем через один из подключённых аккаунтов</i>",
        reply_markup=cancel_admin_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.register_channel_username)
    await call.answer()


@router.message(AdminStates.register_channel_username)
async def admin_do_register_channel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    username = message.text.strip().lstrip("@")
    if not (5 <= len(username) <= 32) or not all(c.isalnum() or c == "_" for c in username):
        await message.answer(
            "❌ Юзернейм должен быть 5–32 символа (буквы, цифры, _):",
            reply_markup=cancel_admin_kb()
        ); return
    await state.clear()
    msg = await message.answer(f"⏳ Создаю канал @{username}...")
    try:
        from bot.utils.channel_manager import register_new_channel_with_username
        result = await register_new_channel_with_username(username)
        if result:
            await add_registered_channel(
                channel_id=result["channel_id"],
                channel_username=result.get("channel_username", username),
                channel_title=result["channel_title"],
                account_phone=result["account_phone"],
                account_username=result["account_username"],
            )
            acc = f"@{result['account_username']}" if result['account_username'] else result['account_phone']
            await msg.edit_text(
                f"✅ <b>Канал создан!</b>\n\n"
                f"📺 Название: <b>{result['channel_title']}</b>\n"
                f"🔗 Юзернейм: @{result.get('channel_username', username)}\n"
                f"👤 Аккаунт: <b>{acc}</b>\n"
                f"🆔 ID: <code>{result['channel_id']}</code>",
                reply_markup=admin_back_kb(), parse_mode="HTML"
            )
        else:
            await msg.edit_text(
                "❌ Не удалось создать канал.\n\nВозможные причины:\n"
                "• Юзернейм уже занят\n"
                "• Нет доступных сессий с правами\n"
                "• Флудвейт Telegram",
                reply_markup=admin_back_kb(), parse_mode="HTML"
            )
    except Exception as e:
        await msg.edit_text(
            f"❌ Ошибка: <code>{e}</code>",
            reply_markup=cancel_admin_kb(), parse_mode="HTML"
        )


# ─── Channel list & management ────────────────────────────────────────────

@router.callback_query(F.data == "admin_list_channels")
async def admin_list_channels(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    channels = await get_registered_channels()
    if not channels:
        await call.message.edit_text(
            "📋 <b>Зарегистрированных каналов нет.</b>",
            reply_markup=admin_back_kb(), parse_mode="HTML"
        )
    else:
        await call.message.edit_text(
            f"📋 <b>Зарегистрированные каналы</b> ({len(channels)}):",
            reply_markup=channels_list_kb(channels), parse_mode="HTML"
        )
    await call.answer()


@router.callback_query(F.data.startswith("chan_view_"))
async def chan_view(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    channel_id = int(call.data.split("_")[-1])
    ch = await get_registered_channel(channel_id)
    if not ch:
        await call.answer("❌ Канал не найден", show_alert=True); return
    uname = ch["channel_username"] or "—"
    acc = f"@{ch['account_username']}" if ch["account_username"] else ch["account_phone"]
    await call.message.edit_text(
        f"📺 <b>{ch['channel_title']}</b>\n\n"
        f"🔗 Юзернейм: @{uname}\n"
        f"👤 Аккаунт: {acc}\n"
        f"🆔 ID: <code>{channel_id}</code>\n"
        f"📅 Создан: {ch['registered_at'][:10]}",
        reply_markup=channel_menu_kb(channel_id), parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("chan_remove_user_"))
async def chan_remove_user(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    channel_id = int(call.data.split("_")[-1])
    msg = await call.message.edit_text("⏳ Убираю юзернейм с канала...")
    try:
        from bot.utils.channel_manager import remove_username_from_channel
        ok = await remove_username_from_channel(channel_id)
        if ok:
            await update_registered_channel_username(channel_id, "")
            await msg.edit_text(
                "✅ Юзернейм убран. Канал теперь приватный.",
                reply_markup=channel_menu_kb(channel_id), parse_mode="HTML"
            )
        else:
            await msg.edit_text(
                "❌ Не удалось убрать юзернейм. Нет прав или сессии?",
                reply_markup=channel_menu_kb(channel_id)
            )
    except Exception as e:
        await msg.edit_text(
            f"❌ Ошибка: <code>{e}</code>",
            reply_markup=channel_menu_kb(channel_id), parse_mode="HTML"
        )
    await call.answer()


@router.callback_query(F.data.startswith("chan_delete_"))
async def chan_delete(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    channel_id = int(call.data.split("_")[-1])
    msg = await call.message.edit_text("⏳ Удаляю канал...")
    try:
        from bot.utils.channel_manager import delete_channel
        ok = await delete_channel(channel_id)
        if ok:
            await delete_registered_channel(channel_id)
            await msg.edit_text(
                "✅ Канал удалён.",
                reply_markup=admin_back_kb()
            )
        else:
            await msg.edit_text(
                "❌ Не удалось удалить канал. Нет прав или сессии?",
                reply_markup=channel_menu_kb(channel_id)
            )
    except Exception as e:
        await msg.edit_text(
            f"❌ Ошибка: <code>{e}</code>",
            reply_markup=channel_menu_kb(channel_id), parse_mode="HTML"
        )
    await call.answer()


@router.callback_query(F.data.startswith("chan_transfer_"))
async def chan_transfer_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True); return
    channel_id = int(call.data.split("_")[-1])
    await state.update_data(transfer_channel_id=channel_id)
    await call.message.edit_text(
        "🔄 <b>Передача канала</b>\n\n"
        "Введите @юзернейм нового владельца:\n"
        "<i>Он должен быть подписан на канал. Вы (админ бота) тоже должны быть подписаны.</i>",
        reply_markup=cancel_admin_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.channel_transfer_owner)
    await call.answer()


@router.message(AdminStates.channel_transfer_owner)
async def chan_transfer_do(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    new_owner = message.text.strip().lstrip("@")
    if not new_owner:
        await message.answer("❌ Введите юзернейм:", reply_markup=cancel_admin_kb()); return
    data = await state.get_data()
    channel_id = data.get("transfer_channel_id")
    await state.clear()
    msg = await message.answer(f"⏳ Передаю канал @{new_owner}...")
    try:
        from bot.utils.channel_manager import transfer_channel_ownership
        ok, detail = await transfer_channel_ownership(channel_id, new_owner)
        if ok:
            await msg.edit_text(
                f"✅ <b>Канал передан!</b>\n\nНовый владелец: @{detail}",
                reply_markup=admin_back_kb(), parse_mode="HTML"
            )
        else:
            await msg.edit_text(
                f"❌ Не удалось передать канал:\n{detail}",
                reply_markup=admin_back_kb()
            )
    except Exception as e:
        await msg.edit_text(
            f"❌ Ошибка: <code>{e}</code>",
            reply_markup=admin_back_kb(), parse_mode="HTML"
        )
