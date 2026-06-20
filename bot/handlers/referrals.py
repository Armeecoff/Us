from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.database import get_user, get_referral_count, get_setting
from bot.keyboards.referral_kb import referral_kb
from bot.keyboards.main_kb import back_to_menu_kb

router = Router()


@router.callback_query(F.data == "menu_referrals")
async def menu_referrals(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = call.from_user.id
    ref_count = await get_referral_count(user_id)
    rewards = await get_setting("referral_rewards")

    rewards_text = ""
    if rewards:
        for refs, days in sorted(rewards.items(), key=lambda x: int(x[0])):
            rewards_text += f"• {refs} рефералов → {days} дн. Premium\n"

    bot_info = await call.bot.get_me()
    bot_username = bot_info.username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    text = (
        "🏆 <b>Реферальная программа</b>\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "👥 Приглашайте друзей — получайте дни Premium бесплатно\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"📊 Приглашено: <b>{ref_count}</b> чел.\n\n"
        f"🎁 <b>Награды:</b>\n"
        f"{rewards_text}\n"
        f"💡 Реферал засчитывается, когда приглашённый впервые запустит бота по вашей ссылке."
    )

    await call.message.edit_text(
        text,
        reply_markup=referral_kb(bot_username, user_id),
        parse_mode="HTML"
    )
    await call.answer()
