# -*- coding: utf-8 -*-
"""Ника: схема в Postgres. Вызывать один раз на старте бота.

По образцу остальных ensure_*_schema в этом проекте: только CREATE TABLE IF
NOT EXISTS / ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS, никаких
DROP и никакого DDL в горячем пути. Функция идемпотентна - повторный запуск
после перезапуска бота ничего не ломает и ничего не переписывает.

Всё состояние системы живёт ТОЛЬКО здесь, в этих таблицах. В памяти процесса
не хранится ни один счётчик, ни один кулдаун - поэтому перезапуск бота не
приводит ни к повторным переводам, ни к потере кулдауна.

Таблицы:
  • nika_settings        - одна строка (id=1): общий выключатель, шаг тика,
                           троттлинг писем владельцу, метка последнего тика.
  • nika_group_settings  - по строке на обслуживаемую группу: цель, режим
                           скорости, мёртвая зона, потолки, свой выключатель.
                           Группы, которой здесь нет, система не касается.
  • nika_balance_sample  - срезы баланса группы: из них считается скорость
                           убывания и «выдержка» излишка перед сбором.
  • nika_transfer_log    - журнал КАЖДОГО перевода: до/после, причина, статус,
                           плюс поля для ручного откада любой операции.
"""

from __future__ import annotations

from bot.config.config import GROWTH_FUND_OWNER_NOTIFY_USER_ID, PROFIT_JAR_CHAT_ID

# Первая группа под Никой - решение владельца. Сид одноразовый (ON CONFLICT DO
# NOTHING), поэтому все последующие правки владельца переживают перезапуск.
FIRST_MANAGED_CHAT_ID = -1001612636292
FIRST_MANAGED_TARGET = 5000

_DDL = """
CREATE TABLE IF NOT EXISTS nika_settings (
    id SMALLINT PRIMARY KEY DEFAULT 1,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    dry_run BOOLEAN NOT NULL DEFAULT FALSE,
    tick_interval_sec INTEGER NOT NULL DEFAULT 20,
    sweep_speed TEXT NOT NULL DEFAULT 'fast',
    owner_alert_user_id BIGINT,
    owner_alert_cooldown_sec INTEGER NOT NULL DEFAULT 21600,
    last_owner_alert_at TIMESTAMPTZ,
    last_tick_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT nika_settings_singleton CHECK (id = 1),
    CONSTRAINT nika_settings_tick_range CHECK (tick_interval_sec BETWEEN 15 AND 3600),
    CONSTRAINT nika_settings_sweep_speed CHECK (sweep_speed IN ('instant', 'fast', 'medium', 'slow')),
    CONSTRAINT nika_settings_alert_cooldown CHECK (owner_alert_cooldown_sec >= 600)
);

INSERT INTO nika_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS nika_group_settings (
    chat_id BIGINT PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    target_balance BIGINT NOT NULL,
    speed_mode TEXT NOT NULL DEFAULT 'auto',
    dead_zone_pct DOUBLE PRECISION NOT NULL DEFAULT 0.05,
    dead_zone_min BIGINT NOT NULL DEFAULT 100,
    max_transfer BIGINT NOT NULL DEFAULT 1000,
    max_daily_topup BIGINT NOT NULL DEFAULT 10000,
    max_daily_sweep BIGINT NOT NULL DEFAULT 10000,
    sweep_share DOUBLE PRECISION NOT NULL DEFAULT 0.90,
    sweep_delay_sec INTEGER NOT NULL DEFAULT 45,
    sweep_cooldown_sec INTEGER NOT NULL DEFAULT 30,
    last_topup_at TIMESTAMPTZ,
    last_sweep_at TIMESTAMPTZ,
    note TEXT,
    updated_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT nika_group_target_nonneg CHECK (target_balance >= 0),
    CONSTRAINT nika_group_speed_mode CHECK (speed_mode IN ('auto', 'slow', 'medium', 'aggressive')),
    CONSTRAINT nika_group_dead_zone_pct CHECK (dead_zone_pct >= 0 AND dead_zone_pct <= 1),
    CONSTRAINT nika_group_dead_zone_min CHECK (dead_zone_min >= 0),
    CONSTRAINT nika_group_max_transfer CHECK (max_transfer >= 0),
    CONSTRAINT nika_group_max_daily_topup CHECK (max_daily_topup >= 0),
    CONSTRAINT nika_group_max_daily_sweep CHECK (max_daily_sweep >= 0),
    CONSTRAINT nika_group_sweep_share CHECK (sweep_share > 0 AND sweep_share <= 1),
    CONSTRAINT nika_group_sweep_delay CHECK (sweep_delay_sec >= 8),
    CONSTRAINT nika_group_sweep_cooldown CHECK (sweep_cooldown_sec >= 8)
);

-- Тик перебирает только включённые группы, их единицы - частичный индекс
-- держит обход коротким и не растёт вместе с выключенными строками.
CREATE INDEX IF NOT EXISTS idx_nika_group_enabled
    ON nika_group_settings (chat_id)
    WHERE enabled;

CREATE TABLE IF NOT EXISTS nika_balance_sample (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    balance BIGINT NOT NULL,
    target_balance BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Таблица растущая: каждый запрос по ней идёт как (chat_id, окно времени).
CREATE INDEX IF NOT EXISTS idx_nika_sample_chat_created
    ON nika_balance_sample (chat_id, created_at DESC);

CREATE TABLE IF NOT EXISTS nika_transfer_log (
    id BIGSERIAL PRIMARY KEY,
    idem_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    chat_id BIGINT NOT NULL,
    source_chat_id BIGINT NOT NULL,
    dest_chat_id BIGINT NOT NULL,
    amount BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT NOT NULL DEFAULT '',
    speed_mode TEXT,
    activity_tier TEXT,
    target_balance BIGINT,
    source_balance_before BIGINT,
    source_balance_after BIGINT,
    dest_balance_before BIGINT,
    dest_balance_after BIGINT,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    revert_requested_at TIMESTAMPTZ,
    revert_requested_by BIGINT,
    reverted_at TIMESTAMPTZ,
    revert_transfer_id BIGINT,
    reverts_transfer_id BIGINT,
    CONSTRAINT nika_transfer_amount_pos CHECK (amount > 0),
    CONSTRAINT nika_transfer_kind CHECK (kind IN ('topup', 'sweep', 'revert')),
    CONSTRAINT nika_transfer_status CHECK (
        status IN ('pending', 'done', 'failed', 'refunded', 'refund_failed', 'dry_run')
    ),
    CONSTRAINT nika_transfer_not_self CHECK (source_chat_id <> dest_chat_id)
);

-- Идемпотентность: ключ детерминирован (тип|группа|слот времени|источник),
-- поэтому повторная попытка того же перевода упирается в уникальность, а не
-- двигает куты второй раз.
CREATE UNIQUE INDEX IF NOT EXISTS uq_nika_transfer_idem
    ON nika_transfer_log (idem_key);

CREATE INDEX IF NOT EXISTS idx_nika_transfer_chat_created
    ON nika_transfer_log (chat_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_nika_transfer_kind_created
    ON nika_transfer_log (kind, created_at DESC);

-- Очередь ручных откатов: строк тут почти всегда ноль, поэтому частичный.
CREATE INDEX IF NOT EXISTS idx_nika_transfer_revert_queue
    ON nika_transfer_log (revert_requested_at)
    WHERE revert_requested_at IS NOT NULL AND reverted_at IS NULL;

-- Незакрытые переводы (процесс умер между списанием и зачислением).
CREATE INDEX IF NOT EXISTS idx_nika_transfer_pending
    ON nika_transfer_log (created_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_nika_transfer_heal
    ON nika_transfer_log (status, created_at)
    WHERE status IN ('pending', 'refund_failed');

ALTER TABLE nika_settings ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE nika_settings ADD COLUMN IF NOT EXISTS last_error_at TIMESTAMPTZ;
ALTER TABLE nika_settings ADD COLUMN IF NOT EXISTS heal_ok_streak INTEGER NOT NULL DEFAULT 0;
ALTER TABLE nika_settings ADD COLUMN IF NOT EXISTS earnings_since TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Инциденты: только то, что код уже пробовал починить и не смог.
-- Обычный кулдаун / мёртвая зона сюда не попадают.
CREATE TABLE IF NOT EXISTS nika_incidents (
    id BIGSERIAL PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    code TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'critical',
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    chat_id BIGINT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    actions JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'open',
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by BIGINT,
    resolve_note TEXT,
    CONSTRAINT nika_incident_severity CHECK (severity IN ('critical', 'warning')),
    CONSTRAINT nika_incident_status CHECK (status IN ('open', 'ack', 'resolved'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_nika_incident_open
    ON nika_incidents (fingerprint)
    WHERE status = 'open';

CREATE INDEX IF NOT EXISTS idx_nika_incident_open
    ON nika_incidents (severity, updated_at DESC)
    WHERE status = 'open';

-- Команды из админки. Деньги двигает ТОЛЬКО процесс бота, иначе
-- fastlane-кэш игр останется со старым балансом.
CREATE TABLE IF NOT EXISTS nika_operator_commands (
    id BIGSERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'queued',
    requested_by BIGINT,
    error TEXT,
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    CONSTRAINT nika_cmd_status CHECK (status IN ('queued', 'running', 'done', 'failed')),
    CONSTRAINT nika_cmd_kind CHECK (
        kind IN (
            'force_tick', 'force_topup', 'force_sweep', 'now_sweep', 'retry_heal', 'revert',
            'pause_group', 'pause_all', 'enable_group', 'enable_all'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_nika_cmd_queue
    ON nika_operator_commands (created_at)
    WHERE status = 'queued';

ALTER TABLE nika_operator_commands DROP CONSTRAINT IF EXISTS nika_cmd_kind;
ALTER TABLE nika_operator_commands ADD CONSTRAINT nika_cmd_kind CHECK (
    kind IN (
        'force_tick', 'force_topup', 'force_sweep', 'now_sweep', 'retry_heal', 'revert',
        'pause_group', 'pause_all', 'enable_group', 'enable_all'
    )
);

-- Срезы «все балансы»: из них видно, когда вселенная кут росла и когда сжималась.
CREATE TABLE IF NOT EXISTS nika_universe_sample (
    id BIGSERIAL PRIMARY KEY,
    users_balance BIGINT NOT NULL DEFAULT 0,
    chats_balance BIGINT NOT NULL DEFAULT 0,
    live_chats_balance BIGINT NOT NULL DEFAULT 0,
    managed_balance BIGINT NOT NULL DEFAULT 0,
    ladder_balance BIGINT NOT NULL DEFAULT 0,
    vault_balance BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nika_universe_created
    ON nika_universe_sample (created_at DESC);

ALTER TABLE nika_universe_sample ADD COLUMN IF NOT EXISTS users_balance BIGINT NOT NULL DEFAULT 0;
ALTER TABLE nika_universe_sample ADD COLUMN IF NOT EXISTS chats_balance BIGINT NOT NULL DEFAULT 0;
ALTER TABLE nika_universe_sample ADD COLUMN IF NOT EXISTS live_chats_balance BIGINT NOT NULL DEFAULT 0;
ALTER TABLE nika_universe_sample ADD COLUMN IF NOT EXISTS managed_balance BIGINT NOT NULL DEFAULT 0;
ALTER TABLE nika_universe_sample ADD COLUMN IF NOT EXISTS ladder_balance BIGINT NOT NULL DEFAULT 0;
ALTER TABLE nika_universe_sample ADD COLUMN IF NOT EXISTS vault_balance BIGINT NOT NULL DEFAULT 0;

ALTER TABLE nika_settings ADD COLUMN IF NOT EXISTS sweep_speed TEXT NOT NULL DEFAULT 'fast';
ALTER TABLE nika_settings DROP CONSTRAINT IF EXISTS nika_settings_tick_range;
ALTER TABLE nika_settings ADD CONSTRAINT nika_settings_tick_range
    CHECK (tick_interval_sec BETWEEN 15 AND 3600);
ALTER TABLE nika_settings DROP CONSTRAINT IF EXISTS nika_settings_sweep_speed;
ALTER TABLE nika_settings ADD CONSTRAINT nika_settings_sweep_speed
    CHECK (sweep_speed IN ('instant', 'fast', 'medium', 'slow'));
UPDATE nika_settings
   SET tick_interval_sec = 20
 WHERE id = 1
   AND tick_interval_sec = 180
   AND sweep_speed = 'fast';

ALTER TABLE nika_group_settings DROP CONSTRAINT IF EXISTS nika_group_sweep_delay;
ALTER TABLE nika_group_settings ADD CONSTRAINT nika_group_sweep_delay
    CHECK (sweep_delay_sec >= 8);
ALTER TABLE nika_group_settings DROP CONSTRAINT IF EXISTS nika_group_sweep_cooldown;
ALTER TABLE nika_group_settings ADD CONSTRAINT nika_group_sweep_cooldown
    CHECK (sweep_cooldown_sec >= 8);
"""

_LEDGER_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_gf_ledger_chat_created
    ON growth_fund_ledger (chat_id, created_at DESC);
"""

_SEED_FIRST_GROUP = """
INSERT INTO nika_group_settings (
    chat_id, enabled, target_balance, speed_mode,
    max_transfer, max_daily_topup, max_daily_sweep, note
)
VALUES ($1, TRUE, $2, 'auto', $3, $4, $4, 'первая группа под Никой')
ON CONFLICT (chat_id) DO NOTHING
"""


async def ready_nika_pool(db) -> None:
    """Пул готов и у бота (ensure_pool), и у API (уже открыт / connect)."""
    if getattr(db, "pool", None) is not None:
        return
    ensure = getattr(db, "ensure_pool", None)
    if callable(ensure):
        try:
            ok = bool(await ensure())
        except Exception as exc:
            raise RuntimeError("Пул соединений не инициализирован (ensure_nika_schema).") from exc
        if not ok or getattr(db, "pool", None) is None:
            raise RuntimeError("Пул соединений не инициализирован (ensure_nika_schema).")
        return
    opener = getattr(db, "ensure_connected", None) or getattr(db, "connect", None)
    if callable(opener):
        await opener()
    if getattr(db, "pool", None) is None:
        raise RuntimeError("Пул соединений не инициализирован (ensure_nika_schema).")


async def ensure_nika_schema(db) -> None:
    """Создать/досоздать таблицы Ники и засеять первую обслуживаемую группу."""
    await ready_nika_pool(db)

    from bot.runtime.nika.policy import SOURCE_LADDER, suggest_caps

    caps = suggest_caps(FIRST_MANAGED_TARGET)
    owner_id = int(GROWTH_FUND_OWNER_NOTIFY_USER_ID or 0) or None
    async with db.pool.acquire() as conn:
        await conn.execute(_DDL)
        try:
            await conn.execute(_LEDGER_INDEX_SQL)
        except Exception as exc:
            # Таблицы комиссий может ещё не быть на свежей базе — индекс
            # не обязателен для работы Ники, тик просто посчитает 0 событий.
            print(f"[NIKA][SCHEMA] ledger index skip: {type(exc).__name__}: {exc}")
        await conn.execute(
            _SEED_FIRST_GROUP,
            int(FIRST_MANAGED_CHAT_ID),
            int(FIRST_MANAGED_TARGET),
            int(caps["max_transfer"]),
            int(caps["max_daily_topup"]),
        )
        await conn.execute(
            """
            UPDATE nika_settings
            SET owner_alert_user_id = COALESCE(owner_alert_user_id, $1)
            WHERE id = 1
            """,
            owner_id,
        )
        # Кассы сами себя не обслуживают: долив из копилки в копилку
        # или из кассы игр в кассу игр — это не баланс группы.
        forbidden = {int(cid) for cid, _ in SOURCE_LADDER}
        forbidden.add(int(PROFIT_JAR_CHAT_ID))
        await conn.execute(
            "DELETE FROM nika_group_settings WHERE chat_id = ANY($1::bigint[])",
            sorted(forbidden),
        )
