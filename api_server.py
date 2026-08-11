"""
API сервер для UqozaSearch
Эндпоинты:
  GET  /api/v1/status               — проверка работы
  GET  /api/v1/search               — поиск свободных ников
  GET  /api/v1/search/mask          — поиск по маске
  POST /api/v1/trap                 — добавить ловушку
  GET  /api/v1/traps                — список ловушек
  DELETE /api/v1/trap/{username}    — удалить ловушку
  GET  /api/v1/history              — история найденных
Все запросы (кроме /status) требуют Authorization: Bearer <api_key>
"""

import asyncio
import logging
from aiohttp import web
from datetime import datetime

from bot.database import (
    get_user_by_api_key,
    get_user_traps,
    add_trap,
    delete_trap,
    get_last_found,
    update_user_stats,
    save_found_username,
    get_user,
)
from bot.utils.username_checker import find_free_usernames, find_free_username, apply_mask

logger = logging.getLogger(__name__)

# ---------- Вспомогательная функция авторизации ----------
async def authorize(request) -> tuple[dict, web.Response | None]:
    """
    Проверяет заголовок Authorization и возвращает (user, None) при успехе,
    иначе (None, web.Response с ошибкой).
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, web.json_response(
            {"ok": False, "error": "Missing or invalid Authorization header. Use: Bearer <api_key>"},
            status=401
        )
    api_key = auth_header.split(" ")[1]
    user = await get_user_by_api_key(api_key)
    if user is None:
        return None, web.json_response(
            {"ok": False, "error": "Invalid API key"},
            status=401
        )
    # Проверяем подписку (Luxe должна быть активна)
    from bot.database import is_luxe
    if not await is_luxe(user["user_id"]):
        return None, web.json_response(
            {"ok": False, "error": "Luxe subscription expired or not active"},
            status=403
        )
    return user, None


# ---------- Эндпоинты ----------

async def api_status(request):
    """Проверка работы API (без авторизации)."""
    return web.json_response({
        "ok": True,
        "status": "running",
        "timestamp": datetime.now().isoformat()
    })


async def api_search(request):
    """
    GET /api/v1/search?length=6&digits=false&rating=7&count=3
    """
    user, err = await authorize(request)
    if err:
        return err

    try:
        length = int(request.query.get("length", 6))
        digits = request.query.get("digits", "false").lower() == "true"
        rating = int(request.query.get("rating", 1))
        count = min(int(request.query.get("count", 1)), 5)  # максимум 5
    except ValueError:
        return web.json_response({"ok": False, "error": "Invalid parameters"}, status=400)

    if length not in (5, 6):
        return web.json_response({"ok": False, "error": "length must be 5 or 6"}, status=400)
    if not 1 <= rating <= 10:
        return web.json_response({"ok": False, "error": "rating must be 1-10"}, status=400)

    results = await find_free_usernames(
        length=length,
        with_digits=digits,
        min_rating=rating,
        count=count,
        max_attempts=500
    )

    # Обновляем статистику пользователя
    for uname, r in results:
        await update_user_stats(user["user_id"], searched=1, found=1, rating=r)
        await save_found_username(user["user_id"], uname, length, r)

    response = {
        "ok": True,
        "results": [
            {
                "username": uname,
                "rating": r,
                "length": length,
                "link": f"t.me/{uname}"
            }
            for uname, r in results
        ]
    }
    return web.json_response(response)


async def api_search_mask(request):
    """
    GET /api/v1/search/mask?mask=pro???
    """
    user, err = await authorize(request)
    if err:
        return err

    mask = request.query.get("mask")
    if not mask:
        return web.json_response({"ok": False, "error": "mask parameter required"}, status=400)

    # Проверка маски (можно добавить validate_mask)
    if len(mask) < 5 or len(mask) > 32:
        return web.json_response({"ok": False, "error": "mask length must be 5-32"}, status=400)

    # Генерируем один ник по маске
    uname = apply_mask(mask)
    rating = 7  # можно вычислить rate_username, но для простоты ставим 7
    # Проверяем, свободен ли
    from bot.utils.username_checker import is_username_free
    free = await is_username_free(uname)
    results = []
    if free:
        results.append({"username": uname, "rating": rating, "length": len(uname), "link": f"t.me/{uname"})
        await update_user_stats(user["user_id"], searched=1, found=1, rating=rating)
        await save_found_username(user["user_id"], uname, len(uname), rating)
    else:
        await update_user_stats(user["user_id"], searched=1, found=0)

    return web.json_response({
        "ok": True,
        "results": results
    })


async def api_add_trap(request):
    """
    POST /api/v1/trap
    Body: {"username": "example", "interval": 1800}
    """
    user, err = await authorize(request)
    if err:
        return err

    try:
        data = await request.json()
    except:
        return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

    username = data.get("username")
    if not username:
        return web.json_response({"ok": False, "error": "username required"}, status=400)

    interval = data.get("interval", 1800)
    try:
        interval = int(interval)
    except:
        return web.json_response({"ok": False, "error": "interval must be integer"}, status=400)

    await add_trap(user["user_id"], username, interval)

    return web.json_response({
        "ok": True,
        "message": f"Trap for @{username} added with interval {interval}s"
    })


async def api_list_traps(request):
    """
    GET /api/v1/traps
    """
    user, err = await authorize(request)
    if err:
        return err

    traps = await get_user_traps(user["user_id"])
    return web.json_response({
        "ok": True,
        "traps": [
            {
                "id": t["id"],
                "target_username": t["target_username"],
                "check_interval": t["check_interval"],
                "created_at": t["created_at"],
                "last_checked_at": t.get("last_checked_at")
            }
            for t in traps
        ]
    })


async def api_delete_trap(request):
    """
    DELETE /api/v1/trap/{username}
    """
    user, err = await authorize(request)
    if err:
        return err

    username = request.match_info.get("username")
    if not username:
        return web.json_response({"ok": False, "error": "username required"}, status=400)

    # Проверяем, что ловушка принадлежит этому пользователю
    traps = await get_user_traps(user["user_id"])
    for t in traps:
        if t["target_username"].lower() == username.lower():
            await delete_trap(t["id"])
            return web.json_response({"ok": True, "message": f"Trap for @{username} deleted"})

    return web.json_response({"ok": False, "error": "Trap not found"}, status=404)


async def api_history(request):
    """
    GET /api/v1/history?limit=100
    """
    user, err = await authorize(request)
    if err:
        return err

    limit = request.query.get("limit", 100)
    try:
        limit = min(int(limit), 200)
    except:
        limit = 100

    records = await get_last_found(user["user_id"], limit)
    return web.json_response({
        "ok": True,
        "results": [
            {
                "username": r["username"],
                "rating": r["rating"],
                "length": r["length"],
                "found_at": r["found_at"]
            }
            for r in records
        ]
    })


# ---------- Сборка приложения ----------
def create_app():
    app = web.Application()
    app.router.add_get("/api/v1/status", api_status)
    app.router.add_get("/api/v1/search", api_search)
    app.router.add_get("/api/v1/search/mask", api_search_mask)
    app.router.add_post("/api/v1/trap", api_add_trap)
    app.router.add_get("/api/v1/traps", api_list_traps)
    app.router.add_delete("/api/v1/trap/{username}", api_delete_trap)
    app.router.add_get("/api/v1/history", api_history)
    return app


# ---------- Запуск ----------
async def start_api_server(port: int = 8080):
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logger.info(f"API сервер запущен на порту {port}")
    return runner
