-- Дата первого /start для окна обучающих подсказок новичка (2 суток).
-- Выполнить на cutebase (test) и/или cutedatabase (main).

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS bot_first_start_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_users_bot_first_start_at
  ON users (bot_first_start_at)
  WHERE bot_first_start_at IS NOT NULL;
