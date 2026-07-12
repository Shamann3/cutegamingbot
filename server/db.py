import secrets
import random
import json
import logging
import os
import time
from datetime import timedelta
from datetime import datetime
from pathlib import Path

import asyncpg

from config import (
    AUTOWATER_ITEM_KEY,
    AXE_ITEM_KEY,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    DATABASE_URL,
    SEED_ITEM_KEY,
    SHOP_CATALOG_CACHE_SECONDS,
    TOBACCO_ITEM_KEY,
    TOBACCO_SEED_ITEM_KEY,
    TREE_ITEM_KEY,
    WATER_ITEM_KEY,
    db_ssl_mode,
)
from farm_crops import (
    balance_bar_for_client,
    crops_for_client,
    get_crop_by_seed,
    get_crop_for_plot,
    normalize_seed_id,
    roll_harvest_drops,
    water_config_for_crop,
    resolve_water_item_for_action,
)
from farm_logic import (
    apply_autowater,
    apply_harvest,
    apply_plant,
    apply_water,
    is_dry,
    normalize_grow_row,
    now,
    plot_to_json,
    sync_growing_plot,
)
from tool_durability import (
    apply_harvest_tool,
    axe_state_for_client,
    parse_tool_durability,
    tool_durability_to_db,
)
from migrate_items import migrate_all_users_items
from dex_catalog import dex_catalog, farm_item_ids_for_client
from shop_cache import build_shop_catalog_cache
from audit_log import schedule_balance_event
from game_events_log import log_game_event
from user_notify import create_market_sale_notification, schedule_market_sale_telegram
from item_catalog import items_for_display, merge_items_for_storage, normalize_items
from user_items import (
    add_item,
    add_shop_item_to_storage,
    can_craft,
    count_item,
    items_to_db,
    log_count,
    parse_items,
    plot_buy_price,
    seed_count,
    plantable_seed_counts,
    take_craft_ingredients,
    take_item,
    take_item_from_storage,
    tobacco_seed_count,
    water_count,
    autowater_count,
)

ONBOARDING_PLOT_ID = 1
ONBOARDING_PREPARE_STEP_INDEX = {"plant": 2, "water": 3, "harvest": 4}


def reconcile_onboarding_step(step, plot):
    step = max(0, int(step or 0))
    if not plot:
        return step
    status = plot.get("status")
    if status == "GROWING":
        return max(step, ONBOARDING_PREPARE_STEP_INDEX["water"])
    if status == "READY":
        return max(step, ONBOARDING_PREPARE_STEP_INDEX["harvest"])
    if status == "EMPTY":
        if step >= ONBOARDING_PREPARE_STEP_INDEX["harvest"]:
            return max(step, 5)
        if step >= ONBOARDING_PREPARE_STEP_INDEX["water"]:
            return ONBOARDING_PREPARE_STEP_INDEX["plant"]
    return step


def ensure_onboarding_demo_seeds(game_items):
    """Для обучения: по 1 семечку дерева и табака, если их нет."""
    changed = False
    if seed_count(game_items) < 1:
        game_items = add_item(game_items, SEED_ITEM_KEY, 1)
        changed = True
    if tobacco_seed_count(game_items) < 1:
        game_items = add_item(game_items, TOBACCO_SEED_ITEM_KEY, 1)
        changed = True
    return game_items, changed


class Database:
    """PostgreSQL — users.balance, users.items, farm_plots."""

    def __init__(self):
        self.pool = None
        self._shop_catalog_cache = build_shop_catalog_cache(SHOP_CATALOG_CACHE_SECONDS)
        self._profile_sync_at = {}
        self.connected_user_count = 0

    async def connect(self):
        if self.pool is not None:
            return
        ssl = db_ssl_mode()
        from config import (
            ACTIVE_DB_PROFILE,
            APP_MODE,
            DB_POOL_MAX,
            DB_POOL_MIN,
            DB_LOCATION,
        )

        # Pool tuned for a fast, warm connection:
        #  - min_size keeps connections pre-opened so the first query is instant;
        #  - command_timeout stops a hung query from blocking forever;
        #  - max_inactive_connection_lifetime recycles idle links (SSH tunnel safe);
        #  - statement_cache_size caches prepared statements for repeat queries.
        pool_kwargs = {
            "min_size": max(1, DB_POOL_MIN),
            "max_size": max(5, DB_POOL_MAX),
            "ssl": ssl,
            "timeout": 10,
            "command_timeout": 30,
            "max_inactive_connection_lifetime": 300,
            "statement_cache_size": 0,
        }
        _t0 = time.perf_counter()
        _via = (
            f"SSH tunnel :{DB_PORT}"
            if DB_LOCATION == "remote"
            else "local"
        )
        print(
            f"[DB] connecting -> APP_MODE={APP_MODE} profile={ACTIVE_DB_PROFILE} "
            f"{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME} ({_via})"
        )
        try:
            if DATABASE_URL:
                self.pool = await asyncpg.create_pool(DATABASE_URL, **pool_kwargs)
            else:
                self.pool = await asyncpg.create_pool(
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                    host=DB_HOST,
                    port=DB_PORT,
                    **pool_kwargs,
                )
        except Exception as exc:
            target = "DATABASE_URL" if DATABASE_URL else f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
            print(f"[DB][FATAL] cannot connect to {target}: {type(exc).__name__}: {exc}")
            raise RuntimeError(
                f"Не подключиться к PostgreSQL: {target} (user={DB_USER}). "
                "Проверь: 1) PostgreSQL запущен, 2) пароль в server/.env ТОЧНО как в pgAdmin, "
                "3) для локальной базы DB_HOST=127.0.0.1 и DB_SSL=false. Ошибка: " + f"{exc}"
            ) from exc

        # Verify + report exactly which database we are really on.
        try:
            async with self.pool.acquire() as _vconn:
                _live_db = await _vconn.fetchval("SELECT current_database()")
                _live_users = await _vconn.fetchval("SELECT COUNT(*)::int FROM users")
            self.connected_user_count = int(_live_users or 0)
            _elapsed_ms = (time.perf_counter() - _t0) * 1000
            print(
                f"[DB][OK] connected to '{_live_db}' via {_via} | "
                f"users={self.connected_user_count} | "
                f"pool={pool_kwargs['min_size']}..{pool_kwargs['max_size']} | {_elapsed_ms:.0f} ms"
            )
        except Exception as _verify_err:
            print(f"[DB][WARN] pool created, verify skipped: {type(_verify_err).__name__}: {_verify_err}")

        # Быстрый путь для farm-ботов: API-сервер (шаг 5 start_all) уже прогрел
        # схему и миграции на той же БД. Повторять тяжёлую инициализацию не нужно.
        _light = os.getenv("CF_DB_LIGHT_CONNECT", "").strip().lower() in ("1", "true", "yes", "on")
        if _light:
            await dex_catalog.load(self.pool)
            from content_registry import load_content_registry

            try:
                await load_content_registry(self.pool)
                from content_registry import all_crops

                print(f"[DB][OK] lightweight connect | farm_crops={len(all_crops())} loaded from PostgreSQL")
            except Exception as _light_content_err:
                print(f"[DB][WARN] lightweight content registry: {_light_content_err}")
            _elapsed_ms = (time.perf_counter() - _t0) * 1000
            print(
                f"[DB][OK] lightweight connect | users={self.connected_user_count} | "
                f"pool={pool_kwargs['min_size']}..{pool_kwargs['max_size']} | {_elapsed_ms:.0f} ms "
                f"(migrations skipped — API already warmed DB)"
            )
            return

        schema = Path(__file__).parent / "schema.sql"
        _mig_logger = logging.getLogger("cute-farm")
        async with self.pool.acquire() as conn:
            # Сначала создаём/актуализируем схему (CREATE TABLE IF NOT EXISTS),
            # затем миграции-ALTER. На пустой базе (например, свежая managed-БД
            # на хостинге) обратный порядок падал: ALTER бил по ещё не созданной
            # таблице farm_plots.
            await conn.execute(schema.read_text(encoding="utf-8"))
            await conn.execute(
                """
                ALTER TABLE farm_plots
                ADD COLUMN IF NOT EXISTS autowater_active BOOLEAN NOT NULL DEFAULT FALSE
                """
            )

            # Heal schema drift on pre-existing DBs: "CREATE TABLE IF NOT EXISTS"
            # never adds a UNIQUE constraint to a table that already exists, so
            # older databases can miss the unique keys that ON CONFLICT relies on.
            # A UNIQUE INDEX satisfies ON CONFLICT inference and is idempotent.
            _unique_index_migrations = (
                ("craft_recipes_key_uidx", "craft_recipes", "key"),
                ("farm_crops_key_uidx", "farm_crops", "key"),
                ("quests_key_uidx", "quests", "key"),
                ("application_questions_qkey_uidx", "application_questions", "qkey"),
            )
            for _idx_name, _table, _column in _unique_index_migrations:
                try:
                    # Self-heal: старые БД могут содержать дубли по ключу (индекс
                    # не мог их запретить, пока его не было). Перед созданием
                    # UNIQUE-индекса удаляем дубли, оставляя строку с наименьшим
                    # id (самую раннюю/оригинальную). Детерминированно и
                    # идемпотентно: NULL-значения не трогаются (NULL <> NULL).
                    _dedup = await conn.execute(
                        f'DELETE FROM {_table} a '
                        f'USING {_table} b '
                        f'WHERE a."{_column}" = b."{_column}" AND a.id > b.id'
                    )
                    try:
                        _removed = int(_dedup.split()[-1])
                    except (ValueError, IndexError, AttributeError):
                        _removed = 0
                    if _removed:
                        _mig_logger.warning(
                            "deduplicated %s: removed %d duplicate row(s) on %s "
                            "(kept earliest id per value)",
                            _table, _removed, _column,
                        )
                    await conn.execute(
                        f'CREATE UNIQUE INDEX IF NOT EXISTS {_idx_name} '
                        f'ON {_table} ("{_column}")'
                    )
                except Exception as _mig_err:
                    _mig_logger.warning(
                        "unique index %s on %s(%s) skipped: %s",
                        _idx_name, _table, _column, _mig_err,
                    )

            # Singleton system_settings: legacy DBs may lack PRIMARY KEY on id,
            # which breaks INSERT ... ON CONFLICT (id) in maintenance toggle.
            try:
                await conn.execute(
                    "DELETE FROM system_settings a USING system_settings b "
                    "WHERE a.id = b.id AND a.ctid > b.ctid"
                )
                await conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS system_settings_id_uidx "
                    "ON system_settings (id)"
                )
            except Exception as _mig_err:
                _mig_logger.warning(
                    "system_settings id unique index skipped: %s", _mig_err
                )

        from system_settings import init_system_settings
        from economy_settings import init_economy_settings
        from farm_settings import init_farm_settings

        _logger = logging.getLogger("cute-farm")
        for _fn, _name in (
            (init_system_settings, "system_settings"),
            (init_economy_settings, "economy_settings"),
            (init_farm_settings, "farm_settings"),
        ):
            try:
                await _fn()
            except Exception as _e:
                _logger.warning("init %s skipped: %s", _name, _e)

        from admin_db import bootstrap_owner_accounts, seed_application_questions

        try:
            await bootstrap_owner_accounts()
        except Exception as _e:
            _logger.warning("bootstrap_owner_accounts skipped: %s", _e)
        try:
            await seed_application_questions()
        except Exception as _e:
            _logger.warning("seed_application_questions skipped: %s", _e)

        await dex_catalog.load(self.pool)

        from content_registry import load_content_registry, seed_default_content

        try:
            await seed_default_content(self.pool)
            await load_content_registry(self.pool)
            from content_registry import all_crops

            print(f"[DB][OK] content registry | farm_crops={len(all_crops())} from PostgreSQL")
        except Exception as _seed_err:
            _logger.warning("seed_default_content skipped: %s", _seed_err)

        from quest_registry import load_quest_registry, seed_default_quests, enabled_quests

        await seed_default_quests(self.pool)
        await load_quest_registry(self.pool)
        print(f"[DB][OK] quest registry | enabled_quests={len(enabled_quests())}")

        from craft_definitions import validate_craft_recipes

        for warning in validate_craft_recipes():
            print(warning)

        migrated = await migrate_all_users_items(self.pool)
        if migrated:
            print(f"Items: мигрировано записей users.items: {migrated}")

        await self._normalize_all_grow_timers()
        print("Пул соединений создан, schema применена.")
        print(f"Dex: {len(dex_catalog._by_id)} предметов в каталоге.")

    async def _normalize_all_grow_timers(self):
        """При старте: подогнать таймеры роста под время культуры (дерево 20 мин, табак 10 мин)."""
        current = now()
        fixed = 0
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, plot_id, status, planted_at, ripe_at, dry_at,
                       needs_water, wilt_at, waters_remaining, crop_id, autowater_active
                FROM farm_plots
                WHERE status = 'GROWING'
                """
            )
            for raw in rows:
                row = dict(raw)
                if not normalize_grow_row(row, current):
                    continue
                await self._save_plot(conn, row["user_id"], row)
                fixed += 1
        if fixed:
            print(f"Ферма: нормализовано таймеров роста: {fixed}")

    async def ensure_connected(self):
        """Idempotent pool init — safe to call from API, bots, or scripts."""
        await self.connect()

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def disconnect(self):
        """Alias for close() — used by migration scripts."""
        await self.close()

    async def get_user_balance(self, user_id):
        if not self.pool:
            raise RuntimeError("Пул не инициализирован")
        value = await self.pool.fetchval("SELECT balance FROM users WHERE user_id = $1", user_id)
        if value is None:
            return None
        return int(value)

    async def get_user_items(self, user_id):
        row = await self.pool.fetchval("SELECT items FROM users WHERE user_id = $1", user_id)
        return parse_items(row)

    async def _set_user_items(self, conn, user_id, items, raw_original=None):
        if raw_original is not None:
            items = merge_items_for_storage(raw_original, items)
        await conn.execute(
            "UPDATE users SET items = $2 WHERE user_id = $1", user_id, items_to_db(items)
        )

    async def _bump_quest_in_tx(self, conn, user_id, action, amount=1, *, item_ids=()):
        from quest_progress import bump_progress, parse_progress_store, progress_store_to_db

        raw = await conn.fetchval("SELECT quest_progress FROM users WHERE user_id = $1", user_id)
        store = bump_progress(parse_progress_store(raw), action, amount=amount, item_ids=item_ids)
        await conn.execute(
            "UPDATE users SET quest_progress = $2::jsonb WHERE user_id = $1",
            user_id,
            json.dumps(progress_store_to_db(store)),
        )

    async def get_owned_plot_count(self, conn, user_id):
        return int(
            await conn.fetchval("SELECT COUNT(*) FROM farm_plots WHERE user_id = $1", user_id) or 0
        )

    async def _ensure_farm_plots(self, conn, user_id, count):
        for plot_id in range(1, count + 1):
            await conn.execute(
                """
                INSERT INTO farm_plots (user_id, plot_id, status)
                VALUES ($1, $2, 'EMPTY')
                ON CONFLICT (user_id, plot_id) DO NOTHING
                """,
                user_id,
                plot_id,
            )

    async def ensure_user(self, user_id):
        """Новый игрок: users + 1 грядка (бесплатно) + стартовый набор."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                balance = await conn.fetchval(
                    "SELECT balance FROM users WHERE user_id = $1", user_id
                )
                if balance is None:
                    from economy_settings import get_default_balance

                    start_balance = get_default_balance()
                    await conn.execute(
                        """
                        INSERT INTO users (user_id, balance)
                        VALUES ($1, $2)
                        ON CONFLICT (user_id) DO NOTHING
                        """,
                        user_id,
                        start_balance,
                    )
                    balance = await conn.fetchval(
                        "SELECT balance FROM users WHERE user_id = $1", user_id
                    )
                    if balance is None:
                        raise ValueError("Не удалось создать профиль. Пожалуйста, попробуйте позже")
                    print(f"Новый игрок: user_id={user_id}, balance={start_balance}")
                    await self._ensure_farm_plots(conn, user_id, 1)
                    await self._try_grant_starter_pack(conn, user_id)
                balance = int(
                    await conn.fetchval("SELECT balance FROM users WHERE user_id = $1", user_id)
                    or 0
                )
        return balance

    async def _try_grant_starter_pack(self, conn, user_id):
        row = await conn.fetchrow(
            """
            SELECT starter_pack_granted, items
            FROM users WHERE user_id = $1 FOR UPDATE
            """,
            user_id,
        )
        if row and row["starter_pack_granted"]:
            return False
        from seed_economy import apply_starter_pack

        raw_items = parse_items(row["items"])
        game_items = apply_starter_pack(normalize_items(raw_items))
        stored = merge_items_for_storage(raw_items, game_items)
        await conn.execute(
            """
            UPDATE users
            SET items = $2, starter_pack_granted = TRUE
            WHERE user_id = $1
            """,
            user_id,
            items_to_db(stored),
        )
        return True

    async def _fetch_plots(self, conn, user_id):
        rows = await conn.fetch(
            """
            SELECT plot_id, status, planted_at, ripe_at, dry_at, needs_water, wilt_at,
                   waters_remaining, crop_id, autowater_active
            FROM farm_plots WHERE user_id = $1 ORDER BY plot_id
            """,
            user_id,
        )
        return [dict(r) for r in rows]

    async def _save_plot(self, conn, user_id, row):
        await conn.execute(
            """
            UPDATE farm_plots
            SET status = $3, planted_at = $4, ripe_at = $5, dry_at = $6,
                needs_water = $7, wilt_at = $8, waters_remaining = $9, crop_id = $10,
                autowater_active = $11
            WHERE user_id = $1 AND plot_id = $2
            """,
            user_id,
            row["plot_id"],
            row["status"],
            row.get("planted_at"),
            row.get("ripe_at"),
            row.get("dry_at"),
            row.get("needs_water", False),
            row.get("wilt_at"),
            int(row.get("waters_remaining") or 0),
            row.get("crop_id"),
            bool(row.get("autowater_active")),
        )

    async def _get_plot(self, conn, user_id, plot_id, *, for_update=False):
        query = """
            SELECT plot_id, status, planted_at, ripe_at, dry_at, needs_water, wilt_at,
                   waters_remaining, crop_id, autowater_active
            FROM farm_plots WHERE user_id = $1 AND plot_id = $2
            """
        if for_update:
            query += " FOR UPDATE"
        row = await conn.fetchrow(query, user_id, plot_id)
        if row:
            return dict(row)
        return None

    def _build_state_meta(self, owned, raw_items, tool_durability, kut=0):
        from farm_settings import (
            get_max_plots,
            get_tree_grow_seconds,
            get_water_interval_seconds,
        )

        normalized = normalize_items(raw_items)
        max_plots = get_max_plots()
        next_id = owned + 1 if owned < max_plots else None
        seed_counts = plantable_seed_counts(raw_items)
        farm_crops = crops_for_client(raw_items)
        return {
            "ownedPlots": owned,
            "maxPlots": max_plots,
            "nextPlotId": next_id,
            "nextPlotPrice": plot_buy_price(next_id) if next_id else None,
            "seedCount": seed_count(raw_items),
            "tobaccoSeedCount": tobacco_seed_count(raw_items),
            "seedCounts": seed_counts,
            "items": raw_items,
            "itemsDisplay": items_for_display(raw_items),
            "itemCatalog": dex_catalog.as_client_dict(),
            "farmItemIds": farm_item_ids_for_client(),
            "farmCrops": farm_crops,
            "balanceBar": balance_bar_for_client(
                kut=int(kut),
                seed_counts=seed_counts,
                raw_items=raw_items,
                farm_crops=farm_crops,
            ),
            "axe": axe_state_for_client(raw_items, tool_durability),
            "waterCount": water_count(normalized),
            "autowaterCount": autowater_count(normalized),
            "growSeconds": get_tree_grow_seconds(),
            "waterIntervalSeconds": get_water_interval_seconds(),
        }

    def _plot_persist_needed(self, before, after):
        keys = (
            "status",
            "planted_at",
            "ripe_at",
            "dry_at",
            "needs_water",
            "wilt_at",
            "waters_remaining",
            "crop_id",
            "autowater_active",
        )
        return any(before.get(key) != after.get(key) for key in keys)

    async def get_farm_state(self, user_id, *, persist_sync=True):
        """Return farm state. Set persist_sync=False for read-only polls (no DB writes)."""
        await self.ensure_user(user_id)
        current = now()
        async with self.pool.acquire() as conn:
            owned = await self.get_owned_plot_count(conn, user_id)
            plots = await self._fetch_plots(conn, user_id)
            synced = []
            for row in plots:
                before = dict(row)
                row = sync_growing_plot(row, current)
                if persist_sync and self._plot_persist_needed(before, row):
                    await self._save_plot(conn, user_id, row)
                synced.append(plot_to_json(row))
            user_row = await conn.fetchrow(
                """
                SELECT items, tool_durability, daily_seed_claimed_on, balance,
                       onboarding_done, onboarding_active, onboarding_seed_granted,
                       onboarding_demo_logs, onboarding_step
                FROM users WHERE user_id = $1
                """,
                user_id,
            )
        if user_row is None:
            raise RuntimeError(f"User {user_id} not found after ensure_user")
        items_raw_val = user_row["items"]
        items = parse_items(items_raw_val)
        normalized = normalize_items(items)
        tool_durability = parse_tool_durability(user_row["tool_durability"])
        daily_seed_claimed_on = user_row["daily_seed_claimed_on"]
        balance = int(user_row["balance"] or 0)
        onboarding = {
            "done": bool(user_row["onboarding_done"]),
            "active": bool(user_row["onboarding_active"]),
            "seedGranted": int(user_row["onboarding_seed_granted"] or 0),
            "demoLogs": int(user_row["onboarding_demo_logs"] or 0),
            "step": int(user_row["onboarding_step"] or 0),
        }
        meta = self._build_state_meta(owned, items, tool_durability, kut=balance)
        from seed_economy import seed_economy_for_client

        return {
            "kut": int(balance or 0),
            "inventory": {"justtree": log_count(normalized)},
            **meta,
            "plots": synced,
            "onboarding": onboarding,
            "seedEconomy": seed_economy_for_client(daily_seed_claimed_on=daily_seed_claimed_on),
        }

    async def get_inventory_state(self, user_id):
        from inventory_catalog import build_inventory_items, inventory_summary
        from item_market_stats import fetch_inventory_item_economy

        await self.ensure_user(user_id)
        async with self.pool.acquire() as conn:
            items_raw = await conn.fetchval("SELECT items FROM users WHERE user_id = $1", user_id)
            tool_durability_raw = await conn.fetchval(
                "SELECT tool_durability FROM users WHERE user_id = $1", user_id
            )
        items = parse_items(items_raw)
        tool_durability = parse_tool_durability(tool_durability_raw)
        axe = axe_state_for_client(items, tool_durability)
        axe_meta = ""
        if axe.get("owned") and axe.get("count", 0) > 0:
            axe_meta = f"{axe['count']} шт. · 1 за сбор"
        normalized = normalize_items(items)
        item_ids = [item_id for item_id, count in normalized.items() if int(count or 0) > 0]
        economy_by_id = await fetch_inventory_item_economy(self.pool, item_ids, user_id)
        inventory_items = build_inventory_items(
            items, axe_meta=axe_meta, economy_by_id=economy_by_id
        )
        balance = await self.get_user_balance(user_id)
        return {
            "kut": int(balance or 0),
            "items": inventory_items,
            "summary": inventory_summary(inventory_items),
            "axe": axe,
            "farmItemIds": farm_item_ids_for_client(),
            "itemCatalog": dex_catalog.as_client_dict(),
        }

    async def buy_plot(self, user_id):
        from farm_settings import get_max_plots

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                balance = await conn.fetchval(
                    "SELECT balance FROM users WHERE user_id = $1 FOR UPDATE", user_id
                )
                if balance is None:
                    raise ValueError("Профиль не найден")
                owned = await self.get_owned_plot_count(conn, user_id)
                if owned >= get_max_plots():
                    raise ValueError(f"У Вас уже максимум грядок ({get_max_plots()})")
                next_id = owned + 1
                price = plot_buy_price(next_id)
                if int(balance) < price:
                    raise ValueError(f"У Вас недостаточно кут (нужно {price})")
                await conn.execute(
                    "UPDATE users SET balance = balance - $2 WHERE user_id = $1", user_id, price
                )
                await conn.execute(
                    """
                    INSERT INTO farm_plots (user_id, plot_id, status)
                    VALUES ($1, $2, 'EMPTY')
                    """,
                    user_id,
                    next_id,
                )
        schedule_balance_event(
            self.pool,
            "plot_buy",
            user_id,
            amount=-price,
            balance_before=int(balance),
            balance_after=int(balance) - price,
            details={"plot_id": next_id, "price": price},
        )
        return await self.get_farm_state(user_id)

    async def plant_seed(self, user_id, plot_id, seed_item_id):
        from farm_settings import get_max_plots

        if plot_id < 1 or plot_id > get_max_plots():
            raise ValueError("Неверный номер грядки")
        seed_id = normalize_seed_id(seed_item_id)
        crop = get_crop_by_seed(seed_id)
        if not crop:
            raise ValueError("Этот саженец нельзя посадить")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                items_raw = await conn.fetchval(
                    "SELECT items FROM users WHERE user_id = $1 FOR UPDATE", user_id
                )
                raw_items = parse_items(items_raw)
                from user_items import count_seed_for_crop, take_seed_from_storage

                if count_seed_for_crop(raw_items, crop) < 1:
                    entry = dex_catalog.get(seed_id)
                    label = entry.name if entry else "саженца"
                    raise ValueError(f"У Вас нет {label}. Купите в магазине")
                row = await self._get_plot(conn, user_id, plot_id, for_update=True)
                if not row:
                    raise ValueError("Эта грядка ещё не куплена")
                if row["status"] != "EMPTY":
                    raise ValueError("Грядка уже занята")
                stored_items = take_seed_from_storage(raw_items, crop, 1)
                await self._set_user_items(conn, user_id, stored_items)
                row = apply_plant(row, now(), crop_id=crop.key)
                await self._save_plot(conn, user_id, row)
                await self._bump_quest_in_tx(conn, user_id, "plant", item_ids=(seed_id,))
        log_game_event(self.pool, "farm_plant", user_id, {"crop_id": seed_id, "plot_id": plot_id})
        from farm_notifications import attach_farm_notify, notify_item

        state = await self.get_farm_state(user_id)
        attach_farm_notify(state, spent=[notify_item(seed_id, 1)])
        return state

    async def water_plot(self, user_id, plot_id, water_item_id=None):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                items_raw = await conn.fetchval(
                    "SELECT items FROM users WHERE user_id = $1 FOR UPDATE", user_id
                )
                raw_items = parse_items(items_raw)
                row = await self._get_plot(conn, user_id, plot_id, for_update=True)
                if not row or row["status"] != "GROWING":
                    raise ValueError("На грядке ничего не растёт")
                current = now()
                row = sync_growing_plot(row, current)
                if row["status"] != "GROWING":
                    raise ValueError("Растение уже не растёт")
                if row.get("autowater_active"):
                    raise ValueError("На грядке работает автополив — ручной полив не нужен")
                if not is_dry(row, current):
                    raise ValueError("Сейчас полив не требуется")
                crop = get_crop_for_plot(row.get("crop_id"))
                resolved_item_id, water_cost = resolve_water_item_for_action(
                    raw_items, crop, water_item_id
                )
                from user_items import take_item_from_storage

                stored_items = take_item_from_storage(raw_items, resolved_item_id, water_cost)
                await self._set_user_items(conn, user_id, stored_items)
                row = apply_water(row, current)
                await self._save_plot(conn, user_id, row)
                await self._bump_quest_in_tx(conn, user_id, "water")
        log_game_event(
            self.pool, "farm_water", user_id, {"crop_id": row.get("crop_id"), "plot_id": plot_id}
        )
        from farm_notifications import attach_farm_notify, notify_item

        state = await self.get_farm_state(user_id)
        attach_farm_notify(state, spent=[notify_item(resolved_item_id, water_cost)])
        return state

    async def install_autowater(self, user_id, plot_id):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                items_raw = await conn.fetchval(
                    "SELECT items FROM users WHERE user_id = $1 FOR UPDATE", user_id
                )
                raw_items = parse_items(items_raw)
                row = await self._get_plot(conn, user_id, plot_id, for_update=True)
                if not row or row["status"] != "GROWING":
                    raise ValueError("На грядке ничего не растёт")
                current = now()
                row = sync_growing_plot(row, current)
                if row["status"] != "GROWING":
                    raise ValueError("Растение уже не растёт")
                if row.get("autowater_active"):
                    raise ValueError("Автополив уже установлен на этой грядке")
                if count_item(raw_items, AUTOWATER_ITEM_KEY) < 1:
                    entry = dex_catalog.get(AUTOWATER_ITEM_KEY)
                    label = entry.name if entry else "автополива"
                    raise ValueError(f"У Вас нет {label}. Скрафтите в разделе «Крафты»")
                stored_items = take_item_from_storage(raw_items, AUTOWATER_ITEM_KEY, 1)
                await self._set_user_items(conn, user_id, stored_items)
                row = apply_autowater(row, current)
                await self._save_plot(conn, user_id, row)
        from farm_notifications import attach_farm_notify, notify_item

        state = await self.get_farm_state(user_id)
        attach_farm_notify(state, spent=[notify_item(AUTOWATER_ITEM_KEY, 1)])
        return state

    async def harvest_plot(self, user_id, plot_id):
        gained_rows: list[dict] = []
        spent_rows: list[dict] = []
        harvest_meta = None
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_row = await conn.fetchrow(
                    "SELECT items, tool_durability FROM users WHERE user_id = $1 FOR UPDATE",
                    user_id,
                )
                if not user_row:
                    raise ValueError("Профиль не найден")
                raw_items = parse_items(user_row["items"])
                tool_durability = parse_tool_durability(user_row["tool_durability"])
                row = await self._get_plot(conn, user_id, plot_id, for_update=True)
                if not row:
                    raise ValueError("Грядка не найдена")
                row = sync_growing_plot(row, now())
                if row["status"] != "READY":
                    raise ValueError("Урожай ещё не готов")
                crop = get_crop_for_plot(row.get("crop_id"))
                if not crop:
                    raise ValueError("Неизвестная культура на грядке")
                amount = random.randint(crop.harvest_min, crop.harvest_max)
                game_items = normalize_items(raw_items)
                if crop.harvest_tool_item_id:
                    game_items, tool_durability, _tool_left = apply_harvest_tool(
                        raw_items,
                        tool_durability,
                        tool_item_id=crop.harvest_tool_item_id,
                        cost=crop.harvest_tool_cost,
                    )
                else:
                    _tool_left = None
                drops = roll_harvest_drops(crop)
                if not drops:
                    drops = [(crop.harvest_id, amount)] if crop.harvest_id else []
                total_harvest_amount = 0
                primary_harvest_id = crop.harvest_id
                for item_id, drop_amount in drops:
                    game_items = add_item(game_items, item_id, drop_amount)
                    if item_id == primary_harvest_id:
                        total_harvest_amount += drop_amount
                if total_harvest_amount == 0 and drops:
                    total_harvest_amount = drops[0][1]
                from seed_economy import roll_harvest_seed_drop, seed_drop_client_meta

                seed_dropped = roll_harvest_seed_drop(crop)
                if seed_dropped:
                    game_items = add_item(game_items, crop.seed_id, 1)
                harvest_meta = seed_drop_client_meta(crop, dropped=seed_dropped)
                from farm_notifications import notify_item

                gained_rows = []
                spent_rows = []
                for item_id, drop_amount in drops:
                    gained_rows.append(notify_item(item_id, drop_amount))
                if seed_dropped:
                    gained_rows.append(notify_item(crop.seed_id, 1))
                if crop.harvest_tool_item_id:
                    spent_rows.append(
                        notify_item(crop.harvest_tool_item_id, crop.harvest_tool_cost)
                    )
                stored = merge_items_for_storage(raw_items, game_items)
                row = apply_harvest(row)
                await self._save_plot(conn, user_id, row)
                await conn.execute(
                    """
                    UPDATE users
                    SET items = $2, tool_durability = $3::jsonb
                    WHERE user_id = $1
                    """,
                    user_id,
                    items_to_db(stored),
                    tool_durability_to_db(tool_durability),
                )
                flags = await self._fetch_onboarding_flags(conn, user_id)
                if (
                    flags["active"]
                    and plot_id == ONBOARDING_PLOT_ID
                    and crop.harvest_id == TREE_ITEM_KEY
                ):
                    await conn.execute(
                        """
                        UPDATE users
                        SET onboarding_demo_logs = onboarding_demo_logs + $2
                        WHERE user_id = $1
                        """,
                        user_id,
                        total_harvest_amount,
                    )
                if drops:
                    drop_item_ids = tuple(item_id for item_id, _ in drops)
                else:
                    drop_item_ids = ()
                if not drop_item_ids and crop.harvest_id:
                    drop_item_ids = (crop.harvest_id,)
                await self._bump_quest_in_tx(conn, user_id, "harvest", item_ids=drop_item_ids)
        log_game_event(
            self.pool,
            "farm_harvest",
            user_id,
            {"crop_id": crop.key if crop else None, "plot_id": plot_id},
        )
        from farm_notifications import attach_farm_notify

        state = await self.get_farm_state(user_id)
        if harvest_meta:
            state["harvestMeta"] = harvest_meta
        attach_farm_notify(state, gained=gained_rows, spent=spent_rows)
        return state

    async def clear_plot(self, user_id, plot_id):
        from economy_settings import get_clear_cost

        clear_cost = get_clear_cost()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                balance = await conn.fetchval(
                    "SELECT balance FROM users WHERE user_id = $1 FOR UPDATE", user_id
                )
                if balance is None:
                    raise ValueError("Профиль не найден")
                if int(balance) < clear_cost:
                    raise ValueError("У Вас недостаточно кут")
                row = await self._get_plot(conn, user_id, plot_id, for_update=True)
                if not row or row["status"] != "WITHERED":
                    raise ValueError("Растение на грядке ещё не засохло")
                withered_crop_id = row.get("crop_id")
                row = apply_harvest(row)
                await conn.execute(
                    "UPDATE users SET balance = balance - $2 WHERE user_id = $1",
                    user_id,
                    clear_cost,
                )
                await self._save_plot(conn, user_id, row)
        log_game_event(
            self.pool,
            "farm_wither",
            user_id,
            {"crop_id": withered_crop_id, "plot_id": plot_id},
        )
        schedule_balance_event(
            self.pool,
            "plot_clear",
            user_id,
            amount=-clear_cost,
            balance_before=int(balance),
            balance_after=int(balance) - clear_cost,
            details={"plot_id": plot_id, "cost": clear_cost},
        )
        return await self.get_farm_state(user_id)

    async def _player_snapshot(self, user_id):
        items_raw = await self.get_user_items(user_id)
        balance = await self.get_user_balance(user_id)
        normalized = normalize_items(items_raw)
        return {
            "kut": int(balance or 0),
            "items": items_raw,
            "itemsDisplay": items_for_display(items_raw),
            "seedCount": seed_count(normalized),
        }

    async def get_shop_catalog(
        self,
        user_id,
        category_id=None,
        page=0,
        search="",
        price_filter="all",
        sort_by="name",
        sort_order="asc",
        page_size=None,
    ):
        from math import ceil
        from shop_catalog import (
            ALL_CATEGORY_ID,
            build_order_clause,
            build_price_filter_clause,
            build_sort_filters,
            category_from_sorting,
            item_to_client,
            normalize_page_size,
            normalize_price_filter,
            normalize_search_query,
            normalize_sort_by,
            normalize_sort_order,
            sorting_for_category_id,
        )

        await self.ensure_user(user_id)
        category_id = category_id or ALL_CATEGORY_ID.strip() or ALL_CATEGORY_ID
        page = max(0, int(page))
        page_size = normalize_page_size(page_size)
        search_q = normalize_search_query(search)
        price_filter = normalize_price_filter(price_filter)
        sort_by = normalize_sort_by(sort_by)
        sort_order = normalize_sort_order(sort_order)
        cached = self._shop_catalog_cache.get(
            category_id, page, search_q, price_filter, sort_by, sort_order, page_size
        )
        if cached is not None:
            balance = await self.get_user_balance(user_id)
            return {**cached, "kut": int(balance or 0)}
        async with self.pool.acquire() as conn:
            category_rows = await conn.fetch(
                """
                SELECT sorting, COUNT(*)::int AS cnt
                FROM dex
                WHERE remains > 0
                GROUP BY sorting
                ORDER BY cnt DESC, sorting NULLS LAST
                """
            )
            categories = [
                {
                    "id": ALL_CATEGORY_ID,
                    "label": "Все",
                    "emoji": "🛍",
                    "sorting": None,
                    "count": sum(row["cnt"] for row in category_rows),
                }
            ]
            for row in category_rows:
                categories.append(category_from_sorting(row["sorting"], row["cnt"]))
            counts_by_sorting = {row["sorting"]: row["cnt"] for row in category_rows}
            sort_filters = build_sort_filters(counts_by_sorting)
            sorting_filter = sorting_for_category_id(category_id)
            params = []
            where = ["remains > 0"]
            if sorting_filter is not None:
                if sorting_filter == "__null__":
                    where.append("sorting IS NULL")
                else:
                    params.append(sorting_filter)
                    where.append(f"sorting = ${len(params)}")
            if search_q:
                params.append(f"%{search_q}%")
                idx = len(params)
                where.append(
                    f"(name ILIKE ${idx} OR name1 ILIKE ${idx} OR CAST(id AS TEXT) ILIKE ${idx})"
                )
            price_clause = build_price_filter_clause(price_filter)
            if price_clause:
                where.append(price_clause)
            where_sql = " AND ".join(where)
            total = await conn.fetchval(
                f"SELECT COUNT(*)::int FROM dex WHERE {where_sql}", *params
            )
            total_pages = max(1, ceil(total / page_size)) if total else 0
            if total == 0:
                page = 0
            else:
                page = min(page, total_pages - 1)
            offset = page * page_size
            limit_idx = len(params) + 1
            offset_idx = len(params) + 2
            order_sql = build_order_clause(sort_by, sort_order)
            rows = await conn.fetch(
                f"""
                SELECT id, name, name1, emoji, price, dis, remains, sorting,
                       stick, use, bonus, craft, bio
                FROM dex
                WHERE {where_sql}
                ORDER BY {order_sql}
                LIMIT ${limit_idx} OFFSET ${offset_idx}
                """,
                *params,
                page_size,
                offset,
            )
        balance = await self.get_user_balance(user_id)
        items = [item_to_client(dict(row)) for row in rows]
        result = {
            "kut": int(balance or 0),
            "categories": categories,
            "sortFilters": sort_filters,
            "activeCategory": category_id,
            "search": search_q,
            "priceFilter": price_filter,
            "sortBy": sort_by,
            "sortOrder": sort_order,
            "page": page,
            "pageSize": page_size,
            "columns": page_size // 4,
            "totalItems": total,
            "totalPages": total_pages,
            "items": items,
        }
        self._shop_catalog_cache.set(
            category_id, page, search_q, price_filter, sort_by, sort_order, page_size, result
        )
        return result

    async def buy_shop_item(
        self,
        user_id,
        item_id,
        category_id=None,
        page=0,
        search="",
        quantity=1,
        price_filter="all",
        sort_by="name",
        sort_order="asc",
        page_size=None,
    ):
        from shop_catalog import effective_price

        await self.ensure_user(user_id)
        item_id = str(item_id).strip()
        if not item_id or not item_id.isdigit():
            raise ValueError("Неверный предмет")
        quantity = max(1, min(int(quantity), 99))
        dex_id = int(item_id)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                dex_row = await conn.fetchrow(
                    """
                    SELECT id, name, emoji, price, dis, remains
                    FROM dex WHERE id = $1 FOR UPDATE
                    """,
                    dex_id,
                )
                if not dex_row:
                    raise ValueError("Предмет не найден")
                remains = int(dex_row["remains"] or 0)
                if remains < 1:
                    raise ValueError("К сожалению, товар закончился")
                buy_qty = min(quantity, remains)
                unit_cost = effective_price(dex_row["price"], dex_row["dis"])
                if unit_cost < 0:
                    raise ValueError("Этот предмет нельзя купить")
                cost = unit_cost * buy_qty
                balance = await conn.fetchval(
                    "SELECT balance FROM users WHERE user_id = $1 FOR UPDATE", user_id
                )
                if balance is None:
                    raise ValueError("Профиль не найден")
                if int(balance) < cost:
                    raise ValueError(f"У Вас недостаточно кут (нужно {cost})")
                items_raw = await conn.fetchval(
                    "SELECT items FROM users WHERE user_id = $1", user_id
                )
                tool_durability_raw = await conn.fetchval(
                    "SELECT tool_durability FROM users WHERE user_id = $1", user_id
                )
                raw_items = parse_items(items_raw)
                stored = add_shop_item_to_storage(raw_items, str(dex_row["id"]), buy_qty)
                tool_durability = parse_tool_durability(tool_durability_raw)
                await conn.execute(
                    """
                    UPDATE users
                    SET balance = balance - $2,
                        items = $3,
                        tool_durability = $4::jsonb
                    WHERE user_id = $1
                    """,
                    user_id,
                    cost,
                    items_to_db(stored),
                    tool_durability_to_db(tool_durability),
                )
                await conn.execute(
                    "UPDATE dex SET remains = remains - $2 WHERE id = $1", dex_id, buy_qty
                )
                purchased = {
                    "id": str(dex_row["id"]),
                    "name": (dex_row["name"] or "").strip() or str(dex_row["id"]),
                    "emoji": (dex_row["emoji"] or "").strip() or "📦",
                    "paid": cost,
                    "quantity": buy_qty,
                }
                audit_payload = {
                    "amount": -cost,
                    "balance_before": int(balance),
                    "balance_after": int(balance) - cost,
                    "details": {
                        "item_id": str(dex_row["id"]),
                        "name": purchased["name"],
                        "emoji": purchased["emoji"],
                        "quantity": buy_qty,
                        "paid": cost,
                        "remains_after": remains - buy_qty,
                    },
                }
        schedule_balance_event(self.pool, "shop_buy", user_id, **audit_payload)
        self._shop_catalog_cache.clear()
        catalog = await self.get_shop_catalog(
            user_id,
            category_id,
            page,
            search=search,
            price_filter=price_filter,
            sort_by=sort_by,
            sort_order=sort_order,
            page_size=page_size,
        )
        catalog["purchased"] = purchased
        catalog["player"] = await self._player_snapshot(user_id)
        return catalog

    async def _fetch_onboarding_flags(self, conn, user_id):
        row = await conn.fetchrow(
            """
            SELECT onboarding_done, onboarding_active, onboarding_seed_granted,
                   onboarding_demo_logs, onboarding_step
            FROM users WHERE user_id = $1
            """,
            user_id,
        )
        if not row:
            return {"done": False, "active": False, "step": 0}
        return {
            "done": bool(row["onboarding_done"]),
            "active": bool(row["onboarding_active"]),
            "seedGranted": int(row["onboarding_seed_granted"] or 0),
            "demoLogs": int(row["onboarding_demo_logs"] or 0),
            "step": int(row["onboarding_step"] or 0),
        }

    async def start_onboarding(self, user_id):
        await self.ensure_user(user_id)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                flags = await self._fetch_onboarding_flags(conn, user_id)
                if flags["done"]:
                    return await self.get_farm_state(user_id)
                await conn.execute(
                    "UPDATE users SET onboarding_active = TRUE WHERE user_id = $1", user_id
                )
                plot = await self._get_plot(conn, user_id, ONBOARDING_PLOT_ID)
                if plot and plot["status"] == "WITHERED":
                    plot = apply_harvest(plot)
                    await self._save_plot(conn, user_id, plot)
                items_raw = await conn.fetchval(
                    "SELECT items FROM users WHERE user_id = $1 FOR UPDATE", user_id
                )
                raw_items = parse_items(items_raw)
                game_items = normalize_items(raw_items)
                plot = await self._get_plot(conn, user_id, ONBOARDING_PLOT_ID)
                if plot and plot["status"] == "EMPTY":
                    game_items, granted = ensure_onboarding_demo_seeds(game_items)
                    if granted:
                        await self._set_user_items(
                            conn, user_id, game_items, raw_original=raw_items
                        )
                        await conn.execute(
                            """
                            UPDATE users
                            SET onboarding_seed_granted = GREATEST(onboarding_seed_granted, 1)
                            WHERE user_id = $1
                            """,
                            user_id,
                        )
                plot = await self._get_plot(conn, user_id, ONBOARDING_PLOT_ID)
                step = reconcile_onboarding_step(flags.get("step") or 0, plot)
                await conn.execute(
                    "UPDATE users SET onboarding_step = $2 WHERE user_id = $1", user_id, step
                )
        return await self.get_farm_state(user_id)

    def _reset_onboarding_plot(self, row):
        return apply_harvest(row)

    async def prepare_onboarding_step(self, user_id, step):
        if step not in ("plant", "water", "harvest"):
            raise ValueError("Неверный шаг обучения")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                flags = await self._fetch_onboarding_flags(conn, user_id)
                if not flags["active"]:
                    raise ValueError("Обучение не активно")
                row = await self._get_plot(conn, user_id, ONBOARDING_PLOT_ID)
                if not row:
                    raise ValueError("Грядка для обучения не найдена")
                current = now()
                if step == "plant":
                    row = self._reset_onboarding_plot(row)
                    await self._save_plot(conn, user_id, row)
                    items_raw = await conn.fetchval(
                        "SELECT items FROM users WHERE user_id = $1 FOR UPDATE", user_id
                    )
                    raw_items = parse_items(items_raw)
                    game_items = normalize_items(raw_items)
                    game_items, granted = ensure_onboarding_demo_seeds(game_items)
                    if granted:
                        await self._set_user_items(
                            conn, user_id, game_items, raw_original=raw_items
                        )
                        await conn.execute(
                            """
                            UPDATE users
                            SET onboarding_seed_granted = GREATEST(onboarding_seed_granted, 1)
                            WHERE user_id = $1
                            """,
                            user_id,
                        )
                elif step == "water":
                    if row["status"] != "GROWING":
                        raise ValueError("Сначала посадите семечко")
                    row["needs_water"] = True
                    row["dry_at"] = current - timedelta(seconds=1)
                    from farm_settings import get_wilt_grace_seconds

                    row["wilt_at"] = current + timedelta(seconds=get_wilt_grace_seconds())
                    row["waters_remaining"] = max(int(row.get("waters_remaining") or 0), 1)
                    await self._save_plot(conn, user_id, row)
                    items_raw = await conn.fetchval(
                        "SELECT items FROM users WHERE user_id = $1 FOR UPDATE", user_id
                    )
                    raw_items = parse_items(items_raw)
                    if count_item(raw_items, WATER_ITEM_KEY) < 1:
                        game_items = add_item(normalize_items(raw_items), WATER_ITEM_KEY, 1)
                        await self._set_user_items(
                            conn, user_id, game_items, raw_original=raw_items
                        )
                else:
                    if row["status"] not in ("GROWING", "READY"):
                        raise ValueError("Сначала посадите и полейте")
                    row["ripe_at"] = current - timedelta(seconds=1)
                    row["needs_water"] = False
                    row["wilt_at"] = None
                    row["dry_at"] = None
                    row = sync_growing_plot(row, current)
                    if row["status"] != "READY":
                        row["status"] = "READY"
                    await self._save_plot(conn, user_id, row)
                    user_row = await conn.fetchrow(
                        "SELECT items FROM users WHERE user_id = $1 FOR UPDATE", user_id
                    )
                    raw_items = parse_items(user_row["items"])
                    if count_item(raw_items, AXE_ITEM_KEY) < 1:
                        game_items = add_item(normalize_items(raw_items), AXE_ITEM_KEY, 1)
                        await self._set_user_items(
                            conn, user_id, game_items, raw_original=raw_items
                        )
                await conn.execute(
                    """
                    UPDATE users SET onboarding_step = $2 WHERE user_id = $1
                    """,
                    user_id,
                    ONBOARDING_PREPARE_STEP_INDEX[step],
                )
        return await self.get_farm_state(user_id)

    async def save_onboarding_step(self, user_id, step):
        step = max(0, min(int(step), 8))
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                flags = await self._fetch_onboarding_flags(conn, user_id)
                if flags["done"]:
                    return await self.get_farm_state(user_id)
                if not flags["active"]:
                    raise ValueError("Обучение не активно")
                plot = await self._get_plot(conn, user_id, ONBOARDING_PLOT_ID)
                step = reconcile_onboarding_step(step, plot)
                await conn.execute(
                    "UPDATE users SET onboarding_step = $2 WHERE user_id = $1", user_id, step
                )
        return await self.get_farm_state(user_id)

    async def complete_onboarding(self, user_id, *, skipped=False):
        await self.ensure_user(user_id)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                flags = await self._fetch_onboarding_flags(conn, user_id)
                if flags["done"]:
                    return await self.get_farm_state(user_id)
                demo_logs = int(flags.get("demoLogs") or 0)
                if demo_logs > 0:
                    items_raw = await conn.fetchval(
                        "SELECT items FROM users WHERE user_id = $1 FOR UPDATE", user_id
                    )
                    raw_items = parse_items(items_raw)
                    game_items = normalize_items(raw_items)
                    current_logs = log_count(game_items)
                    remove = min(demo_logs, current_logs)
                    if remove > 0:
                        game_items = take_item(game_items, (TREE_ITEM_KEY, "justtree"), remove)
                        await self._set_user_items(
                            conn, user_id, game_items, raw_original=raw_items
                        )
                await conn.execute(
                    """
                    UPDATE users
                    SET onboarding_done = TRUE,
                        onboarding_active = FALSE,
                        onboarding_seed_granted = 0,
                        onboarding_demo_logs = 0,
                        onboarding_step = 0
                    WHERE user_id = $1
                    """,
                    user_id,
                )
        return await self.get_farm_state(user_id)

    async def claim_daily_seed(self, user_id, *, seed_item_id=None):
        from seed_economy import (
            daily_seed_reward_label,
            get_daily_seed_amount,
            local_today,
            normalize_daily_seed_choice,
        )

        DAILY_SEED_AMOUNT = get_daily_seed_amount()
        await self.ensure_user(user_id)
        today = local_today()
        chosen_seed = normalize_daily_seed_choice(seed_item_id)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT daily_seed_claimed_on, items
                    FROM users WHERE user_id = $1 FOR UPDATE
                    """,
                    user_id,
                )
                if not row:
                    raise ValueError("Профиль не найден")
                claimed_on = row["daily_seed_claimed_on"]
                if claimed_on == today:
                    raise ValueError("Сегодня вы уже получили бесплатное семя. Загляните завтра")
                raw_items = parse_items(row["items"])
                game_items = add_item(normalize_items(raw_items), chosen_seed, DAILY_SEED_AMOUNT)
                stored = merge_items_for_storage(raw_items, game_items)
                await conn.execute(
                    """
                    UPDATE users
                    SET items = $2, daily_seed_claimed_on = $3
                    WHERE user_id = $1
                    """,
                    user_id,
                    items_to_db(stored),
                    today,
                )
        state = await self.get_farm_state(user_id)
        state["dailySeedReward"] = {
            "seedItemId": chosen_seed,
            "amount": DAILY_SEED_AMOUNT,
            "label": daily_seed_reward_label(chosen_seed),
        }
        return state

    async def get_quests_state(self, user_id):
        from quest_progress import build_quests_state
        from seed_economy import seed_economy_for_client

        await self.ensure_user(user_id)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT quest_progress, daily_seed_claimed_on, items
                FROM users WHERE user_id = $1
                """,
                user_id,
            )
        balance = await self.get_user_balance(user_id)
        payload = build_quests_state(
            row["quest_progress"] if row else {},
            daily_seed_claimed_on=row["daily_seed_claimed_on"] if row else None,
        )
        payload["kut"] = int(balance or 0)
        payload["seedEconomy"] = seed_economy_for_client(
            daily_seed_claimed_on=row["daily_seed_claimed_on"] if row else None
        )
        payload["farmCrops"] = crops_for_client(parse_items(row["items"]) if row else {})
        try:
            from quest_registry import enabled_quests as _enabled_quests
            _sec = payload.get("sections") or {}
            print(
                f"[QUESTS][DEBUG] user_id={user_id} registry_enabled={len(_enabled_quests())} "
                f"sections=" + ",".join(f"{k}:{len(v)}" for k, v in _sec.items())
            )
        except Exception as _dbg_e:
            print(f"[QUESTS][DEBUG][WARN] {_dbg_e}")
        return payload

    async def accept_quest(self, user_id, quest_id):
        from quest_progress import (
            accept_quest as accept_quest_in_store,
            parse_progress_store,
            progress_store_to_db,
        )
        from quest_registry import quest_by_key

        await self.ensure_user(user_id)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                raw = await conn.fetchval(
                    "SELECT quest_progress FROM users WHERE user_id = $1 FOR UPDATE", user_id
                )
                store = accept_quest_in_store(parse_progress_store(raw), quest_id)
                await conn.execute(
                    "UPDATE users SET quest_progress = $2::jsonb WHERE user_id = $1",
                    user_id,
                    json.dumps(progress_store_to_db(store)),
                )
        quest = quest_by_key(quest_id)
        log_game_event(
            self.pool,
            "quest_accept",
            user_id,
            {"quest_id": quest_id, "period": quest.period if quest else None},
        )
        return await self.get_quests_state(user_id)

    async def cancel_quest(self, user_id, quest_id):
        from quest_progress import (
            cancel_quest as cancel_quest_in_store,
            parse_progress_store,
            progress_store_to_db,
        )

        await self.ensure_user(user_id)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                raw = await conn.fetchval(
                    "SELECT quest_progress FROM users WHERE user_id = $1 FOR UPDATE", user_id
                )
                store = cancel_quest_in_store(parse_progress_store(raw), quest_id)
                await conn.execute(
                    "UPDATE users SET quest_progress = $2::jsonb WHERE user_id = $1",
                    user_id,
                    json.dumps(progress_store_to_db(store)),
                )
        return await self.get_quests_state(user_id)

    async def claim_quest_reward(self, user_id, quest_id):
        from quest_progress import (
            apply_quest_rewards,
            mark_quest_claimed,
            normalize_progress_store,
            parse_progress_store,
            progress_store_to_db,
            reward_summary,
        )
        from quest_registry import quest_by_key

        quest = quest_by_key(str(quest_id).strip())
        if not quest:
            raise ValueError("Задание не найдено")
        if quest.action == "claim_daily_seed":
            raise ValueError("Семя забирают кнопкой в карточке задания")
        await self.ensure_user(user_id)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT quest_progress, items, balance
                    FROM users WHERE user_id = $1 FOR UPDATE
                    """,
                    user_id,
                )
                if not row:
                    raise ValueError("Профиль не найден")
                store = normalize_progress_store(parse_progress_store(row["quest_progress"]))
                bucket = store[quest.period]
                if bucket.get("acceptedQuestId") != quest.id:
                    raise ValueError("Сначала возьми это задание")
                progress = int(bucket["progress"].get(quest.id, 0) or 0)
                if progress < quest.target:
                    raise ValueError("Задание ещё не выполнено")
                if quest.id in bucket["claimed"]:
                    raise ValueError("Награда уже получена")
                store = mark_quest_claimed(store, quest.id)
                raw_items = parse_items(row["items"])
                stored, kut_reward = apply_quest_rewards(raw_items, quest)
                balance_before = int(row["balance"] or 0)
                balance_after = balance_before + kut_reward
                await conn.execute(
                    """
                    UPDATE users
                    SET items = $2,
                        quest_progress = $3::jsonb,
                        balance = $4
                    WHERE user_id = $1
                    """,
                    user_id,
                    items_to_db(stored),
                    json.dumps(progress_store_to_db(store)),
                    balance_after,
                )
                if kut_reward:
                    schedule_balance_event(
                        self.pool,
                        "quest_reward",
                        user_id,
                        amount=kut_reward,
                        balance_before=balance_before,
                        balance_after=balance_after,
                        details={"quest_id": quest.id, "title": quest.title},
                    )
                log_game_event(
                    self.pool,
                    "quest_complete",
                    user_id,
                    {"quest_id": quest.id, "period": quest.period},
                )
        state = await self.get_quests_state(user_id)
        state["questReward"] = {
            "questId": quest.id,
            "title": quest.title,
            "rewards": reward_summary(quest),
        }
        return state

    async def get_craft_recipes(self, user_id):
        from craft_catalog import recipes_for_client

        await self.ensure_user(user_id)
        items_raw = await self.get_user_items(user_id)
        balance = await self.get_user_balance(user_id)
        return {
            "kut": int(balance or 0),
            "recipes": recipes_for_client(items_raw),
            "player": await self._player_snapshot(user_id),
        }

    async def execute_craft(self, user_id, slot_a, slot_b):
        from craft_catalog import normalize_success_percent, recipe_for_execute

        await self.ensure_user(user_id)
        slot_a = str(slot_a).strip()
        slot_b = str(slot_b).strip()
        if not slot_a or not slot_b:
            raise ValueError("Укажи оба предмета для крафта")
        recipe = recipe_for_execute(slot_a, slot_b)
        if not recipe:
            raise ValueError("Такой рецепт не существует. Эта пара ничего не создаёт")
        ingredients = recipe.ingredients()
        if not ingredients:
            raise ValueError("У рецепта нет ингредиентов")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                items_raw = await conn.fetchval(
                    "SELECT items FROM users WHERE user_id = $1 FOR UPDATE", user_id
                )
                raw_items = parse_items(items_raw)
                if not can_craft(raw_items, ingredients):
                    raise ValueError("Недостаточно предметов для крафта")
                success_percent = normalize_success_percent(recipe.success_percent)
                rolled_success = secrets.randbelow(100) < success_percent
                stored = take_craft_ingredients(raw_items, ingredients)
                result_id = str(recipe.result_id)
                if rolled_success:
                    stored = add_shop_item_to_storage(stored, result_id, 1)
                await conn.execute(
                    "UPDATE users SET items = $2 WHERE user_id = $1", user_id, items_to_db(stored)
                )
                if rolled_success:
                    await self._bump_quest_in_tx(
                        conn, user_id, "craft", item_ids=(result_id,)
                    )
                result_entry = dex_catalog.get(result_id)
                result_name = result_entry.name if result_entry else result_id
                result_emoji = result_entry.emoji if result_entry else "📦"
        event_type = "craft_success" if rolled_success else "craft_fail"
        schedule_balance_event(
            self.pool,
            event_type,
            user_id,
            details={
                "recipe_id": recipe.id,
                "recipe_key": recipe.key,
                "result_id": result_id,
                "result_name": result_name,
                "result_emoji": result_emoji,
                "success_percent": success_percent,
                "rolled_success": rolled_success,
                "ingredients": ingredients,
            },
        )
        catalog = await self.get_craft_recipes(user_id)
        if rolled_success:
            catalog["message"] = f"Успех! Получено: {result_emoji} {result_name}"
        else:
            catalog["message"] = "Не повезло: крафт не удался, материалы израсходованы"
        catalog["craftSuccess"] = rolled_success
        return catalog

    async def get_market_catalog(
        self,
        user_id,
        category_id=None,
        page=0,
        search="",
        price_filter="all",
        sort_by="name",
        sort_order="asc",
        page_size=None,
    ):
        from math import ceil
        from market_catalog import (
            ALL_CATEGORY_ID,
            build_market_order_clause,
            build_market_price_filter_clause,
            build_sort_filters,
            category_from_sorting,
            listing_to_client,
            normalize_page_size,
            normalize_price_filter,
            normalize_search_query,
            normalize_sort_by,
            normalize_sort_order,
            sorting_for_category_id,
        )

        await self.ensure_user(user_id)
        category_id = category_id or ALL_CATEGORY_ID.strip() or ALL_CATEGORY_ID
        page = max(0, int(page))
        page_size = normalize_page_size(page_size)
        search_q = normalize_search_query(search)
        price_filter = normalize_price_filter(price_filter)
        sort_by = normalize_sort_by(sort_by)
        sort_order = normalize_sort_order(sort_order)
        async with self.pool.acquire() as conn:
            category_rows = await conn.fetch(
                """
                SELECT d.sorting, COUNT(*)::int AS cnt
                FROM market_listings l
                JOIN dex d ON CAST(d.id AS TEXT) = l.item_id
                WHERE l.status = 'active' AND l.quantity > 0
                GROUP BY d.sorting
                ORDER BY cnt DESC, d.sorting NULLS LAST
                """
            )
            categories = [
                {
                    "id": ALL_CATEGORY_ID,
                    "label": "Все",
                    "emoji": "🛍",
                    "sorting": None,
                    "count": sum(row["cnt"] for row in category_rows),
                }
            ]
            for row in category_rows:
                categories.append(category_from_sorting(row["sorting"], row["cnt"]))
            counts_by_sorting = {row["sorting"]: row["cnt"] for row in category_rows}
            sort_filters = build_sort_filters(counts_by_sorting)
            sorting_filter = sorting_for_category_id(category_id)
            params = []
            where = ["l.status = 'active'", "l.quantity > 0"]
            if sorting_filter is not None:
                if sorting_filter == "__null__":
                    where.append("d.sorting IS NULL")
                else:
                    params.append(sorting_filter)
                    where.append(f"d.sorting = ${len(params)}")
            if search_q:
                params.append(f"%{search_q}%")
                idx = len(params)
                where.append(
                    f"(d.name ILIKE ${idx} OR d.name1 ILIKE ${idx} OR CAST(d.id AS TEXT) ILIKE ${idx} OR l.item_id ILIKE ${idx})"
                )
            price_clause = build_market_price_filter_clause(price_filter)
            if price_clause:
                where.append(price_clause)
            where_sql = " AND ".join(where)
            total = await conn.fetchval(
                f"""
                SELECT COUNT(*)::int
                FROM market_listings l
                JOIN dex d ON CAST(d.id AS TEXT) = l.item_id
                WHERE {where_sql}
                """,
                *params,
            )
            total_pages = max(1, ceil(total / page_size)) if total else 0
            if total == 0:
                page = 0
            else:
                page = min(page, total_pages - 1)
            offset = page * page_size
            limit_idx = len(params) + 1
            offset_idx = len(params) + 2
            order_sql = build_market_order_clause(sort_by, sort_order)
            rows = await conn.fetch(
                f"""
                SELECT l.id AS listing_id, l.seller_id, l.item_id, l.quantity, l.price,
                       l.created_at,
                       d.name, d.name1, d.emoji, d.sorting, d.stick, d.use, d.bonus,
                       d.craft, d.bio,
                       u.username AS seller_username,
                       u.first_name AS seller_first_name,
                       u.last_name AS seller_last_name,
                       u.display_name AS seller_display_name,
                       u.photo_url AS seller_photo_url
                FROM market_listings l
                JOIN dex d ON CAST(d.id AS TEXT) = l.item_id
                LEFT JOIN users u ON u.user_id = l.seller_id
                WHERE {where_sql}
                ORDER BY {order_sql}
                LIMIT ${limit_idx} OFFSET ${offset_idx}
                """,
                *params,
                page_size,
                offset,
            )
        balance = await self.get_user_balance(user_id)
        items = [listing_to_client(dict(row), viewer_id=user_id) for row in rows]
        from market_rules import market_commission_meta

        return {
            "kut": int(balance or 0),
            **market_commission_meta(),
            "categories": categories,
            "sortFilters": sort_filters,
            "activeCategory": category_id,
            "search": search_q,
            "priceFilter": price_filter,
            "sortBy": sort_by,
            "sortOrder": sort_order,
            "page": page,
            "pageSize": page_size,
            "columns": page_size // 4,
            "totalItems": total,
            "totalPages": total_pages,
            "items": items,
        }

    async def get_market_sellable(self, user_id):
        from market_catalog import sellable_item_to_client
        from market_rules import is_market_listable, normalize_market_item_id
        from user_items import count_item_in_storage

        await self.ensure_user(user_id)
        async with self.pool.acquire() as conn:
            items_raw = await conn.fetchval("SELECT items FROM users WHERE user_id = $1", user_id)
        raw_items = parse_items(items_raw)
        normalized = normalize_items(raw_items)
        sellable = []
        seen = set()
        for item_id in normalized:
            canon = normalize_market_item_id(item_id)
            if not canon or canon in seen:
                continue
            seen.add(canon)
            qty = count_item_in_storage(raw_items, canon)
            if qty < 1 or not is_market_listable(canon):
                continue
            entry = dex_catalog.get(canon)
            if not entry:
                continue
            sellable.append(sellable_item_to_client(entry, count=qty))
        sellable.sort(key=lambda row: row["name"].lower())
        balance = await self.get_user_balance(user_id)
        from market_rules import market_commission_meta

        return {
            "kut": int(balance or 0),
            "items": sellable,
            **market_commission_meta(),
        }

    async def create_market_listing(
        self,
        user_id,
        item_id,
        quantity,
        price,
        *,
        category_id=None,
        page=0,
        search="",
        price_filter="all",
        sort_by="name",
        sort_order="asc",
        page_size=None,
    ):
        from market_rules import (
            MARKET_MAX_LIST_QUANTITY,
            MARKET_MAX_PRICE,
            MARKET_MIN_PRICE,
            is_market_listable,
            normalize_market_item_id,
        )

        await self.ensure_user(user_id)
        item_key = normalize_market_item_id(item_id)
        if not item_key or not is_market_listable(item_key):
            raise ValueError("Этот предмет нельзя выставить на биржу")
        quantity = max(1, min(int(quantity), MARKET_MAX_LIST_QUANTITY))
        price = int(price)
        if price < MARKET_MIN_PRICE or price > MARKET_MAX_PRICE:
            raise ValueError(f"Цена должна быть от {MARKET_MIN_PRICE} до {MARKET_MAX_PRICE} КУТ")
        entry = dex_catalog.get(item_key)
        if not entry:
            raise ValueError("Предмет не найден")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                items_raw = await conn.fetchval(
                    "SELECT items FROM users WHERE user_id = $1 FOR UPDATE", user_id
                )
                raw_items = parse_items(items_raw)
                stored = take_item_from_storage(raw_items, item_key, quantity)
                await conn.execute(
                    "UPDATE users SET items = $2 WHERE user_id = $1", user_id, items_to_db(stored)
                )
                await conn.execute(
                    """
                    INSERT INTO market_listings (seller_id, item_id, quantity, price, status)
                    VALUES ($1, $2, $3, $4, 'active')
                    """,
                    user_id,
                    item_key,
                    quantity,
                    price,
                )
        schedule_balance_event(
            self.pool,
            "market_list",
            user_id,
            details={
                "item_id": item_key,
                "name": entry.name,
                "emoji": entry.emoji,
                "quantity": quantity,
                "price": price,
            },
        )
        catalog = await self.get_market_catalog(
            user_id,
            category_id=category_id,
            page=page,
            search=search,
            price_filter=price_filter,
            sort_by=sort_by,
            sort_order=sort_order,
            page_size=page_size,
        )
        catalog["listed"] = {
            "itemId": item_key,
            "name": entry.name,
            "emoji": entry.emoji,
            "quantity": quantity,
            "price": price,
        }
        catalog["player"] = await self._player_snapshot(user_id)
        return catalog

    async def buy_market_listing(
        self,
        user_id,
        listing_id,
        quantity,
        *,
        category_id=None,
        page=0,
        search="",
        price_filter="all",
        sort_by="name",
        sort_order="asc",
        page_size=None,
    ):
        await self.ensure_user(user_id)
        listing_id = int(listing_id)
        quantity = max(1, min(int(quantity), 99))
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SET LOCAL lock_timeout = '4000ms'")
                row = await conn.fetchrow(
                    """
                    SELECT l.id, l.seller_id, l.item_id, l.quantity, l.price, l.status,
                           d.name, d.emoji
                    FROM market_listings l
                    LEFT JOIN dex d ON CAST(d.id AS TEXT) = l.item_id
                    WHERE l.id = $1
                    FOR UPDATE OF l
                    """,
                    listing_id,
                )
                if not row or row["status"] != "active":
                    raise ValueError("Лот не найден или уже продан")
                if int(row["seller_id"]) == int(user_id):
                    raise ValueError("Нельзя купить свой лот")
                available = int(row["quantity"] or 0)
                if available < 1:
                    raise ValueError("Лот закончился")
                buy_qty = min(quantity, available)
                unit_price = int(row["price"] or 0)
                total_cost = unit_price * buy_qty
                from market_rules import calc_market_commission, calc_market_seller_payout

                commission = calc_market_commission(total_cost)
                seller_payout = calc_market_seller_payout(total_cost)
                seller_id = int(row["seller_id"])
                user_rows = await conn.fetch(
                    """
                    SELECT user_id, balance, items FROM users
                    WHERE user_id = ANY($1::bigint[])
                    ORDER BY user_id
                    FOR UPDATE
                    """,
                    [user_id, seller_id],
                )
                users_by_id = {int(r["user_id"]): r for r in user_rows}
                buyer_row = users_by_id.get(user_id)
                seller_row = users_by_id.get(seller_id)
                if buyer_row is None:
                    raise ValueError("Профиль не найден")
                if seller_row is None:
                    raise ValueError("Продавец не найден")
                buyer_balance = int(buyer_row["balance"])
                seller_balance = int(seller_row["balance"])
                if buyer_balance < total_cost:
                    raise ValueError(f"У Вас недостаточно кут (нужно {total_cost})")
                buyer_raw = parse_items(buyer_row["items"])
                buyer_stored = add_shop_item_to_storage(buyer_raw, str(row["item_id"]), buy_qty)
                await conn.execute(
                    """
                    UPDATE users
                    SET balance = balance - $2, items = $3
                    WHERE user_id = $1
                    """,
                    user_id,
                    total_cost,
                    items_to_db(buyer_stored),
                )
                await conn.execute(
                    """
                    UPDATE users
                    SET balance = balance + $2,
                        market_sales_count = market_sales_count + 1,
                        market_items_sold = market_items_sold + $3
                    WHERE user_id = $1
                    """,
                    int(row["seller_id"]),
                    seller_payout,
                    buy_qty,
                )
                remaining = available - buy_qty
                if remaining <= 0:
                    await conn.execute(
                        """
                        UPDATE market_listings
                        SET quantity = 0, status = 'sold'
                        WHERE id = $1
                        """,
                        listing_id,
                    )
                else:
                    await conn.execute(
                        "UPDATE market_listings SET quantity = $2 WHERE id = $1",
                        listing_id,
                        remaining,
                    )
        from config import TECH_CHAT_ID

        await self.update_chat_balance(TECH_CHAT_ID, commission)
        schedule_balance_event(
            self.pool,
            "market_buy",
            user_id,
            amount=-total_cost,
            details={
                "listing_id": listing_id,
                "item_id": str(row["item_id"]),
                "name": row["name"] or str(row["item_id"]),
                "emoji": row["emoji"] or "📦",
                "quantity": buy_qty,
                "paid": total_cost,
                "seller_id": int(row["seller_id"]),
            },
        )
        schedule_balance_event(
            self.pool,
            "market_sell",
            int(row["seller_id"]),
            amount=seller_payout,
            details={
                "listing_id": listing_id,
                "item_id": str(row["item_id"]),
                "name": row["name"] or str(row["item_id"]),
                "emoji": row["emoji"] or "📦",
                "quantity": buy_qty,
                "gross": total_cost,
                "commission": commission,
                "payout": seller_payout,
                "buyer_id": user_id,
            },
        )
        seller_balance_after = int(seller_balance) + seller_payout
        sale_name = row["name"] or str(row["item_id"])
        sale_emoji = row["emoji"] or "📦"
        await create_market_sale_notification(
            self.pool,
            int(row["seller_id"]),
            listing_id=listing_id,
            item_id=str(row["item_id"]),
            name=sale_name,
            emoji=sale_emoji,
            quantity=buy_qty,
            gross=total_cost,
            commission=commission,
            payout=seller_payout,
            balance=seller_balance_after,
            buyer_id=user_id,
        )
        schedule_market_sale_telegram(
            int(row["seller_id"]),
            emoji=sale_emoji,
            name=sale_name,
            quantity=buy_qty,
            gross=total_cost,
            commission=commission,
            payout=seller_payout,
            balance=seller_balance_after,
        )
        catalog = await self.get_market_catalog(
            user_id,
            category_id=category_id,
            page=page,
            search=search,
            price_filter=price_filter,
            sort_by=sort_by,
            sort_order=sort_order,
            page_size=page_size,
        )
        catalog["purchased"] = {
            "listingId": listing_id,
            "name": row["name"] or str(row["item_id"]),
            "emoji": row["emoji"] or "📦",
            "quantity": buy_qty,
            "paid": total_cost,
        }
        catalog["player"] = await self._player_snapshot(user_id)
        return catalog

    async def update_chat_balance(self, chat_id, amount):
        """Зачисляет amount КУТ в chatbalance указанного чата."""
        try:
            chat_id = int(chat_id)
            amount = int(amount)
            if amount <= 0:
                return False
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    "UPDATE chat SET chatbalance = chatbalance + $1 WHERE chat_id = $2",
                    amount,
                    chat_id,
                )
            return result == "UPDATE 1"
        except Exception as e:
            logging.warning("update_chat_balance error chat_id=%s: %s", chat_id, e)
            return False

    async def ensure_chat_row(self, chat_id):
        """Создаёт строку чата если её нет."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO chat (chat_id, chatbalance, dexbalance)
                    VALUES ($1, 0, 0)
                    ON CONFLICT (chat_id) DO NOTHING
                    """,
                    int(chat_id),
                )
        except Exception as e:
            logging.warning("ensure_chat_row error chat_id=%s: %s", chat_id, e)

    async def get_chat_balances(self, chat_id):
        """Возвращает (chatbalance, dexbalance). Создаёт строку если нет."""
        await self.ensure_chat_row(chat_id)
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT chatbalance, dexbalance FROM chat WHERE chat_id = $1",
                    int(chat_id),
                )
            if row:
                return (int(row["chatbalance"] or 0), int(row["dexbalance"] or 0))
            return (0, 0)
        except Exception as e:
            logging.warning("get_chat_balances error chat_id=%s: %s", chat_id, e)
            return (0, 0)

    async def cancel_market_listing(
        self,
        user_id,
        listing_id,
        *,
        category_id=None,
        page=0,
        search="",
        price_filter="all",
        sort_by="name",
        sort_order="asc",
        page_size=None,
    ):
        await self.ensure_user(user_id)
        listing_id = int(listing_id)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT id, seller_id, item_id, quantity, status
                    FROM market_listings
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    listing_id,
                )
                if not row or row["status"] != "active":
                    raise ValueError("Лот не найден")
                if int(row["seller_id"]) != int(user_id):
                    raise ValueError("Можно снять только свой лот")
                qty = int(row["quantity"] or 0)
                if qty < 1:
                    raise ValueError("Лот уже пуст")
                items_raw = await conn.fetchval(
                    "SELECT items FROM users WHERE user_id = $1 FOR UPDATE", user_id
                )
                raw_items = parse_items(items_raw)
                stored = add_shop_item_to_storage(raw_items, str(row["item_id"]), qty)
                await conn.execute(
                    "UPDATE users SET items = $2 WHERE user_id = $1", user_id, items_to_db(stored)
                )
                await conn.execute(
                    """
                    UPDATE market_listings
                    SET quantity = 0, status = 'cancelled'
                    WHERE id = $1
                    """,
                    listing_id,
                )
        catalog = await self.get_market_catalog(
            user_id,
            category_id=category_id,
            page=page,
            search=search,
            price_filter=price_filter,
            sort_by=sort_by,
            sort_order=sort_order,
            page_size=page_size,
        )
        catalog["player"] = await self._player_snapshot(user_id)
        return catalog

    async def sync_user_profile(self, user_id, tg_user):
        from player_profile import profile_from_telegram_user

        if int(tg_user.get("id") or 0) != int(user_id):
            return None
        await self.ensure_user(user_id)
        data = profile_from_telegram_user(tg_user)
        lang_raw = tg_user.get("language_code") if isinstance(tg_user, dict) else None
        lang = str(lang_raw).strip()[:16] if lang_raw else None
        if lang == "":
            lang = None
        premium = tg_user.get("is_premium") if isinstance(tg_user, dict) else None
        is_premium = bool(premium) if premium is not None else None
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET username = $2,
                    first_name = $3,
                    last_name = $4,
                    display_name = $5,
                    photo_url = $6,
                    last_language_code = COALESCE($7, last_language_code),
                    is_premium = COALESCE($8, is_premium),
                    profile_updated_at = NOW()
                WHERE user_id = $1
                """,
                user_id,
                data["username"],
                data["first_name"],
                data["last_name"],
                data["display_name"],
                data["photo_url"],
                lang,
                is_premium,
            )
        return None

    async def sync_user_profile_throttled(self, user_id, tg_user):
        """Sync Telegram profile at most once per PROFILE_SYNC_INTERVAL_SECONDS."""
        import time
        from config import PROFILE_SYNC_INTERVAL_SECONDS

        now = time.monotonic()
        last = self._profile_sync_at.get(user_id, 0.0)
        if now - last < PROFILE_SYNC_INTERVAL_SECONDS:
            return None
        self._profile_sync_at[user_id] = now
        await self.sync_user_profile(user_id, tg_user)
        return None

    async def get_public_profile(self, viewer_id, target_user_id):
        from player_profile import profile_row_to_client

        target_user_id = int(target_user_id)
        if target_user_id <= 0:
            raise ValueError("Профиль не найден")
        await self.ensure_user(viewer_id)
        await self.ensure_user(target_user_id)
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT user_id, username, first_name, last_name, display_name, photo_url,
                       market_sales_count, market_items_sold
                FROM users
                WHERE user_id = $1
                """,
                target_user_id,
            )
            active_listings = await conn.fetchval(
                """
                SELECT COUNT(*)::int
                FROM market_listings
                WHERE seller_id = $1 AND status = 'active' AND quantity > 0
                """,
                target_user_id,
            )
        return profile_row_to_client(
            dict(row) if row else None,
            user_id=target_user_id,
            active_listings=int(active_listings or 0),
            viewer_id=viewer_id,
        )

    async def get_pending_notifications(self, user_id, *, limit=20):
        await self.ensure_user(user_id)
        limit = max(1, min(int(limit), 20))
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, event_type, payload, created_at
                FROM user_notifications
                WHERE user_id = $1 AND web_delivered = FALSE
                ORDER BY created_at ASC
                LIMIT $2
                """,
                user_id,
                limit,
            )
        result = []
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            result.append(
                {
                    "id": int(row["id"]),
                    "eventType": row["event_type"],
                    "payload": payload or {},
                    "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
                }
            )
        return result

    async def ack_notifications(self, user_id, notification_ids):
        if not notification_ids:
            return 0
        ids = [int(nid) for nid in notification_ids if int(nid) > 0]
        if not ids:
            return 0
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE user_notifications
                SET web_delivered = TRUE
                WHERE user_id = $1 AND id = ANY($2::bigint[]) AND web_delivered = FALSE
                """,
                user_id,
                ids,
            )
        try:
            return int(str(result).split()[-1])
        except (ValueError, IndexError):
            return 0

    async def get_my_profile_and_leaderboard(self, user_id):
        from player_profile import format_display_name

        await self.ensure_user(user_id)
        boards = {
            "balance": "balance",
            "harvests": "harvest_count",
            "sales": "market_items_sold",
        }
        leaderboard = {"total": 0, "myRank": {}, "myValue": {}}
        async with self.pool.acquire() as conn:
            me = await conn.fetchrow(
                """
                SELECT user_id, username, first_name, last_name, display_name, photo_url,
                       balance, harvest_count, craft_count,
                       market_items_sold, market_sales_count, created_at
                FROM users WHERE user_id = $1
                """,
                user_id,
            )
            total = await conn.fetchval("SELECT COUNT(*)::int FROM users")
            leaderboard["total"] = int(total or 0)
            for board_id, column in boards.items():
                rows = await conn.fetch(
                    f"""
                    SELECT user_id, username, first_name, last_name, display_name, photo_url,
                           {column} AS value
                    FROM users
                    WHERE {column} > 0
                    ORDER BY {column} DESC, user_id ASC
                    LIMIT 10
                    """
                )
                board_rows = []
                for idx, row in enumerate(rows):
                    uid = int(row["user_id"])
                    board_rows.append(
                        {
                            "rank": idx + 1,
                            "userId": uid,
                            "name": format_display_name(
                                first_name=row["first_name"],
                                last_name=row["last_name"],
                                username=row["username"],
                                display_name=row["display_name"],
                                user_id=uid,
                            ),
                            "photoUrl": (row["photo_url"] or "").strip() or None,
                            "value": int(row["value"] or 0),
                            "isMe": uid == int(user_id),
                        }
                    )
                leaderboard[board_id] = board_rows
                my_value = int((me[column] if me else 0) or 0)
                leaderboard["myValue"][board_id] = my_value
                if my_value > 0:
                    greater = await conn.fetchval(
                        f"SELECT COUNT(*)::int FROM users WHERE {column} > $1",
                        my_value,
                    )
                    leaderboard["myRank"][board_id] = int(greater or 0) + 1
                else:
                    leaderboard["myRank"][board_id] = 0

        uid = int(me["user_id"]) if me else int(user_id)
        display = format_display_name(
            first_name=me["first_name"] if me else None,
            last_name=me["last_name"] if me else None,
            username=me["username"] if me else None,
            display_name=me["display_name"] if me else None,
            user_id=uid,
        )
        username = ((me["username"] if me else None) or "").strip().lstrip("@") or None
        photo = ((me["photo_url"] if me else None) or "").strip() or None
        created_at = me["created_at"] if me else None
        days_in_game = 0
        if created_at is not None:
            days_in_game = max(0, (now() - created_at).days)
        profile = {
            "userId": uid,
            "displayName": display,
            "username": username,
            "photoUrl": photo,
            "balance": int((me["balance"] if me else 0) or 0),
            "daysInGame": days_in_game,
            "harvestCount": int((me["harvest_count"] if me else 0) or 0),
            "craftCount": int((me["craft_count"] if me else 0) or 0),
            "marketItemsSold": int((me["market_items_sold"] if me else 0) or 0),
            "marketSalesCount": int((me["market_sales_count"] if me else 0) or 0),
        }
        return {"profile": profile, "leaderboard": leaderboard}


db = Database()
