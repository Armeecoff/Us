from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery

from bot.database import (
    get_setting, is_premium, is_luxe, get_premium_until, get_luxe_until,
    get_referral_count, add_premium_days, generate_api_key
)
from bot.keyboards.premium_kb import premium_menu_kb, sub_prices_kb

router = Router()


@router.callback_query(F.data == "menu_premium")
async def menu_premium(call: CallbackQuery):
    user_id = call.from_user.id
    prem = await is_premium(user_id)
    luxe = await is_luxe(user_id)
    until_p = await get_premium_until(user_id)
    until_l = await get_luxe_until(user_id)
    ref_count = await get_referral_count(user_id)
    rewards = await get_setting("referral_rewards")

    if luxe and until_l:
        status = f"👑 Luxe до {until_l.strftime('%d.%m.%Y %H:%M')}"
    elif prem and until_p:
        status = f"💎 Premium до {until_p.strftime('%d.%m.%Y %H:%M')}"
    else:
        status = "❌ Нет подписки"

    rewards_text = ""
    if rewards:
        for r, d in sorted(rewards.items(), key=lambda x: int(x[0])):
            rewards_text += f"• {r} рефералов → {d} дн.\n"

    text = (
        f"💎 <b>ПОДПИСКИ</b>\n\n"
        f"Статус: {status}\n\n"
        f"━━━━ 💎 <b>PREMIUM</b> ━━━━\n"
        f"• Поиск 5-буквенных ников\n"
        f"• Фильтр по маске\n"
        f"• Поиск по рейтингу\n"
        f"• 🪤 Ловушка на ник\n"
        f"• 📦 Массовый поиск (5 шт, 10/день)\n"
        f"• ♾️ Безлимитный поиск\n"
        f"• 📋 История 100 найденных ников\n\n"
        f"━━━━ 👑 <b>LUXE</b> ━━━━\n"
        f"• Всё из Premium\n"
        f"• 🌐 REST API (поиск, фильтры, ловушки)\n"
        f"• Массовый поиск: 100/день\n\n"
        f"🏆 <b>Рефералы → Premium бесплатно:</b>\n"
        f"{rewards_text}\n"
        f"👥 Ваших рефералов: <b>{ref_count}</b>"
    )
    await call.message.edit_text(text, reply_markup=premium_menu_kb(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "buy_sub_premium")
async def buy_sub_premium(call: CallbackQuery):
    prices = await get_setting("premium_prices")
    await call.message.edit_text(
        "💎 <b>Premium подписка</b>\n\nВыберите срок:",
        reply_markup=sub_prices_kb(prices, "premium"),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "buy_sub_luxe")
async def buy_sub_luxe(call: CallbackQuery):
    prices = await get_setting("luxe_prices")
    await call.message.edit_text(
        "👑 <b>Luxe подписка</b>\n\nВключает всё из Premium + REST API + 100 массовых поисков/день\n\nВыберите срок:",
        reply_markup=sub_prices_kb(prices, "luxe"),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("buy_premium_"))
async def buy_premium(call: CallbackQuery):
    days = call.data.split("_")[-1]
    prices = await get_setting("premium_prices")
    if days not in prices:
        await call.answer("❌ Ошибка", show_alert=True)
        return
    stars = prices[days]["stars"]
    labels = {"1": "1 день", "3": "3 дня", "10": "10 дней", "30": "30 дней"}
    await call.message.answer_invoice(
        title=f"💎 Premium на {labels.get(days, days+' дней')}",
        description="Безлимитный поиск, 5-буквенные ники, фильтры, ловушка, массовый поиск, история!",
        payload=f"premium_{days}",
        currency="XTR",
        prices=[LabeledPrice(label=f"Premium {labels.get(days)}", amount=stars)],
    )
    await call.answer()


@router.callback_query(F.data.startswith("buy_luxe_"))
async def buy_luxe(call: CallbackQuery):
    days = call.data.split("_")[-1]
    prices = await get_setting("luxe_prices")
    if days not in prices:
        await call.answer("❌ Ошибка", show_alert=True)
        return
    stars = prices[days]["stars"]
    labels = {"1": "1 день", "3": "3 дня", "10": "10 дней", "30": "30 дней"}
    await call.message.answer_invoice(
        title=f"👑 Luxe на {labels.get(days, days+' дней')}",
        description="Всё из Premium + REST API доступ + 100 массовых поисков/день!",
        payload=f"luxe_{days}",
        currency="XTR",
        prices=[LabeledPrice(label=f"Luxe {labels.get(days)}", amount=stars)],
    )
    await call.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    user_id = message.from_user.id

    if payload.startswith("premium_"):
        days = int(payload.split("_")[1])
        await add_premium_days(user_id, days, "premium")
        until = await get_premium_until(user_id)
        labels = {1: "1 день", 3: "3 дня", 10: "10 дней", 30: "30 дней"}
        await message.answer(
            f"✅ <b>Оплата прошла!</b>\n\n"
            f"💎 Premium активирован на {labels.get(days, f'{days} дней')}\n"
            f"📅 До: {until.strftime('%d.%m.%Y %H:%M') if until else '—'}\n\n"
            f"Наслаждайтесь безлимитным поиском! 🚀",
            parse_mode="HTML"
        )

    elif payload.startswith("luxe_"):
        days = int(payload.split("_")[1])
        await add_premium_days(user_id, days, "luxe")
        until = await get_luxe_until(user_id)
        # Generate API key if not exists
        from bot.database import get_api_key
        key = await get_api_key(user_id)
        if not key:
            key = await generate_api_key(user_id)
        labels = {1: "1 день", 3: "3 дня", 10: "10 дней", 30: "30 дней"}
        await message.answer(
            f"✅ <b>Оплата прошла!</b>\n\n"
            f"👑 Luxe активирован на {labels.get(days, f'{days} дней')}\n"
            f"📅 До: {until.strftime('%d.%m.%Y %H:%M') if until else '—'}\n\n"
            f"🌐 Ваш API ключ:\n<code>{key}</code>\n\n"
            f"Нажмите «🌐 API Luxe» в главном меню для инструкций.",
            parse_mode="HTML"
        )

    elif payload.startswith("bulk_extra"):
        extra_count = int(payload.split("_")[-1])
        from bot.database import add_bulk_extra
        await add_bulk_extra(user_id, extra_count)
        await message.answer(
            f"✅ <b>Докуплено {extra_count} попыток массового поиска!</b>",
            parse_mode="HTML"
        )
