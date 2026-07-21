from contextlib import asynccontextmanager
import asyncio
import json
import logging

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response, StreamingResponse

from config import (
    PRODUCTION,
    UVICORN_WORKERS,
    ACTIVE_DB_PROFILE,
    APP_MODE,
    DB_HOST,
    DB_NAME,
    DB_PORT,
    cors_origins,
    app_mode_summary,
    db_connection_label,
    validate_security_settings,
    assert_security_startup,
)
from db import db
from error_codes import ERROR_CATALOG, error_meaning, error_title
from error_reporter import schedule_error_report, schedule_http_error, schedule_security_alert, schedule_server_exception
from admin_routes import router as admin_router
from support_routes import router as support_router
from maintenance import MAINTENANCE_MESSAGE, is_maintenance, maintenance_http_error
from notification_hub import encode_sse, subscribe, unsubscribe
from rate_limit import rate_limit
from auth import get_user_id
from security_watch import report_if_suspicious

logger = logging.getLogger("cute-farm")

_PUBLIC_PATHS = frozenset({"/health", "/api/status", "/admin/api/health"})


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if PRODUCTION:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class MaintenanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if is_maintenance() and path not in _PUBLIC_PATHS and not path.startswith("/admin/api/"):
            return JSONResponse(
                status_code=503,
                content={"detail": MAINTENANCE_MESSAGE},
            )
        return await call_next(request)



class SecurityWatchMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        report_if_suspicious(request)
        return await call_next(request)


_IP_BAN_EXEMPT = frozenset({"/health", "/admin/api/health"})
_IP_BAN_EXEMPT_PREFIX = "/admin/api/auth/"


class IpBanMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        # Never block admin auth (so admins can always log in to manage bans)
        # and health checks
        if path in _IP_BAN_EXEMPT or path.startswith(_IP_BAN_EXEMPT_PREFIX):
            return await call_next(request)
        from ip_ban import is_ip_banned_sync
        forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        ip = forwarded[:64] if forwarded else (request.client.host if request.client else "")
        import logging as _log
        _log.getLogger("ip_ban.mw").debug("request ip=%r path=%s", ip, request.url.path)
        if ip and is_ip_banned_sync(ip):
            return JSONResponse(
                status_code=403,
                content={"detail": "Доступ заблокирован", "code": "ERR_IP_BANNED"},
            )
        return await call_next(request)


class BodyUserIdGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "POST" and request.url.path.startswith("/api/"):
            body = await request.body()
            if body:
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    data = None
                if isinstance(data, dict):
                    if "user_id" in data or "userId" in data:
                        schedule_security_alert(
                            "ERR_SEC_BODY_UID",
                            request=request,
                            message="user_id/userId в JSON",
                            status=400,
                        )
                        return JSONResponse(
                            status_code=400,
                            content={"detail": "user_id берётся только из Telegram initData"},
                        )
                    if any(key in data for key in ("balance", "kut", "amount", "paid")):
                        schedule_security_alert(
                            "ERR_SEC_BODY_BALANCE",
                            request=request,
                            message=f"поля: {', '.join(k for k in ('balance','kut','amount','paid') if k in data)}",
                            status=400,
                        )
                        return JSONResponse(
                            status_code=400,
                            content={"detail": "Баланс меняется только на сервере"},
                        )

            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}

            request = Request(request.scope, receive)

        return await call_next(request)


async def _mute_cleanup_loop(stop: asyncio.Event) -> None:
    """Каждую минуту снимает истёкшие муты и инвалидирует кэш."""
    while not stop.is_set():
        try:
            rows = await db.pool.fetch(
                """
                UPDATE users SET mute_until = NULL
                WHERE mute_until IS NOT NULL AND mute_until < NOW()
                RETURNING user_id
                """
            )
            if rows:
                from rate_limit import invalidate_ban_cache
                for r in rows:
                    invalidate_ban_cache(r["user_id"])
                logger.info("mute_cleanup: сняли мут с %d игроков", len(rows))
        except Exception as exc:
            logger.warning("mute_cleanup error: %s", exc)
        try:
            await asyncio.wait_for(stop.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass


@asynccontextmanager
async def lifespan(application: FastAPI):
    assert_security_startup()
    for warning in validate_security_settings():
        logger.warning("SECURITY: %s", warning)
    logger.info("Database target: %s", db_connection_label())
    logger.info("Runtime mode: %s", app_mode_summary())
    from config import log_bot_tokens_startup
    await log_bot_tokens_startup(logger)
    if UVICORN_WORKERS > 1:
        logger.warning(
            "UVICORN_WORKERS=%s: rate limit, SSE и IP-ban кэш — in-memory на процесс. "
            "Для горизонтального масштаба нужен Redis.",
            UVICORN_WORKERS,
        )
    from config import DB_POOL_MAX
    est_pool = UVICORN_WORKERS * max(5, DB_POOL_MAX)
    if est_pool > 40:
        logger.warning(
            "DB pool: %s workers × DB_POOL_MAX=%s ≈ %s соединений с API. "
            "На Managed Postgres (25–97 conn) уменьшите DB_POOL_MAX или workers.",
            UVICORN_WORKERS,
            DB_POOL_MAX,
            est_pool,
        )
    await db.connect()

    from support_db import ensure_tables as ensure_support_tables
    try:
        await ensure_support_tables()
    except Exception:
        logger.warning("Support tables init failed — check DB permissions")

    from admin_broadcast import recover_orphaned_broadcasts
    from ip_ban import init_ip_ban_cache

    recovered = await recover_orphaned_broadcasts()
    if recovered:
        logger.info("Recovered %s orphaned broadcast(s)", recovered)

    await init_ip_ban_cache()

    from presence import online_snapshot_loop
    from event_scheduler import event_scheduler_loop

    stop_online = asyncio.Event()
    online_task = asyncio.create_task(online_snapshot_loop(stop_online))

    stop_scheduler = asyncio.Event()
    scheduler_task = asyncio.create_task(event_scheduler_loop(stop_scheduler))

    from staff_notify import staff_salary_reminder_loop
    stop_reminder = asyncio.Event()
    reminder_task = asyncio.create_task(staff_salary_reminder_loop(stop_reminder))

    from support_cleanup import support_cleanup_loop
    stop_support_cleanup = asyncio.Event()
    support_cleanup_task = asyncio.create_task(support_cleanup_loop(stop_support_cleanup))

    stop_mute_cleanup = asyncio.Event()
    mute_cleanup_task = asyncio.create_task(_mute_cleanup_loop(stop_mute_cleanup))

    yield

    stop_online.set()
    online_task.cancel()
    stop_scheduler.set()
    scheduler_task.cancel()
    stop_reminder.set()
    reminder_task.cancel()
    stop_support_cleanup.set()
    support_cleanup_task.cancel()
    stop_mute_cleanup.set()
    mute_cleanup_task.cancel()
    for t in (online_task, scheduler_task, reminder_task, support_cleanup_task, mute_cleanup_task):
        try:
            await t
        except asyncio.CancelledError:
            pass
    await db.close()


app = FastAPI(title="Cute Farm", lifespan=lifespan, docs_url=None if PRODUCTION else "/docs")


class UserIdStateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.user_id = None
        return await call_next(request)


app.add_middleware(UserIdStateMiddleware)
app.add_middleware(IpBanMiddleware)
app.add_middleware(SecurityWatchMiddleware)
app.add_middleware(MaintenanceMiddleware)
app.add_middleware(BodyUserIdGuardMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Accept",
        "Authorization",
        "X-Telegram-Init-Data",
        "X-Dev-User-Id",
        "X-Client-Info",
    ],
)

app.include_router(admin_router)
app.include_router(support_router)


class FarmPlantAction(BaseModel):
    plotId: int = Field(ge=1, le=100)
    seedItemId: str = Field(min_length=1, max_length=32)
    model_config = {"extra": "forbid"}


class FarmWaterAction(BaseModel):
    plotId: int = Field(ge=1, le=100)
    waterItemId: str | None = Field(default=None, max_length=32)
    model_config = {"extra": "forbid"}


class PlotAction(BaseModel):
    plotId: int = Field(ge=1, le=100)
    model_config = {"extra": "forbid"}


class ClaimDailySeedBody(BaseModel):
    seedItemId: str | None = Field(default=None, max_length=32)
    model_config = {"extra": "forbid"}


class ClaimQuestBody(BaseModel):
    questId: str = Field(..., min_length=1, max_length=64)
    model_config = {"extra": "forbid"}


class AcceptQuestBody(BaseModel):
    questId: str = Field(..., min_length=1, max_length=64)
    model_config = {"extra": "forbid"}


class CancelQuestBody(BaseModel):
    questId: str = Field(..., min_length=1, max_length=64)
    model_config = {"extra": "forbid"}


class ParticipateGiveawayBody(BaseModel):
    model_config = {"extra": "forbid"}


class ShopBuyAction(BaseModel):
    itemId: str = Field(min_length=1)
    category: str = "all"
    page: int = Field(default=0, ge=0)
    search: str = ""
    quantity: int = Field(default=1, ge=1, le=99)
    priceFilter: str = "all"
    sortBy: str = "name"
    sortOrder: str = "asc"
    pageSize: int = Field(default=8, ge=8, le=16)
    useCoupon: bool = False
    model_config = {"extra": "forbid"}


class MarketCatalogQuery(BaseModel):
    category: str = "all"
    page: int = Field(default=0, ge=0)
    search: str = ""
    priceFilter: str = "all"
    sortBy: str = "name"
    sortOrder: str = "asc"
    pageSize: int = Field(default=8, ge=8, le=16)


class MarketListAction(MarketCatalogQuery):
    itemId: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1, le=99)
    price: int = Field(ge=1, le=999_999)
    model_config = {"extra": "forbid"}


class MarketBuyAction(MarketCatalogQuery):
    listingId: int = Field(ge=1)
    quantity: int = Field(default=1, ge=1, le=99)
    model_config = {"extra": "forbid"}


class MarketCancelAction(MarketCatalogQuery):
    listingId: int = Field(ge=1)
    model_config = {"extra": "forbid"}


class CraftExecuteAction(BaseModel):
    slotA: str = Field(min_length=1, max_length=64)
    slotB: str = Field(min_length=1, max_length=64)
    model_config = {"extra": "forbid"}


class NotificationsAckAction(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=20)
    model_config = {"extra": "forbid"}


class ClientErrorReport(BaseModel):
    code: str = Field(min_length=3, max_length=64)
    message: str = Field(default="", max_length=500)
    path: str = Field(default="", max_length=200)
    context: str = Field(default="", max_length=200)
    model_config = {"extra": "forbid"}


class ComplaintBody(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)
    subject: str = Field(default="", max_length=300)
    model_config = {"extra": "forbid"}


class OnboardingPrepareBody(BaseModel):
    step: str = Field(pattern="^(plant|water|harvest)$")
    model_config = {"extra": "forbid"}


class OnboardingCompleteBody(BaseModel):
    skipped: bool = False
    model_config = {"extra": "forbid"}


class OnboardingStepBody(BaseModel):
    step: int = Field(ge=0, le=8)
    model_config = {"extra": "forbid"}


class PresenceBody(BaseModel):
    platform: str | None = Field(default=None, max_length=64)
    tgPlatform: str | None = Field(default=None, max_length=64)
    appVersion: str | None = Field(default=None, max_length=32)
    userAgent: str | None = Field(default=None, max_length=500)
    language: str | None = Field(default=None, max_length=32)
    navigatorLanguage: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)
    colorScheme: str | None = Field(default=None, max_length=16)
    deviceModel: str | None = Field(default=None, max_length=120)
    viewportWidth: int | None = Field(default=None, ge=0, le=10000)
    viewportHeight: int | None = Field(default=None, ge=0, le=10000)
    screenWidth: int | None = Field(default=None, ge=0, le=10000)
    screenHeight: int | None = Field(default=None, ge=0, le=10000)
    isExpanded: bool | None = None
    isPremium: bool | None = None
    model_config = {"extra": "ignore"}


class SessionSyncBody(PresenceBody):
    pass


def _request_user_id(request: Request) -> int | None:
    raw = getattr(request.state, "user_id", None)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _client_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _server_error(exc: Exception, request: Request) -> HTTPException:
    logger.exception("API error")
    schedule_server_exception(
        user_id=_request_user_id(request),
        method=request.method,
        path=request.url.path,
        exc=exc,
    )
    detail = "Внутренняя ошибка сервера" if PRODUCTION else str(exc)
    http_exc = HTTPException(status_code=500, detail=detail)
    # Уже залогировано выше через schedule_server_exception — не даём
    # http_exception_handler записать вторую строку в system_logs для той же ошибки.
    http_exc._already_reported = True
    return http_exc


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    if not getattr(exc, "_already_reported", False):
        schedule_http_error(
            user_id=_request_user_id(request),
            method=request.method,
            path=request.url.path,
            status=exc.status_code,
            detail=detail,
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    detail = "Неверный формат запроса"
    if not PRODUCTION and exc.errors():
        first = exc.errors()[0]
        loc = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        msg = first.get("msg", "")
        if loc:
            detail = f"{detail}: {loc} — {msg}"
        elif msg:
            detail = f"{detail}: {msg}"
    schedule_security_alert(
        "ERR_SEC_EXTRA_FIELDS",
        request=request,
        message=detail,
        status=422,
    )
    return JSONResponse(status_code=422, content={"detail": detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    schedule_server_exception(
        user_id=_request_user_id(request),
        method=request.method,
        path=request.url.path,
        exc=exc,
    )
    logger.exception("Unhandled API error")
    detail = "Внутренняя ошибка сервера" if PRODUCTION else str(exc)
    return JSONResponse(status_code=500, content={"detail": detail})


@app.get("/health")
async def health():
    live_db = DB_NAME
    live_users = db.connected_user_count
    if db.pool is not None:
        try:
            async with db.pool.acquire() as conn:
                live_db = await conn.fetchval("SELECT current_database()")
                live_users = await conn.fetchval("SELECT COUNT(*)::int FROM users")
        except Exception:
            pass
    return {
        "ok": True,
        "maintenance": is_maintenance(),
        "app_mode": APP_MODE,
        "db_profile": ACTIVE_DB_PROFILE,
        "db_name": DB_NAME,
        "db_host": DB_HOST,
        "db_port": DB_PORT,
        "db_connected": live_db,
        "users_count": live_users,
    }


@app.get("/api/status")
async def api_status(request: Request):
    from config import SUPPORT_BOT_URL
    from private_mode import PRIVATE_MODE, is_allowed

    # Если приватный режим включён — проверяем init data прямо здесь,
    # чтобы заблокированный пользователь получил 503 ещё до загрузки UI.
    if PRIVATE_MODE is not None:
        init_data = request.headers.get("X-Telegram-Init-Data")
        dev_user_id = request.headers.get("X-Dev-User-Id")
        uid: int | None = None
        if init_data:
            try:
                from auth import _validate_telegram_init_data
                uid = _validate_telegram_init_data(init_data, request)
            except Exception:
                pass
        elif dev_user_id:
            try:
                uid = int(dev_user_id)
            except ValueError:
                pass
        if uid is not None and not is_allowed(uid):
            raise HTTPException(status_code=503, detail="сервис временно недоступен")

    return {
        "ok": not is_maintenance(),
        "maintenance": is_maintenance(),
        "supportBotUrl": SUPPORT_BOT_URL or None,
    }


@app.post("/api/presence")
async def presence_ping(
    request: Request,
    body: PresenceBody | None = None,
    user_id: int = Depends(rate_limit),
):
    if is_maintenance():
        raise maintenance_http_error()
    try:
        await db.ensure_user(user_id)
        from presence import mark_user_online
        from user_client import sync_user_client_info

        tg_user = getattr(request.state, "telegram_user", None)
        if tg_user:
            await db.sync_user_profile_throttled(user_id, tg_user)
        await sync_user_client_info(
            user_id,
            request,
            body.model_dump(exclude_none=True) if body else None,
            tg_user,
            force=True,
        )
        await mark_user_online(user_id)
        return {"ok": True}
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/session/sync")
async def session_sync(
    request: Request,
    body: SessionSyncBody | None = None,
    user_id: int = Depends(rate_limit),
):
    if is_maintenance():
        raise maintenance_http_error()
    try:
        await db.ensure_user(user_id)
        from user_client import sync_user_client_info

        tg_user = getattr(request.state, "telegram_user", None)
        await sync_user_client_info(
            user_id,
            request,
            body.model_dump(exclude_none=True) if body else None,
            tg_user,
            force=True,
        )
        # Один раз при входе в WebApp сверяем инвентарь с dex и молча убираем
        # предметы, которых больше нет в магазине. Не должно ронять вход —
        # сбой здесь не критичнее устаревшего предмета в инвентаре.
        try:
            await db.sanitize_user_items_against_dex(user_id)
        except Exception as sanitize_err:
            logger.warning(
                "sanitize_user_items_against_dex failed for %s: %s",
                user_id, sanitize_err,
            )
        return {"ok": True}
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/presence/leave")
async def presence_leave(request: Request, user_id: int = Depends(rate_limit)):
    if is_maintenance():
        raise maintenance_http_error()
    try:
        from presence import mark_user_offline

        await mark_user_offline(user_id)
        return {"ok": True}
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/error-codes")
async def api_error_codes():
    return {
        "codes": [
            {
                "code": code,
                "title": meta["title"],
                "meaning": meta["meaning"],
                "security": code.startswith("ERR_SEC_"),
            }
            for code, meta in ERROR_CATALOG.items()
        ]
    }


@app.post("/api/complaints")
async def submit_player_complaint(
    body: ComplaintBody,
    request: Request,
    user_id: int = Depends(rate_limit),
):
    if is_maintenance():
        raise maintenance_http_error()
    try:
        from admin_db import create_player_complaint
        from staff_notify import notify_owners

        complaint_id = await create_player_complaint(
            user_id, None, body.subject.strip(), body.reason.strip(),
        )
        notify_owners(f"<tg-emoji emoji-id='5222453530677225961'>🚨</tg-emoji> <b>Жалоба от игрока {user_id} на модерацию.</b>")
        return {"ok": True, "complaintId": complaint_id}
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/farm/state")
async def farm_state(request: Request, user_id: int = Depends(rate_limit)):
    if is_maintenance():
        raise maintenance_http_error()
    try:
        return await db.get_farm_state(user_id, persist_sync=False)
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/inventory")
async def inventory_state(request: Request, user_id: int = Depends(rate_limit)):
    if is_maintenance():
        raise maintenance_http_error()
    try:
        return await db.get_inventory_state(user_id)
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/farm/plant")
async def farm_plant(body: FarmPlantAction, user_id: int = Depends(rate_limit)):
    try:
        return await db.plant_seed(user_id, body.plotId, body.seedItemId)
    except ValueError as e:
        raise _client_error(e)


@app.post("/api/farm/water")
async def farm_water(body: FarmWaterAction, user_id: int = Depends(rate_limit)):
    try:
        return await db.water_plot(user_id, body.plotId, body.waterItemId)
    except ValueError as e:
        raise _client_error(e)


@app.post("/api/farm/autowater")
async def farm_autowater(body: PlotAction, request: Request, user_id: int = Depends(rate_limit)):
    try:
        return await db.install_autowater(user_id, body.plotId)
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/farm/harvest")
async def farm_harvest(body: PlotAction, user_id: int = Depends(rate_limit)):
    try:
        return await db.harvest_plot(user_id, body.plotId)
    except ValueError as e:
        raise _client_error(e)


@app.post("/api/farm/clear")
async def farm_clear(body: PlotAction, user_id: int = Depends(rate_limit)):
    try:
        return await db.clear_plot(user_id, body.plotId)
    except ValueError as e:
        raise _client_error(e)


@app.post("/api/farm/buy-plot")
async def farm_buy_plot(user_id: int = Depends(rate_limit)):
    try:
        return await db.buy_plot(user_id)
    except ValueError as e:
        raise _client_error(e)


@app.post("/api/farm/claim-daily-seed")
async def farm_claim_daily_seed(
    body: ClaimDailySeedBody,
    user_id: int = Depends(rate_limit),
):
    try:
        return await db.claim_daily_seed(user_id, seed_item_id=body.seedItemId)
    except ValueError as e:
        raise _client_error(e)


@app.get("/api/quests/state")
async def quests_state(request: Request, user_id: int = Depends(rate_limit)):
    if is_maintenance():
        raise maintenance_http_error()
    try:
        return await db.get_quests_state(user_id)
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/quests/accept")
async def quests_accept(body: AcceptQuestBody, user_id: int = Depends(rate_limit)):
    try:
        return await db.accept_quest(user_id, body.questId)
    except ValueError as e:
        raise _client_error(e)


@app.post("/api/quests/cancel")
async def quests_cancel(body: CancelQuestBody, user_id: int = Depends(rate_limit)):
    try:
        return await db.cancel_quest(user_id, body.questId)
    except ValueError as e:
        raise _client_error(e)


@app.post("/api/quests/claim")
async def quests_claim(body: ClaimQuestBody, user_id: int = Depends(rate_limit)):
    try:
        return await db.claim_quest_reward(user_id, body.questId)
    except ValueError as e:
        raise _client_error(e)


@app.get("/api/giveaways")
async def giveaways_state(request: Request, user_id: int = Depends(rate_limit)):
    if is_maintenance():
        raise maintenance_http_error()
    try:
        return await db.get_giveaways_state(user_id)
    except Exception as e:
        raise _server_error(e, request)


# ВАЖНО: литеральные маршруты (/history, /winners-feed) должны быть
# зарегистрированы РАНЬШЕ динамического /{giveaway_id}, иначе FastAPI
# сопоставит "history"/"winners-feed" с {giveaway_id: int}, парсинг в int
# упадёт → 422 «Неверный формат запроса». См. test_giveaway_routes_order.py.
@app.get("/api/giveaways/history")
async def giveaways_history(request: Request, user_id: int = Depends(rate_limit)):
    if is_maintenance():
        raise maintenance_http_error()
    try:
        return await db.get_giveaways_history()
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/giveaways/winners-feed")
async def giveaways_winners_feed(request: Request, user_id: int = Depends(rate_limit)):
    if is_maintenance():
        raise maintenance_http_error()
    try:
        return await db.get_giveaway_winners_feed()
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/giveaways/{giveaway_id}")
async def giveaway_detail(giveaway_id: int, request: Request, user_id: int = Depends(rate_limit)):
    try:
        return await db.get_giveaway_detail(user_id, giveaway_id)
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/giveaways/{giveaway_id}/participate")
async def giveaway_participate(
    giveaway_id: int,
    body: ParticipateGiveawayBody,
    user_id: int = Depends(rate_limit),
):
    try:
        return await db.participate_in_giveaway(user_id, giveaway_id)
    except ValueError as e:
        raise _client_error(e)


@app.get("/api/shop/catalog")
async def shop_catalog(
    request: Request,
    user_id: int = Depends(rate_limit),
    category: str = "all",
    page: int = 0,
    search: str = "",
    priceFilter: str = "all",
    sortBy: str = "name",
    sortOrder: str = "asc",
    pageSize: int = 8,
):
    try:
        return await db.get_shop_catalog(
            user_id,
            category_id=category,
            page=page,
            search=search,
            price_filter=priceFilter,
            sort_by=sortBy,
            sort_order=sortOrder,
            page_size=pageSize,
        )
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/shop/buy")
async def shop_buy(request: Request, body: ShopBuyAction, user_id: int = Depends(rate_limit)):
    try:
        return await db.buy_shop_item(
            user_id,
            body.itemId,
            category_id=body.category,
            page=body.page,
            search=body.search,
            quantity=body.quantity,
            price_filter=body.priceFilter,
            sort_by=body.sortBy,
            sort_order=body.sortOrder,
            page_size=body.pageSize,
            use_coupon=body.useCoupon,
        )
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/market/catalog")
async def market_catalog(
    request: Request,
    user_id: int = Depends(rate_limit),
    category: str = "all",
    page: int = 0,
    search: str = "",
    priceFilter: str = "all",
    sortBy: str = "name",
    sortOrder: str = "asc",
    pageSize: int = 8,
):
    try:
        return await db.get_market_catalog(
            user_id,
            category_id=category,
            page=page,
            search=search,
            price_filter=priceFilter,
            sort_by=sortBy,
            sort_order=sortOrder,
            page_size=pageSize,
        )
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/market/sellable")
async def market_sellable(request: Request, user_id: int = Depends(rate_limit)):
    try:
        return await db.get_market_sellable(user_id)
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/market/list")
async def market_list(request: Request, body: MarketListAction, user_id: int = Depends(rate_limit)):
    try:
        return await db.create_market_listing(
            user_id,
            body.itemId,
            body.quantity,
            body.price,
            category_id=body.category,
            page=body.page,
            search=body.search,
            price_filter=body.priceFilter,
            sort_by=body.sortBy,
            sort_order=body.sortOrder,
            page_size=body.pageSize,
        )
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/market/buy")
async def market_buy(request: Request, body: MarketBuyAction, user_id: int = Depends(rate_limit)):
    try:
        return await db.buy_market_listing(
            user_id,
            body.listingId,
            body.quantity,
            category_id=body.category,
            page=body.page,
            search=body.search,
            price_filter=body.priceFilter,
            sort_by=body.sortBy,
            sort_order=body.sortOrder,
            page_size=body.pageSize,
        )
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/market/cancel")
async def market_cancel(request: Request, body: MarketCancelAction, user_id: int = Depends(rate_limit)):
    try:
        return await db.cancel_market_listing(
            user_id,
            body.listingId,
            category_id=body.category,
            page=body.page,
            search=body.search,
            price_filter=body.priceFilter,
            sort_by=body.sortBy,
            sort_order=body.sortOrder,
            page_size=body.pageSize,
        )
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/me")
async def my_profile(request: Request, user_id: int = Depends(rate_limit)):
    """Профиль текущего игрока + лидерборды."""
    try:
        return await db.get_my_profile_and_leaderboard(user_id)
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/profile/{target_user_id}")
async def user_profile(
    target_user_id: int,
    request: Request,
    user_id: int = Depends(rate_limit),
):
    try:
        return await db.get_public_profile(user_id, target_user_id)
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/craft/recipes")
async def craft_recipes(request: Request, user_id: int = Depends(rate_limit)):
    try:
        return await db.get_craft_recipes(user_id)
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/craft/execute")
async def craft_execute(request: Request, body: CraftExecuteAction, user_id: int = Depends(rate_limit)):
    try:
        return await db.execute_craft(user_id, body.slotA, body.slotB)
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/notifications")
async def notifications_poll(request: Request, user_id: int = Depends(rate_limit)):
    try:
        items = await db.get_pending_notifications(user_id)
        return {"notifications": items}
    except Exception as e:
        raise _server_error(e, request)


@app.get("/api/notifications/stream")
async def notifications_stream(request: Request, user_id: int = Depends(rate_limit)):
    queue = subscribe(user_id)
    if queue is None:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Слишком много активных соединений. Уведомления через опрос.",
                "code": "ERR_SSE_LIMIT",
            },
        )

    async def event_generator():
        try:
            pending = await db.get_pending_notifications(user_id)
            for item in pending:
                yield encode_sse(item)

            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=25.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield encode_sse(item)
        finally:
            unsubscribe(user_id, queue)

    try:
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        unsubscribe(user_id, queue)
        raise _server_error(e, request)


@app.post("/api/notifications/ack")
async def notifications_ack(
    request: Request,
    body: NotificationsAckAction,
    user_id: int = Depends(rate_limit),
):
    try:
        acked = await db.ack_notifications(user_id, body.ids)
        return {"acked": acked}
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/onboarding/start")
async def onboarding_start(request: Request, user_id: int = Depends(rate_limit)):
    try:
        return await db.start_onboarding(user_id)
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/onboarding/prepare")
async def onboarding_prepare(
    request: Request,
    body: OnboardingPrepareBody,
    user_id: int = Depends(rate_limit),
):
    try:
        return await db.prepare_onboarding_step(user_id, body.step)
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/onboarding/complete")
async def onboarding_complete(
    request: Request,
    body: OnboardingCompleteBody,
    user_id: int = Depends(rate_limit),
):
    try:
        return await db.complete_onboarding(user_id, skipped=body.skipped)
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


@app.post("/api/onboarding/step")
async def onboarding_save_step(
    request: Request,
    body: OnboardingStepBody,
    user_id: int = Depends(rate_limit),
):
    try:
        return await db.save_onboarding_step(user_id, body.step)
    except ValueError as e:
        raise _client_error(e)
    except Exception as e:
        raise _server_error(e, request)


class AppealBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)


@app.post("/api/appeal")
async def submit_appeal(
    body: AppealBody,
    request: Request,
    user_id: int = Depends(get_user_id),
):
    """Подача апелляции — доступна даже забаненным игрокам."""
    from admin_appeals import submit_appeal as _submit
    tg_user = getattr(request.state, "telegram_user", {}) or {}

    row = await db.pool.fetchrow(
        "SELECT banned, banned_reason, first_name, username FROM users WHERE user_id = $1",
        user_id,
    )
    if not row or not row["banned"]:
        raise HTTPException(status_code=400, detail="Ваш аккаунт не заблокирован")

    try:
        result = await _submit(
            user_id,
            body.text,
            username=tg_user.get("username") or row["username"] or "",
            first_name=tg_user.get("first_name") or row["first_name"] or "",
            ban_reason=row["banned_reason"] or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@app.get("/api/appeal/status")
async def appeal_status(user_id: int = Depends(get_user_id)):
    from admin_appeals import get_player_appeal_status
    return await get_player_appeal_status(user_id) or {"status": None}


@app.post("/api/settings/harvest-notify")
async def toggle_harvest_notify(request: Request, user_id: int = Depends(rate_limit)):
    body = await request.json()
    enabled = bool(body.get("enabled", False))
    await db.pool.execute(
        "UPDATE users SET harvest_notify = $2 WHERE user_id = $1",
        user_id, enabled,
    )
    return {"harvestNotify": enabled}


@app.get("/api/settings")
async def get_settings(user_id: int = Depends(rate_limit)):
    row = await db.pool.fetchrow(
        "SELECT harvest_notify FROM users WHERE user_id = $1", user_id
    )
    return {"harvestNotify": bool(row["harvest_notify"]) if row else False}


@app.post("/api/settings/harvest-notify-test")
async def test_harvest_notify(user_id: int = Depends(rate_limit)):
    """Тест: шлёт уведомление прямо сейчас (для проверки что токен работает)."""
    from config import BOT_TOKEN
    import aiohttp
    if not BOT_TOKEN:
        raise HTTPException(500, "BOT_TOKEN не настроен")
    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": user_id, "text": "<tg-emoji emoji-id='5436085410138703352'>🌾</tg-emoji><tg-emoji emoji-id='5436321070699268504'>🌾</tg-emoji> <b>Тест уведомлений работает!</b>", "parse_mode": "HTML"},
            timeout=aiohttp.ClientTimeout(total=8),
        )
        data = await resp.json()
    if not data.get("ok"):
        raise HTTPException(502, f"Telegram: {data.get('description', 'ошибка')}")
    return {"ok": True}


@app.post("/api/report-error")
async def report_client_error(
    body: ClientErrorReport,
    user_id: int = Depends(rate_limit),
):
    schedule_error_report(
        body.code,
        user_id=user_id,
        path=body.path,
        method="CLIENT",
        message=body.message or body.context,
        source="client",
    )
    return {"ok": True}
