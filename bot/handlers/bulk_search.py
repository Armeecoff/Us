import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.database import (
    is_premium, is_luxe, get_bulk_used_today, get_bulk_extra,
    increment_bulk, increment_found, save_found_username, get_setting,
    update_user_stats, get_user_stats   # новые импорты
)
from bot.config import BULK_PREMIUM_PER_DAY, BULK_LUXE_PER_DAY, BULK_SIZE
from bot.keyboards.search_kb import (
    search_sections_kb, bulk_options_kb, bulk_buy_extra_kb, cancel_kb
)
from bot.utils.username_checker import find_free_usernames

router = Router()


async def get_bulk_limit(user_id: int) -> int:
    luxe = await is_luxe(user_id)
    return BULK_LUXE_PER_DAY if luxe else BULK_PREMIUM_PER_DAY


@router.callback_query(F.data == "search_bulk")
async def search_bulk_menu(call: CallbackQuery):
    user_id = call.from_user.id
    prem = await is_premium(user_id)
    if not prem:
        await call.answer("🔒 Массовый поиск — только для Premium!", show_alert=True)
        return

    limit = await get_bulk_limit(user_id)
    used = await get_bulk_used_today(user_id)
    extra = await get_bulk_extra(user_id)
    remaining = max(0, limit - used) + extra

    text = (
        f"📦 <b>Массовый поиск</b>\n\n"
        f"Находит сразу <b>{BULK_SIZE} свободных ника</b> за один раз!\n\n"
        f"🎯 Осталось запусков сегодня: <b>{remaining}</b> "
        f"(лимит {limit}/день{', +' + str(extra) + ' доп.' if extra else ''})\n\n"
        f"Выберите параметры поиска:"
    )
    await call.message.edit_text(text, reply_markup=bulk_options_kb(), parse_mode="HTML")
    await call.answer()


async def do_bulk(call: CallbackQuery, length: int, with_digits: bool):
    user_id = call.from_user.id
    limit = await get_bulk_limit(user_id)
    used = await get_bulk_used_today(user_id)
    extra = await get_bulk_extra(user_id)
    remaining = max(0, limit - used) + extra

    if remaining <= 0:
        price_data = await get_setting("bulk_extra_price")
        stars = price_data.get("stars", 50) if price_data else 50
        await call.message.edit_text(
            f"⛔ <b>Лимит массового поиска исчерпан!</b>\n\n"
            f"Использовано: {used}/{limit} сегодня\n\n"
            f"Докупите дополнительные попытки:",
            reply_markup=bulk_buy_extra_kb(stars),
            parse_mode="HTML"
        )
        await call.answer()
        return

    digits_text = "с цифрами" if with_digits else "без цифр"
    await call.message.edit_text(
        f"🔍 <b>Массовый поиск {length}-буквенных ников ({digits_text})...</b>\n\n"
        f"Ищу сразу {BULK_SIZE} свободных ника. Двойная проверка: Telegram + Fragment\n"
        f"⏳ Пожалуйста, подождите...",
        parse_mode="HTML"
    )
    await call.answer()

    # Увеличиваем счётчик использованных массовых поисков
    await increment_bulk(user_id)
    if extra > 0 and (await get_bulk_used_today(user_id)) > limit:
        from bot.database import spend_bulk_extra
        await spend_bulk_extra(user_id)

    # Запускаем поиск
    results = await find_free_usernames(
        length, with_digits, count=BULK_SIZE, max_attempts=1000
    )

    prem = await is_premium(user_id)

    # Обновляем статистику для каждого найденного ника
    for uname, rating in results:
        await increment_found(user_id)
        await save_found_username(user_id, uname, length, rating)
        # Обновляем расширенную статистику (total_searches, avg_rating и т.д.)
        await update_user_stats(user_id, searched=1, found=1, rating=rating)

    # Если ников не найдено, всё равно увеличим счётчик поисков (хотя бы на 1)
    if not results:
        # Можно засчитать как одну проверку без находки
        await update_user_stats(user_id, searched=1, found=0)

    # Получаем обновлённую статистику пользователя
    stats = await get_user_stats(user_id)

    if results:
        lines = []
        for i, (uname, rating) in enumerate(results, 1):
            stars_str = "⭐" * rating + "☆" * (10 - rating)
            lines.append(
                f"{i}. <code>@{uname}</code> — {rating}/10 {stars_str}\n"
                f"   📎 t.me/{uname}"
            )

        new_used = await get_bulk_used_today(user_id)
        new_extra = await get_bulk_extra(user_id)
        new_limit = await get_bulk_limit(user_id)
        new_remaining = max(0, new_limit - new_used) + new_extra

        result_text = "\n\n".join(lines)

        # Добавляем блок статистики
        stats_text = (
            f"\n\n📊 <b>Ваша статистика</b>\n"
            f"• Всего поисков: {stats['total_searches']}\n"
            f"• Найдено ников: {stats['total_found']}\n"
            f"• Сегодня: {stats['today_searches']} проверок, {stats['today_found']} найдено\n"
            f"• Средний рейтинг: {stats['avg_rating']:.1f}"
        )

        await call.message.edit_text(
            f"✅ <b>Найдено {len(results)} свободных ника!</b>\n\n"
            f"{result_text}\n\n"
            f"🎯 Осталось запусков: {new_remaining}"
            f"{stats_text}",
            reply_markup=search_sections_kb(prem),
            parse_mode="HTML"
        )
    else:
        # Если ничего не найдено, показываем статистику
        stats_text = (
            f"\n\n📊 <b>Ваша статистика</b>\n"
            f"• Всего поисков: {stats['total_searches']}\n"
            f"• Найдено ников: {stats['total_found']}\n"
            f"• Сегодня: {stats['today_searches']} проверок, {stats['today_found']} найдено\n"
            f"• Средний рейтинг: {stats['avg_rating']:.1f}"
        )

        await call.message.edit_text(
            f"❌ <b>Не удалось найти ники</b>\n\n"
            f"Попробуйте ещё раз."
            f"{stats_text}",
            reply_markup=search_sections_kb(prem),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "bulk_5_no")
async def bulk_5_no(call: CallbackQuery):
    await do_bulk(call, 5, False)


@router.callback_query(F.data == "bulk_5_yes")
async def bulk_5_yes(call: CallbackQuery):
    await do_bulk(call, 5, True)


@router.callback_query(F.data == "bulk_6_no")
async def bulk_6_no(call: CallbackQuery):
    await do_bulk(call, 6, False)


@router.callback_query(F.data == "bulk_6_yes")
async def bulk_6_yes(call: CallbackQuery):
    await do_bulk(call, 6, True)


@router.callback_query(F.data == "bulk_buy_extra")
async def bulk_buy_extra(call: CallbackQuery):
    from aiogram.types import LabeledPrice
    price_data = await get_setting("bulk_extra_price")
    stars = price_data.get("stars", 50) if price_data else 50
    await call.message.answer_invoice(
        title="📦 Дополнительные попытки массового поиска",
        description=f"Докупить 5 дополнительных попыток массового поиска (не сгорают на следующий день)",
        payload="bulk_extra_5",
        currency="XTR",
        prices=[LabeledPrice(label="5 попыток массового поиска", amount=stars)],
    )
    await call.answer()
