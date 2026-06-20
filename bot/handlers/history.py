from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.database import is_premium, get_last_found
from bot.keyboards.main_kb import back_to_menu_kb

router = Router()


@router.callback_query(F.data == "profile_history")
async def show_history(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    prem = await is_premium(user_id)
    if not prem:
        await call.answer("🔒 История доступна только в Premium!", show_alert=True)
        return

    records = await get_last_found(user_id, limit=100)
    if not records:
        await call.message.edit_text(
            "📋 <b>История найденных ников</b>\n\nПока ничего нет — начни поиск!",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML"
        )
        await call.answer()
        return

    lines = []
    for i, r in enumerate(records, 1):
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(r["found_at"]).strftime("%d.%m %H:%M")
        except Exception:
            dt = "—"
        lines.append(f"{i}. <code>@{r['username']}</code> ({r['length']}б, ⭐{r['rating']}/10) — {dt}")

    # Split into chunks of 50
    chunk = lines[:50]
    text = (
        f"📋 <b>История найденных ников</b> (последние {len(records)})\n\n"
        + "\n".join(chunk)
    )
    if len(records) > 50:
        text += f"\n\n<i>...и ещё {len(records) - 50}. Всего: {len(records)}</i>"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Профиль", callback_data="menu_profile")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()
