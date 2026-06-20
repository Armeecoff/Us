from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.database import is_luxe, get_api_key, generate_api_key
from bot.config import ADMIN_IDS, API_PORT, API_BASE_URL

router = Router()


@router.callback_query(F.data == "menu_api_info")
async def menu_api_info(call: CallbackQuery):
    user_id = call.from_user.id
    luxe = await is_luxe(user_id)
    is_admin = user_id in ADMIN_IDS

    if not luxe and not is_admin:
        await call.answer("🔒 API доступен только для Luxe подписчиков!", show_alert=True)
        return

    api_key = await get_api_key(user_id)
    if not api_key and (luxe or is_admin):
        api_key = await generate_api_key(user_id)

    base_url = API_BASE_URL

    text = (
        "🌐 <b>UqozaSearch API — Luxe</b>\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 <b>Ваш API ключ:</b>\n"
        f"<code>{api_key}</code>\n\n"
        f"🔗 <b>Base URL:</b>\n"
        f"<code>{base_url}</code>\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "📖 <b>Эндпоинты:</b>\n\n"

        "🔍 <b>Поиск свободного ника</b>\n"
        "<code>GET /search</code>\n"
        "Параметры:\n"
        "• <code>length</code> — длина (5 или 6)\n"
        "• <code>digits</code> — с цифрами (true/false)\n"
        "• <code>rating</code> — мин. рейтинг (1-10)\n"
        "• <code>count</code> — кол-во (1-5)\n\n"
        "Пример:\n"
        f"<code>GET {base_url}/search?length=6&digits=false&rating=7&count=3\n"
        f"Authorization: Bearer {api_key[:20]}...</code>\n\n"

        "🎭 <b>Поиск по маске</b>\n"
        "<code>GET /search/mask</code>\n"
        "• <code>mask</code> — маска (pro???, a?b?c)\n\n"
        "Пример:\n"
        f"<code>GET {base_url}/search/mask?mask=pro???\n"
        f"Authorization: Bearer {api_key[:20]}...</code>\n\n"

        "🪤 <b>Управление ловушками</b>\n"
        f"<code>POST {base_url}/trap</code> — добавить\n"
        f"<code>GET {base_url}/traps</code> — список\n"
        f"<code>DELETE {base_url}/trap/username</code> — удалить\n\n"

        "📋 <b>История</b>\n"
        f"<code>GET {base_url}/history?limit=100</code>\n\n"

        "━━━━━━━━━━━━━━━━━\n"
        "📌 <b>Формат ответа (JSON):</b>\n"
        "<code>{\n"
        '  "ok": true,\n'
        '  "results": [\n'
        '    {"username": "abcdef", "rating": 8,\n'
        '     "length": 6, "link": "t.me/abcdef"}\n'
        "  ]\n"
        "}</code>\n\n"

        "📌 <b>Авторизация:</b>\n"
        "<code>Authorization: Bearer &lt;api_key&gt;</code>\n\n"

        "❌ <b>Коды ошибок:</b>\n"
        "• <code>401</code> — неверный ключ\n"
        "• <code>403</code> — подписка истекла\n"
        "• <code>429</code> — превышен лимит"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()
