"""
UqozaSearch REST API — доступен для Luxe подписчиков.
Запускается на отдельном порту рядом с ботом.
"""
import json
import logging
from aiohttp import web

from bot.database import (
    get_user_by_api_key, is_luxe, add_trap,
    get_user_traps, delete_trap, get_last_found,
    increment_search, increment_found, save_found_username,
    get_bulk_used_today, increment_bulk, get_bulk_extra, spend_bulk_extra
)
from bot.utils.username_checker import (
    find_free_usernames, find_free_username, validate_mask
)
from bot.config import BULK_LUXE_PER_DAY, BULK_SIZE

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


async def auth(request: web.Request):
    """Validate API key. Returns (user_row, error_response)."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, web.Response(
            status=401,
            content_type="application/json",
            text=json.dumps({"ok": False, "error": "Missing Authorization header"})
        )
    api_key = header[7:].strip()
    user = await get_user_by_api_key(api_key)
    if not user:
        return None, web.Response(
            status=401,
            content_type="application/json",
            text=json.dumps({"ok": False, "error": "Invalid API key"})
        )
    if not await is_luxe(user["user_id"]):
        return None, web.Response(
            status=403,
            content_type="application/json",
            text=json.dumps({"ok": False, "error": "Luxe subscription required"})
        )
    return user, None


def ok(data: dict) -> web.Response:
    return web.Response(
        status=200,
        content_type="application/json",
        text=json.dumps({"ok": True, **data})
    )


def err(status: int, message: str) -> web.Response:
    return web.Response(
        status=status,
        content_type="application/json",
        text=json.dumps({"ok": False, "error": message})
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@routes.get("/api/v1/search")
async def api_search(request: web.Request):
    user, error = await auth(request)
    if error:
        return error

    try:
        length = int(request.rel_url.query.get("length", "6"))
        if length not in (5, 6):
            return err(400, "length must be 5 or 6")
    except ValueError:
        return err(400, "Invalid length")

    digits = request.rel_url.query.get("digits", "false").lower() == "true"

    try:
        rating = int(request.rel_url.query.get("rating", "1"))
        rating = max(1, min(10, rating))
    except ValueError:
        rating = 1

    try:
        count = int(request.rel_url.query.get("count", "1"))
        count = max(1, min(5, count))
    except ValueError:
        count = 1

    user_id = user["user_id"]
    await increment_search(user_id)

    results = await find_free_usernames(length, digits, min_rating=rating, count=count)

    found = []
    for uname, urating in results:
        await increment_found(user_id)
        await save_found_username(user_id, uname, length, urating)
        found.append({
            "username": uname,
            "rating": urating,
            "length": length,
            "link": f"https://t.me/{uname}"
        })

    return ok({"results": found, "count": len(found)})


@routes.get("/api/v1/search/mask")
async def api_search_mask(request: web.Request):
    user, error = await auth(request)
    if error:
        return error

    mask = request.rel_url.query.get("mask", "").strip()
    if not mask:
        return err(400, "mask parameter required")
    if not validate_mask(mask):
        return err(400, "Invalid mask. Use letters, digits and ? for wildcards. Length 5-32.")

    user_id = user["user_id"]
    await increment_search(user_id)

    result = await find_free_username(len(mask), mask=mask)

    if result:
        uname, urating = result
        await increment_found(user_id)
        await save_found_username(user_id, uname, len(mask), urating)
        return ok({"results": [{"username": uname, "rating": urating,
                                 "length": len(mask), "link": f"https://t.me/{uname}"}],
                    "count": 1})
    return ok({"results": [], "count": 0, "message": "No username found for this mask"})


@routes.get("/api/v1/search/bulk")
async def api_search_bulk(request: web.Request):
    user, error = await auth(request)
    if error:
        return error

    user_id = user["user_id"]
    used = await get_bulk_used_today(user_id)
    extra = await get_bulk_extra(user_id)
    remaining = max(0, BULK_LUXE_PER_DAY - used) + extra

    if remaining <= 0:
        return err(429, f"Bulk search limit reached ({BULK_LUXE_PER_DAY}/day). "
                        "Buy extra attempts in the bot.")

    try:
        length = int(request.rel_url.query.get("length", "6"))
        if length not in (5, 6):
            return err(400, "length must be 5 or 6")
    except ValueError:
        return err(400, "Invalid length")

    digits = request.rel_url.query.get("digits", "false").lower() == "true"

    try:
        rating = int(request.rel_url.query.get("rating", "1"))
        rating = max(1, min(10, rating))
    except ValueError:
        rating = 1

    await increment_bulk(user_id)
    results = await find_free_usernames(length, digits, min_rating=rating,
                                         count=BULK_SIZE, max_attempts=1000)

    found = []
    for uname, urating in results:
        await increment_found(user_id)
        await save_found_username(user_id, uname, length, urating)
        found.append({"username": uname, "rating": urating,
                       "length": length, "link": f"https://t.me/{uname}"})

    new_used = await get_bulk_used_today(user_id)
    new_extra = await get_bulk_extra(user_id)
    return ok({
        "results": found,
        "count": len(found),
        "bulk_remaining": max(0, BULK_LUXE_PER_DAY - new_used) + new_extra
    })


@routes.post("/api/v1/trap")
async def api_add_trap(request: web.Request):
    user, error = await auth(request)
    if error:
        return error

    try:
        body = await request.json()
        username = body.get("username", "").strip().lstrip("@").lower()
    except Exception:
        return err(400, "Invalid JSON body. Expected: {\"username\": \"target\"}")

    if not username or len(username) < 5 or len(username) > 32:
        return err(400, "username must be 5-32 characters")

    await add_trap(user["user_id"], username)
    return ok({"message": f"Trap set for @{username}"})


@routes.get("/api/v1/traps")
async def api_list_traps(request: web.Request):
    user, error = await auth(request)
    if error:
        return error

    traps = await get_user_traps(user["user_id"])
    data = [{"id": t["id"], "username": t["target_username"],
              "created_at": t["created_at"]} for t in traps]
    return ok({"traps": data, "count": len(data)})


@routes.delete("/api/v1/trap/{username}")
async def api_delete_trap(request: web.Request):
    user, error = await auth(request)
    if error:
        return error

    target = request.match_info["username"].lower()
    traps = await get_user_traps(user["user_id"])
    deleted = 0
    for t in traps:
        if t["target_username"] == target:
            await delete_trap(t["id"])
            deleted += 1

    if deleted:
        return ok({"message": f"Trap for @{target} deleted"})
    return err(404, f"No active trap found for @{target}")


@routes.get("/api/v1/history")
async def api_history(request: web.Request):
    user, error = await auth(request)
    if error:
        return error

    try:
        limit = int(request.rel_url.query.get("limit", "100"))
        limit = max(1, min(100, limit))
    except ValueError:
        limit = 100

    records = await get_last_found(user["user_id"], limit=limit)
    data = [{"username": r["username"], "rating": r["rating"],
              "length": r["length"], "found_at": r["found_at"],
              "link": f"https://t.me/{r['username']}"} for r in records]
    return ok({"history": data, "count": len(data)})


@routes.get("/api/v1/status")
async def api_status(request: web.Request):
    user, error = await auth(request)
    if error:
        return error

    from bot.database import get_user, get_today_searches, get_bulk_used_today
    u = await get_user(user["user_id"])
    today = await get_today_searches(user["user_id"])
    bulk_used = await get_bulk_used_today(user["user_id"])
    bulk_extra = await get_bulk_extra(user["user_id"])

    return ok({
        "user_id": user["user_id"],
        "username": u["username"] if u else None,
        "subscription": "luxe",
        "searches_today": today,
        "bulk_used_today": bulk_used,
        "bulk_remaining_today": max(0, BULK_LUXE_PER_DAY - bulk_used) + bulk_extra,
        "bulk_limit_per_day": BULK_LUXE_PER_DAY,
        "found_total": u["found_count"] if u else 0,
    })


@routes.get("/")
async def root(request: web.Request):
    return web.Response(
        content_type="application/json",
        text=json.dumps({
            "service": "UqozaSearch API",
            "version": "1.0",
            "docs": "/api/v1/status",
            "subscription": "Luxe required"
        })
    )


async def start_api_server(port: int):
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"API сервер запущен на порту {port}")
    return runner
