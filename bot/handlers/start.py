from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from bot.database import get_user, create_user, update_username, add_referral, add_premium_days, get_setting, get_referral_count, is_luxe
from bot.keyboards.main_kb import main_menu_kb
from bot.config import ADMIN_IDS

router = Router()


async def check_referral_reward(referrer_id: int, bot):
    count = await get_referral_count(referrer_id)
    rewards = await get_setting("referral_rewards")
    if not rewards:
        return
    for refs_str, days in rewards.items():
        if count == int(refs_str):
            await add_premium_days(referrer_id, days)
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎉 <b>Поздравляем!</b> Вы пригласили <b>{count}</b> рефералов "
                    f"и получили <b>{days} дней Premium</b>!",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            break


def get_welcome_text(remaining: int) -> str:
    return (
        "⚡️ <b>UqozaSearch</b> — поиск свободных ников\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"🎯 Попытки: <b>{remaining}/3</b>\n"
        "💎 Premium открывает:\n"
        "• Поиск редких 5-буквенных ников\n"
        "• Фильтр по маске (a?b?c → любые буквы)\n"
        "• Поиск по рейтингу (7/10–10/10)\n"
        "• Ловушка — уведомление когда ник освободится\n"
        "• 📦 Массовый поиск (5 ников за раз)\n"
        "• Безлимитный поиск без ограничений\n\n"
        "Выберите действие ниже 👇"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split()
    referrer_id = None

    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_id = int(args[1].split("_")[1])
            if ref_id != message.from_user.id:
                referrer_id = ref_id
        except Exception:
            pass

    user_id = message.from_user.id
    username = message.from_user.username or ""
    user = await get_user(user_id)

    if not user:
        await create_user(user_id, username, referrer_id)
        if referrer_id:
            await add_referral(referrer_id)
            await check_referral_reward(referrer_id, message.bot)
    else:
        await update_username(user_id, username)

    from bot.database import get_today_searches
    from bot.config import FREE_DAILY_ATTEMPTS
    from bot.database import is_premium as _is_premium
    prem = await _is_premium(user_id)
    luxe = await is_luxe(user_id)
    used = await get_today_searches(user_id)
    remaining = FREE_DAILY_ATTEMPTS - used if not prem else 999

    await message.answer(
        get_welcome_text(min(remaining, FREE_DAILY_ATTEMPTS) if not prem else 999),
        reply_markup=main_menu_kb(user_id=user_id, is_luxe=luxe),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = call.from_user.id
    from bot.database import get_today_searches, is_premium as _is_premium
    from bot.config import FREE_DAILY_ATTEMPTS
    prem = await _is_premium(user_id)
    luxe = await is_luxe(user_id)
    used = await get_today_searches(user_id)
    remaining = FREE_DAILY_ATTEMPTS - used if not prem else 999

    await call.message.edit_text(
        get_welcome_text(min(remaining, FREE_DAILY_ATTEMPTS) if not prem else 999),
        reply_markup=main_menu_kb(user_id=user_id, is_luxe=luxe),
        parse_mode="HTML"
    )
    await call.answer()
