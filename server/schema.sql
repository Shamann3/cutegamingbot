-- Базовые таблицы legacy-бота. Остальная схема ниже расширяет их через ALTER.
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    balance INT NOT NULL DEFAULT 0,
    items TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS dex (
    id INT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    name1 TEXT NOT NULL DEFAULT '',
    emoji TEXT NOT NULL DEFAULT '📦',
    price INT NOT NULL DEFAULT 0,
    dis INT NOT NULL DEFAULT 0,
    remains INT NOT NULL DEFAULT 0,
    sorting TEXT,
    bio TEXT NOT NULL DEFAULT '',
    "use" TEXT,
    bonus TEXT,
    craft TEXT
);

-- Грядки: до 10 на игрока, состояние сохраняется в БД
CREATE TABLE IF NOT EXISTS farm_plots (
    user_id BIGINT NOT NULL,
    plot_id INT NOT NULL CHECK (plot_id BETWEEN 1 AND 150),
    status TEXT NOT NULL DEFAULT 'EMPTY',
    planted_at TIMESTAMPTZ,
    ripe_at TIMESTAMPTZ,
    dry_at TIMESTAMPTZ,
    needs_water BOOLEAN NOT NULL DEFAULT FALSE,
    wilt_at TIMESTAMPTZ,
    waters_remaining INT NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, plot_id)
);

ALTER TABLE farm_plots ADD COLUMN IF NOT EXISTS waters_remaining INT NOT NULL DEFAULT 0;
ALTER TABLE farm_plots ADD COLUMN IF NOT EXISTS crop_id TEXT;
ALTER TABLE farm_plots ADD COLUMN IF NOT EXISTS autowater_active BOOLEAN NOT NULL DEFAULT FALSE;

-- Если таблица уже была с лимитом 4/10 грядок — поднять до 150:
ALTER TABLE farm_plots DROP CONSTRAINT IF EXISTS farm_plots_plot_id_check;
ALTER TABLE farm_plots ADD CONSTRAINT farm_plots_plot_id_check CHECK (plot_id BETWEEN 1 AND 150);

-- Логи покупок и изменений баланса
CREATE TABLE IF NOT EXISTS audit_events (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id BIGINT NOT NULL,
    event_type TEXT NOT NULL,
    amount INT,
    balance_before INT,
    balance_after INT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS audit_events_created_at_idx ON audit_events (created_at DESC);
CREATE INDEX IF NOT EXISTS audit_events_user_id_idx ON audit_events (user_id);

-- Журнал P2P-переводов (команда "дать") - одна строка на весь перевод,
-- баланс до/после у обеих сторон, пишется атомарно вместе с самим переводом
-- (bot/db_create/db.py::transfer_currency).
CREATE TABLE IF NOT EXISTS p2p_transfers (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sender_id BIGINT NOT NULL,
    receiver_id BIGINT NOT NULL,
    amount BIGINT NOT NULL,
    sender_balance_before BIGINT NOT NULL,
    sender_balance_after BIGINT NOT NULL,
    receiver_balance_before BIGINT NOT NULL,
    receiver_balance_after BIGINT NOT NULL,
    cause TEXT NOT NULL DEFAULT 'дать'
);

CREATE INDEX IF NOT EXISTS p2p_transfers_sender_idx ON p2p_transfers (sender_id, created_at DESC);
CREATE INDEX IF NOT EXISTS p2p_transfers_receiver_idx ON p2p_transfers (receiver_id, created_at DESC);
CREATE INDEX IF NOT EXISTS p2p_transfers_created_idx ON p2p_transfers (created_at DESC);

-- Игровые события для аналитики (всегда пишутся, без Telegram-нотификаций)
CREATE TABLE IF NOT EXISTS game_events (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id BIGINT NOT NULL,
    event_type TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS game_events_type_time_idx ON game_events (event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS game_events_user_time_idx ON game_events (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS game_events_created_at_idx ON game_events (created_at DESC);

-- Заметки администраторов о конкретных игроках
CREATE TABLE IF NOT EXISTS player_admin_notes (
    id BIGSERIAL PRIMARY KEY,
    player_id BIGINT NOT NULL,
    admin_user_id BIGINT NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS player_admin_notes_player_idx ON player_admin_notes (player_id, created_at DESC);

-- Культуры фермы и крафт — настраиваются из admin-панели (Content).
CREATE TABLE IF NOT EXISTS farm_crops (
    id SERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL DEFAULT '',
    seed_item_id TEXT NOT NULL,
    grow_seconds INT NOT NULL DEFAULT 1200 CHECK (grow_seconds >= 30),
    harvest_tool_item_id TEXT,
    harvest_tool_cost INT NOT NULL DEFAULT 1 CHECK (harvest_tool_cost >= 1),
    water_item_id TEXT,
    water_cost_per_use INT CHECK (water_cost_per_use IS NULL OR water_cost_per_use >= 1),
    sprite_key TEXT NOT NULL DEFAULT 'generic',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS farm_crop_harvest_drops (
    id SERIAL PRIMARY KEY,
    crop_id INT NOT NULL REFERENCES farm_crops(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    min_amount INT NOT NULL DEFAULT 1 CHECK (min_amount >= 1),
    max_amount INT NOT NULL DEFAULT 1 CHECK (max_amount >= 1),
    chance_percent INT NOT NULL DEFAULT 100 CHECK (chance_percent BETWEEN 1 AND 100),
    sort_order INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS farm_crop_harvest_drops_crop_idx
    ON farm_crop_harvest_drops (crop_id, sort_order, id);

CREATE TABLE IF NOT EXISTS craft_recipes (
    id SERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL DEFAULT '',
    result_item_id TEXT NOT NULL,
    ingredient_a_id TEXT NOT NULL,
    ingredient_b_id TEXT NOT NULL,
    success_percent INT NOT NULL DEFAULT 100 CHECK (success_percent BETWEEN 1 AND 100),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE craft_recipes ADD COLUMN IF NOT EXISTS display_name TEXT NOT NULL DEFAULT '';
ALTER TABLE craft_recipes ADD COLUMN IF NOT EXISTS remains INT NOT NULL DEFAULT 0;
ALTER TABLE craft_recipes ADD COLUMN IF NOT EXISTS result_qty INT NOT NULL DEFAULT 1;
-- result_qty: сколько предметов выдаётся при успешном крафте

-- Обучение при первом входе
ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_done BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_active BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_seed_granted INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_demo_logs INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_step INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS tool_durability JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Экономика семян: стартовый набор + ежедневная выдача
ALTER TABLE users ADD COLUMN IF NOT EXISTS starter_pack_granted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_seed_claimed_on DATE;

-- Прогресс заданий NPC (ежедневные / почасовые / недельные)
ALTER TABLE users ADD COLUMN IF NOT EXISTS quest_progress JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS quests (
    id SERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    period TEXT NOT NULL CHECK (period IN ('hourly', 'daily', 'weekly')),
    action TEXT NOT NULL,
    target INT NOT NULL CHECK (target >= 1),
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    emoji TEXT NOT NULL DEFAULT '📋',
    target_scope TEXT NOT NULL DEFAULT 'any',
    target_crop_key TEXT,
    target_item_id TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE quests ADD COLUMN IF NOT EXISTS target_scope TEXT NOT NULL DEFAULT 'any';
ALTER TABLE quests ADD COLUMN IF NOT EXISTS target_crop_key TEXT;
ALTER TABLE quests ADD COLUMN IF NOT EXISTS target_item_id TEXT;

-- Scheduling for timed/recurring quests
ALTER TABLE quests ADD COLUMN IF NOT EXISTS active_from TIMESTAMPTZ;
ALTER TABLE quests ADD COLUMN IF NOT EXISTS active_until TIMESTAMPTZ;
ALTER TABLE quests ADD COLUMN IF NOT EXISTS recurrence TEXT CHECK (recurrence IN ('daily', 'weekly'));
ALTER TABLE quests ADD COLUMN IF NOT EXISTS recurrence_end TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS quest_rewards (
    id SERIAL PRIMARY KEY,
    quest_id INT NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('kut', 'item')),
    amount INT NOT NULL CHECK (amount >= 1),
    item_id TEXT,
    sort_order INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS quest_rewards_quest_idx ON quest_rewards (quest_id, sort_order, id);

CREATE TABLE IF NOT EXISTS market_listings (
    id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT NOT NULL,
    item_id TEXT NOT NULL,
    quantity INT NOT NULL,
    price INT NOT NULL CHECK (price > 0),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'sold', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT market_listings_quantity_check CHECK (status <> 'active' OR quantity > 0)
);

-- Активные лоты: quantity > 0; проданные/снятые могут иметь 0
ALTER TABLE market_listings DROP CONSTRAINT IF EXISTS market_listings_quantity_check;
ALTER TABLE market_listings ADD CONSTRAINT market_listings_quantity_check
    CHECK (status <> 'active' OR quantity > 0);

CREATE INDEX IF NOT EXISTS market_listings_active_idx
    ON market_listings (status, created_at DESC)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS market_listings_seller_idx
    ON market_listings (seller_id)
    WHERE status = 'active';

-- Уведомления для WebApp (продажа на бирже и др.)
CREATE TABLE IF NOT EXISTS user_notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    web_delivered BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS user_notifications_pending_idx
    ON user_notifications (user_id, created_at ASC)
    WHERE web_delivered = FALSE;

-- Профили игроков (имя из Telegram Web App)
ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS photo_url TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_updated_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS market_sales_count INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS market_items_sold INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS harvest_count INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS craft_count INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS harvest_notify BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE farm_plots ADD COLUMN IF NOT EXISTS harvest_notified BOOLEAN NOT NULL DEFAULT FALSE;

-- Модерация. Эти колонки создаёт код бота (ban.py / mute.py), которого нет в
-- контейнере сервера. Дублируем idempotent, иначе на «чистой» БД (managed на
-- хостинге) rate_limit._check_user_status падает на отсутствующей колонке и
-- отдаёт 503 на КАЖДЫЙ авторизованный запрос.
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_reason TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS mute_until TIMESTAMPTZ;

-- Подтянуть прошлые продажи из audit_events (если логи включались)
UPDATE users u
SET
    market_sales_count = COALESCE(sub.sales, 0),
    market_items_sold = COALESCE(sub.items, 0)
FROM (
    SELECT
        user_id,
        COUNT(*)::int AS sales,
        COALESCE(SUM((details->>'quantity')::int), 0)::int AS items
    FROM audit_events
    WHERE event_type = 'market_sell'
    GROUP BY user_id
) sub
WHERE u.user_id = sub.user_id
  AND (u.market_sales_count = 0 OR u.market_items_sold = 0);

-- Системные настройки (maintenance и др.)
CREATE TABLE IF NOT EXISTS system_settings (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    maintenance BOOLEAN NOT NULL DEFAULT FALSE,
    updated_by BIGINT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS default_balance INT;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS plot_price_step INT;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS clear_cost INT;

ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS tree_grow_seconds INT;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS tobacco_grow_seconds INT;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS max_plots INT;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS water_interval_seconds INT;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS wilt_grace_seconds INT;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS water_cost_per_use INT;

-- Seed economy runtime overrides
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS harvest_seed_drop_percent INT;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS daily_seed_amount INT;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS starter_tree_seeds INT;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS starter_tobacco_seeds INT;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS starter_water INT;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS starter_axe INT;

-- Admin session timeout override
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS admin_session_minutes INT;

-- История изменений настроек
CREATE TABLE IF NOT EXISTS settings_history (
    id BIGSERIAL PRIMARY KEY,
    admin_user_id BIGINT NOT NULL,
    category TEXT NOT NULL,
    setting_key TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS settings_history_time_idx ON settings_history (created_at DESC);
CREATE INDEX IF NOT EXISTS settings_history_category_idx ON settings_history (category, created_at DESC);

-- Admin panel: аккаунты и pending TOTP при регистрации
CREATE TABLE IF NOT EXISTS admin_accounts (
    user_id BIGINT PRIMARY KEY,
    totp_secret TEXT NOT NULL,
    username TEXT,
    first_name TEXT,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admin_register_pending (
    setup_token TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    totp_secret TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS admin_register_pending_user_idx
    ON admin_register_pending (user_id);

CREATE INDEX IF NOT EXISTS admin_register_pending_expires_idx
    ON admin_register_pending (expires_at);

-- Ветка регистрации (owner — без анкеты, staff — с анкетой)
ALTER TABLE admin_register_pending ADD COLUMN IF NOT EXISTS key_type TEXT NOT NULL DEFAULT 'staff';
-- Инвайт-токен из admin_invite_tokens, по которому шла регистрация
ALTER TABLE admin_register_pending ADD COLUMN IF NOT EXISTS invite_token TEXT;

-- Admin session security fields
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS session_fingerprint TEXT;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS force_reauth_at TIMESTAMPTZ;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS last_ip TEXT;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;

-- Staff roles / statuses (роли персонала, найм, согласие с правилами, выплаты)
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'applicant';
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS hired_at TIMESTAMPTZ;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS hired_by BIGINT;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS rules_accepted_at TIMESTAMPTZ;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS rules_version INT NOT NULL DEFAULT 1;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS payout_type TEXT;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS payout_details TEXT;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS login_key TEXT;

ALTER TABLE admin_accounts DROP CONSTRAINT IF EXISTS admin_accounts_role_check;
ALTER TABLE admin_accounts ADD CONSTRAINT admin_accounts_role_check
    CHECK (role IN ('owner', 'senior_admin', 'junior_admin', 'moderator', 'applicant', 'suspended'));

ALTER TABLE admin_accounts DROP CONSTRAINT IF EXISTS admin_accounts_status_check;
ALTER TABLE admin_accounts ADD CONSTRAINT admin_accounts_status_check
    CHECK (status IN ('active', 'pending', 'rejected', 'suspended'));

CREATE INDEX IF NOT EXISTS admin_accounts_status_idx ON admin_accounts (status);
CREATE INDEX IF NOT EXISTS admin_accounts_role_idx ON admin_accounts (role);

-- Заявки кандидатов в персонал (анкета при регистрации)
CREATE TABLE IF NOT EXISTS admin_applications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username TEXT,
    first_name TEXT,
    answers JSONB NOT NULL DEFAULT '{}'::jsonb,
    payout_type TEXT,
    payout_details TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    assigned_role TEXT,
    review_note TEXT,
    reviewed_by BIGINT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Один активный (pending) запрос на пользователя — повторно подавать нельзя
CREATE UNIQUE INDEX IF NOT EXISTS admin_applications_one_pending_idx
    ON admin_applications (user_id)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS admin_applications_status_idx
    ON admin_applications (status, created_at DESC);

CREATE INDEX IF NOT EXISTS admin_applications_user_idx
    ON admin_applications (user_id, created_at DESC);

-- Зарплаты персонала (понедельная). Ставит senior/owner, платит owner.
CREATE TABLE IF NOT EXISTS staff_salaries (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    week_start DATE NOT NULL,
    amount INT NOT NULL CHECK (amount >= 0),
    status TEXT NOT NULL DEFAULT 'pending_approval'
        CHECK (status IN ('pending_approval', 'approved', 'paid', 'cancelled')),
    note TEXT,
    set_by BIGINT,
    approved_by BIGINT,
    paid_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS staff_salaries_user_week_idx
    ON staff_salaries (user_id, week_start);
CREATE INDEX IF NOT EXISTS staff_salaries_week_idx
    ON staff_salaries (week_start DESC);

-- Расчётный листок: ставка × коэффициент + бонус − штраф = amount (к выплате)
ALTER TABLE staff_salaries ADD COLUMN IF NOT EXISTS base_amount INT NOT NULL DEFAULT 0;
ALTER TABLE staff_salaries ADD COLUMN IF NOT EXISTS coefficient NUMERIC(5,2) NOT NULL DEFAULT 1.0;
ALTER TABLE staff_salaries ADD COLUMN IF NOT EXISTS bonus INT NOT NULL DEFAULT 0;
ALTER TABLE staff_salaries ADD COLUMN IF NOT EXISTS bonus_reason TEXT;
ALTER TABLE staff_salaries ADD COLUMN IF NOT EXISTS penalty INT NOT NULL DEFAULT 0;
ALTER TABLE staff_salaries ADD COLUMN IF NOT EXISTS penalty_reason TEXT;
ALTER TABLE staff_salaries ADD COLUMN IF NOT EXISTS txid TEXT;
ALTER TABLE staff_salaries ADD COLUMN IF NOT EXISTS payout_proof TEXT;
ALTER TABLE staff_salaries ADD COLUMN IF NOT EXISTS payout_type TEXT NOT NULL DEFAULT 'other';
-- paid_amount для частичных выплат
ALTER TABLE staff_salaries ADD COLUMN IF NOT EXISTS paid_amount INT NOT NULL DEFAULT 0;

-- Частичные выплаты / аванс
ALTER TABLE staff_salaries ADD COLUMN IF NOT EXISTS paid_amount INT NOT NULL DEFAULT 0;
ALTER TABLE staff_salaries DROP CONSTRAINT IF EXISTS staff_salaries_status_check;
ALTER TABLE staff_salaries ADD CONSTRAINT staff_salaries_status_check
    CHECK (status IN ('pending_approval', 'approved', 'partially_paid', 'paid', 'cancelled'));

CREATE TABLE IF NOT EXISTS salary_payments (
    id BIGSERIAL PRIMARY KEY,
    salary_id BIGINT NOT NULL REFERENCES staff_salaries(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    amount INT NOT NULL CHECK (amount > 0),
    method TEXT,
    kind TEXT NOT NULL DEFAULT 'payment' CHECK (kind IN ('payment', 'advance')),
    txid TEXT,
    proof TEXT,
    paid_by BIGINT,
    paid_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS salary_payments_salary_idx ON salary_payments (salary_id);
CREATE INDEX IF NOT EXISTS salary_payments_paid_at_idx ON salary_payments (paid_at DESC);
CREATE INDEX IF NOT EXISTS salary_payments_user_idx ON salary_payments (user_id, paid_at DESC);

-- Активность администраторов (10-минутные слоты присутствия в панели)
CREATE TABLE IF NOT EXISTS admin_activity (
    admin_user_id BIGINT NOT NULL,
    slot TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (admin_user_id, slot)
);

CREATE INDEX IF NOT EXISTS admin_activity_slot_idx ON admin_activity (slot DESC);

-- Куратор сотрудника (старший закреплён за модератором)
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS curator_id BIGINT;

-- История смены должностей
CREATE TABLE IF NOT EXISTS staff_role_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    old_role TEXT,
    new_role TEXT NOT NULL,
    changed_by BIGINT,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS staff_role_history_user_idx
    ON staff_role_history (user_id, created_at DESC);

-- Доступность сотрудника (в отпуске / афк — не требуем активности)
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS availability TEXT NOT NULL DEFAULT 'active';
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS availability_until TIMESTAMPTZ;

-- Заметки о сотрудниках (внутренние, как заметки об игроках)
CREATE TABLE IF NOT EXISTS staff_notes (
    id BIGSERIAL PRIMARY KEY,
    staff_user_id BIGINT NOT NULL,
    author_id BIGINT NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS staff_notes_user_idx ON staff_notes (staff_user_id, created_at DESC);

-- Страйки сотрудников (с истечением — «сгорают» через месяц)
CREATE TABLE IF NOT EXISTS staff_strikes (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    complaint_id BIGINT,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '30 days')
);
CREATE INDEX IF NOT EXISTS staff_strikes_user_idx ON staff_strikes (user_id, expires_at DESC);

-- График смен
CREATE TABLE IF NOT EXISTS staff_shifts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    note TEXT,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS staff_shifts_user_idx ON staff_shifts (user_id, starts_at DESC);
CREATE INDEX IF NOT EXISTS staff_shifts_time_idx ON staff_shifts (starts_at DESC);

-- Шаблоны вопросов анкеты (редактируются из панели)
CREATE TABLE IF NOT EXISTS application_questions (
    id BIGSERIAL PRIMARY KEY,
    qkey TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    qtype TEXT NOT NULL DEFAULT 'text' CHECK (qtype IN ('text', 'textarea')),
    required BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);

-- Ожидающие со-подтверждения крупные выплаты (нужен второй владелец)
CREATE TABLE IF NOT EXISTS pending_payouts (
    id BIGSERIAL PRIMARY KEY,
    salary_id BIGINT NOT NULL REFERENCES staff_salaries(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    amount INT NOT NULL,
    method TEXT,
    kind TEXT NOT NULL DEFAULT 'payment',
    txid TEXT,
    proof TEXT,
    requested_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS pending_payouts_created_idx ON pending_payouts (created_at DESC);

-- Апелляции работников по зарплате
CREATE TABLE IF NOT EXISTS salary_appeals (
    id BIGSERIAL PRIMARY KEY,
    salary_id BIGINT NOT NULL REFERENCES staff_salaries(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    resolution TEXT,
    reviewed_by BIGINT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS salary_appeals_status_idx
    ON salary_appeals (status, created_at DESC);
CREATE INDEX IF NOT EXISTS salary_appeals_salary_idx
    ON salary_appeals (salary_id);

-- Доказательная отчётность: действия сотрудника над игроками (мут/бан + пруфы)
CREATE TABLE IF NOT EXISTS staff_actions (
    id BIGSERIAL PRIMARY KEY,
    admin_user_id BIGINT NOT NULL,
    admin_name TEXT NOT NULL DEFAULT '',
    action_type TEXT NOT NULL,
    target_player_id BIGINT,
    target_name TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '',
    proof_media_id TEXT,
    duration_minutes INT,
    -- Группа, где выдано наказание. 0 => во всех официальных группах / во всём
    -- проекте (охват уточняет столбец scope). Пишется ботом (bot/admins/*).
    chat_id BIGINT,
    -- Охват наказания: 'chat' (одна группа) / 'all' (все офиц. группы) /
    -- 'full' (весь проект). Позволяет архиву различать Бан/Баналл/Банфулл,
    -- Варн/Варналл/Варнфулл, Мут/Муталл, Кик/Кикалл и снятия по охвату.
    scope TEXT,
    -- Токен бота, ПОЛУЧИВШЕГО фото-доказательство. Telegram file_id валиден
    -- только для того бота, который его выдал, поэтому пруфы часто снимаются
    -- «другим ботом» (отдельный бот модерации), чей токен админ-панель не знает.
    -- Сохраняем токен-владельца рядом с file_id, чтобы архив всегда мог скачать
    -- фото именно тем ботом. Используется ТОЛЬКО на сервере (photo-proxy отдаёт
    -- байты), клиенту НИКОГДА не передаётся.
    proof_bot_token TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE staff_actions ADD COLUMN IF NOT EXISTS admin_name TEXT NOT NULL DEFAULT '';
ALTER TABLE staff_actions ADD COLUMN IF NOT EXISTS target_name TEXT NOT NULL DEFAULT '';
ALTER TABLE staff_actions ADD COLUMN IF NOT EXISTS proof_media_id TEXT;
ALTER TABLE staff_actions ADD COLUMN IF NOT EXISTS duration_minutes INT;
ALTER TABLE staff_actions ADD COLUMN IF NOT EXISTS chat_id BIGINT;
ALTER TABLE staff_actions ADD COLUMN IF NOT EXISTS scope TEXT;
ALTER TABLE staff_actions ADD COLUMN IF NOT EXISTS proof_bot_token TEXT;

CREATE INDEX IF NOT EXISTS staff_actions_admin_idx
    ON staff_actions (admin_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS staff_actions_player_idx
    ON staff_actions (target_player_id, created_at DESC);
-- Быстрый поиск токена-владельца по file_id при выдаче пруфа в архиве.
CREATE INDEX IF NOT EXISTS staff_actions_proof_media_idx
    ON staff_actions (proof_media_id)
    WHERE proof_media_id IS NOT NULL;

-- Жалобы на сотрудников (от персонала или от игроков)
CREATE TABLE IF NOT EXISTS staff_complaints (
    id BIGSERIAL PRIMARY KEY,
    target_admin_id BIGINT,
    subject TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'in_progress', 'resolved')),
    evidence TEXT NOT NULL DEFAULT '',
    resolution TEXT,
    source TEXT NOT NULL DEFAULT 'staff',
    complainant_player_id BIGINT,
    created_by BIGINT,
    taken_by BIGINT,
    resolved_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    taken_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ
);

-- Миграция: гарантируем все колонки (на случай старой/расходящейся таблицы),
-- затем делаем target_admin_id необязательным.
ALTER TABLE staff_complaints ADD COLUMN IF NOT EXISTS target_admin_id BIGINT;
ALTER TABLE staff_complaints ADD COLUMN IF NOT EXISTS subject TEXT NOT NULL DEFAULT '';
ALTER TABLE staff_complaints ADD COLUMN IF NOT EXISTS reason TEXT NOT NULL DEFAULT '';
ALTER TABLE staff_complaints ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'open';
ALTER TABLE staff_complaints ADD COLUMN IF NOT EXISTS evidence TEXT NOT NULL DEFAULT '';
ALTER TABLE staff_complaints ADD COLUMN IF NOT EXISTS resolution TEXT;
ALTER TABLE staff_complaints ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'staff';
ALTER TABLE staff_complaints ADD COLUMN IF NOT EXISTS complainant_player_id BIGINT;
ALTER TABLE staff_complaints ADD COLUMN IF NOT EXISTS created_by BIGINT;
ALTER TABLE staff_complaints ADD COLUMN IF NOT EXISTS taken_by BIGINT;
ALTER TABLE staff_complaints ADD COLUMN IF NOT EXISTS resolved_by BIGINT;
ALTER TABLE staff_complaints ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE staff_complaints ADD COLUMN IF NOT EXISTS taken_at TIMESTAMPTZ;
ALTER TABLE staff_complaints ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;
ALTER TABLE staff_complaints ALTER COLUMN target_admin_id DROP NOT NULL;

CREATE INDEX IF NOT EXISTS staff_complaints_status_idx
    ON staff_complaints (status, created_at DESC);
CREATE INDEX IF NOT EXISTS staff_complaints_target_idx
    ON staff_complaints (target_admin_id, status);

-- Admin action audit log (separate from game audit_events)
CREATE TABLE IF NOT EXISTS admin_audit_log (
    id BIGSERIAL PRIMARY KEY,
    admin_user_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    target_label TEXT,
    details JSONB NOT NULL DEFAULT '{}',
    ip TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS admin_audit_log_time_idx ON admin_audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS admin_audit_log_admin_idx ON admin_audit_log (admin_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS admin_audit_log_action_idx ON admin_audit_log (action, created_at DESC);

-- IP bans
CREATE TABLE IF NOT EXISTS ip_bans (
    id BIGSERIAL PRIMARY KEY,
    ip_or_cidr TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    banned_by BIGINT NOT NULL,
    banned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS ip_bans_active_idx ON ip_bans (active, ip_or_cidr);

-- Онлайн: последняя активность игрока
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS users_last_seen_idx
    ON users (last_seen_at DESC)
    WHERE last_seen_at IS NOT NULL;

-- Кулдаун ежедневной ротации напоминалок (server/admin_broadcast.py::start_daily_rotation_broadcast)
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_daily_broadcast_sent_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS users_last_daily_broadcast_idx
    ON users (last_daily_broadcast_sent_at)
    WHERE last_daily_broadcast_sent_at IS NOT NULL;

-- Регистрация и клиентские данные WebApp
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_client_ip TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_user_agent TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_platform TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_app_version TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_language_code TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium BOOLEAN;
ALTER TABLE users ADD COLUMN IF NOT EXISTS client_info JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS client_info_updated_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS user_login_events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    client_ip TEXT,
    user_agent TEXT,
    platform TEXT,
    device_model TEXT,
    app_version TEXT,
    language_code TEXT,
    is_premium BOOLEAN,
    screen_width INT,
    screen_height INT,
    timezone TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS user_login_events_user_idx
    ON user_login_events (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS online_snapshots (
    id BIGSERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    online_count INT NOT NULL CHECK (online_count >= 0)
);

CREATE INDEX IF NOT EXISTS online_snapshots_recorded_idx
    ON online_snapshots (recorded_at DESC);

CREATE TABLE IF NOT EXISTS online_daily_stats (
    stat_date DATE PRIMARY KEY,
    peak_online INT NOT NULL DEFAULT 0,
    peak_at TIMESTAMPTZ
);

-- Бан игроков (admin panel)
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_reason TEXT;

CREATE INDEX IF NOT EXISTS users_not_banned_idx
    ON users (user_id)
    WHERE banned = FALSE;

-- Рассылки (admin panel)
CREATE TABLE IF NOT EXISTS broadcast_templates (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    telegram_text TEXT NOT NULL DEFAULT '',
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS broadcast_runs (
    id BIGSERIAL PRIMARY KEY,
    admin_user_id BIGINT NOT NULL,
    audience TEXT NOT NULL,
    filter_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    channels_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    telegram_text TEXT NOT NULL DEFAULT '',
    template_key TEXT,
    recipient_count INT NOT NULL DEFAULT 0,
    webapp_sent INT NOT NULL DEFAULT 0,
    telegram_sent INT NOT NULL DEFAULT 0,
    telegram_failed INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS broadcast_runs_created_idx
    ON broadcast_runs (created_at DESC);

-- Scheduled broadcasts
ALTER TABLE broadcast_runs ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ;
ALTER TABLE broadcast_runs ADD COLUMN IF NOT EXISTS label TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS broadcast_runs_scheduled_idx
    ON broadcast_runs (scheduled_at) WHERE status = 'scheduled';

-- CTA-кнопка рассылки (web_app-кнопка "Открыть ферму" и т.п.)
ALTER TABLE broadcast_runs ADD COLUMN IF NOT EXISTS cta_text TEXT;
ALTER TABLE broadcast_runs ADD COLUMN IF NOT EXISTS cta_url TEXT;

-- Ежедневная ротация "напоминалок" (server/event_scheduler.py::_fire_daily_rotation_broadcast)
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS daily_broadcast_enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS daily_broadcast_hour SMALLINT NOT NULL DEFAULT 12;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS daily_broadcast_minute SMALLINT NOT NULL DEFAULT 0;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS daily_broadcast_rotation_index SMALLINT NOT NULL DEFAULT 0;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS daily_broadcast_next_fire_at TIMESTAMPTZ;
-- Не всем сразу и не каждый день одному и тому же игроку: кулдаун + случайная выборка
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS daily_broadcast_cooldown_days SMALLINT NOT NULL DEFAULT 2;
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS daily_broadcast_sample_rate REAL NOT NULL DEFAULT 0.5;

-- Помечает запуск как ежедневную ротацию, чтобы _execute_broadcast обновлял
-- users.last_daily_broadcast_sent_at только для неё, а не для ручных рассылок админа.
ALTER TABLE broadcast_runs ADD COLUMN IF NOT EXISTS is_daily_rotation BOOLEAN NOT NULL DEFAULT FALSE;

-- Разбивка причин недоставки Telegram-сообщений при рассылке, например
-- {"blocked": 3, "chat_not_found": 12, "other": 1}. См. server/telegram_notify.py::_classify_error.
ALTER TABLE broadcast_runs ADD COLUMN IF NOT EXISTS telegram_failed_reasons JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Кому конкретно ушла рассылка (по каналам) - для просмотра в админке "кому отправило".
-- status: 'sent' | 'failed'. fail_reason заполнен только для status='failed'
-- (см. server/telegram_notify.py::_classify_error для telegram-каналов).
-- Без FK на broadcast_runs(id) намеренно: в проде на момент миграции у broadcast_runs
-- не нашлось подходящего unique/primary key constraint (см. инцидент 2026-07-15,
-- CREATE TABLE падал с InvalidForeignKeyError и ронял старт всего api). run_id всегда
-- пишется программно из admin_broadcast.py, так что ссылочная целостность гарантируется
-- на уровне приложения, а не FK.
CREATE TABLE IF NOT EXISTS broadcast_recipients (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    fail_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS broadcast_recipients_run_idx
    ON broadcast_recipients (run_id, id);

CREATE INDEX IF NOT EXISTS broadcast_recipients_run_status_idx
    ON broadcast_recipients (run_id, status);

-- Какой именно из шаблонов ежедневной ротации достался ЭТОМУ игроку (при
-- is_daily_rotation - у каждого получателя текст выбирается персонально, см.
-- admin_broadcast.py::pick_daily_template). NULL для обычных ручных рассылок.
ALTER TABLE broadcast_recipients ADD COLUMN IF NOT EXISTS template_label TEXT;

-- Security / API errors (дублируют Telegram error topic)
CREATE TABLE IF NOT EXISTS system_logs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    category TEXT NOT NULL,
    code TEXT NOT NULL,
    user_id BIGINT,
    method TEXT,
    path TEXT,
    status INT,
    message TEXT,
    source TEXT,
    client_ip TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS system_logs_created_idx
    ON system_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS system_logs_category_idx
    ON system_logs (category, created_at DESC);

CREATE INDEX IF NOT EXISTS system_logs_user_idx
    ON system_logs (user_id, created_at DESC)
    WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS system_logs_code_idx
    ON system_logs (code);

CREATE INDEX IF NOT EXISTS audit_events_type_idx
    ON audit_events (event_type, created_at DESC);

CREATE INDEX IF NOT EXISTS game_events_quest_type_time_idx
    ON game_events (event_type, created_at DESC)
    WHERE event_type IN ('quest_accept', 'quest_complete');

CREATE INDEX IF NOT EXISTS game_events_user_quest_complete_idx
    ON game_events (user_id, (details->>'quest_id'), created_at)
    WHERE event_type = 'quest_complete';

-- Балансы чатов (чёрный рынок и другие групповые кошельки)
CREATE TABLE IF NOT EXISTS chat (
    chat_id BIGINT PRIMARY KEY,
    chatbalance BIGINT NOT NULL DEFAULT 0,
    dexbalance BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Начальная строка для технического чата (чёрный рынок)
INSERT INTO chat (chat_id, chatbalance, dexbalance)
SELECT -1003855337972, 0, 0
WHERE NOT EXISTS (SELECT 1 FROM chat WHERE chat_id = -1003855337972);

-- В проде эта таблица уже содержит namechat (название группы) - её завёл
-- старый bot/db_create/db.py. Здесь - только для чистых/тестовых БД, где
-- chat создаётся впервые этим файлом (CREATE TABLE выше её не потрогает).
-- Используется в admin-панели для выбора группы по имени в "Постах в группы"
-- (server/group_posts.py::list_known_chats).
ALTER TABLE chat ADD COLUMN IF NOT EXISTS namechat TEXT;

-- Логи взносов в чёрный рынок от покупок в магазине
CREATE TABLE IF NOT EXISTS black_market_shop_deposits (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    source_chat_id BIGINT,
    target_chat_id BIGINT NOT NULL,
    amount BIGINT NOT NULL CHECK (amount > 0),
    note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bm_shop_deposits_user_created
    ON black_market_shop_deposits (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_bm_shop_deposits_target_created
    ON black_market_shop_deposits (target_chat_id, created_at DESC);

-- Апелляции банов игроков
CREATE TABLE IF NOT EXISTS ban_appeals (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username TEXT,
    first_name TEXT,
    ban_reason TEXT,
    appeal_text TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'taken', 'approved', 'rejected')),
    taken_by BIGINT,
    taken_at TIMESTAMPTZ,
    resolved_by BIGINT,
    resolved_at TIMESTAMPTZ,
    resolution TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ban_appeals_one_pending_idx
    ON ban_appeals (user_id)
    WHERE status IN ('pending', 'taken');

CREATE INDEX IF NOT EXISTS ban_appeals_status_idx
    ON ban_appeals (status, created_at DESC);

CREATE INDEX IF NOT EXISTS ban_appeals_user_idx
    ON ban_appeals (user_id, created_at DESC);

-- Сообщения в апелляциях банов (переписка игрока с администратором)
CREATE TABLE IF NOT EXISTS ban_appeal_messages (
    id BIGSERIAL PRIMARY KEY,
    appeal_id BIGINT NOT NULL REFERENCES ban_appeals(id) ON DELETE CASCADE,
    from_user BOOLEAN NOT NULL,
    admin_id BIGINT,
    admin_name TEXT,
    text TEXT NOT NULL DEFAULT '',
    photo_file_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ban_appeal_messages_appeal_idx
    ON ban_appeal_messages (appeal_id, created_at ASC);

-- Циклические посты в группы (см. docs/superpowers/specs/2026-07-15-group-post-campaigns-design.md).
-- Без FK на существующие таблицы намеренно — см. broadcast_recipients выше и
-- инцидент 2026-07-15 (InvalidForeignKeyError уронил старт всего api).
CREATE TABLE IF NOT EXISTS group_post_campaigns (
    id BIGSERIAL PRIMARY KEY,
    admin_user_id BIGINT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    chat_ids BIGINT[] NOT NULL,
    telegram_text TEXT NOT NULL DEFAULT '',
    photo_bytes BYTEA,
    photo_mime TEXT,
    photo_file_id TEXT,
    buttons_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    interval_minutes INT NOT NULL CHECK (interval_minutes >= 1),
    status TEXT NOT NULL DEFAULT 'active',
    next_fire_at TIMESTAMPTZ,
    total_sent INT NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS group_post_campaigns_active_idx
    ON group_post_campaigns (next_fire_at) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS group_post_log (
    id BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    status TEXT NOT NULL,
    fail_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS group_post_log_campaign_idx
    ON group_post_log (campaign_id, id);

CREATE TABLE IF NOT EXISTS giveaways (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    emoji TEXT NOT NULL DEFAULT '🎁',
    rarity TEXT NOT NULL CHECK (rarity IN ('common', 'rare', 'legendary')),
    prize_type TEXT NOT NULL CHECK (prize_type IN ('kut', 'manual')),
    prize_kut_amount INT,
    prize_title TEXT,
    prize_emoji TEXT,
    prize_description TEXT,
    draw_type TEXT NOT NULL CHECK (draw_type IN ('timer', 'instant')),
    ends_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
    winner_user_id BIGINT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    drawn_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS giveaway_conditions (
    id SERIAL PRIMARY KEY,
    giveaway_id INT NOT NULL REFERENCES giveaways(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('balance', 'harvest_count', 'item_count')),
    target_value INT NOT NULL CHECK (target_value >= 1),
    item_id TEXT,
    sort_order INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS giveaway_entries (
    giveaway_id INT NOT NULL REFERENCES giveaways(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (giveaway_id, user_id)
);
