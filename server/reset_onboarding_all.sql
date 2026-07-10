-- Сброс обучения для всех пользователей (pgAdmin / Railway SQL)
UPDATE users
SET onboarding_done = FALSE,
    onboarding_active = FALSE,
    onboarding_seed_granted = 0,
    onboarding_demo_logs = 0,
    onboarding_step = 0;

-- Очистить учебную грядку №1 у всех
UPDATE farm_plots
SET status = 'EMPTY',
    planted_at = NULL,
    ripe_at = NULL,
    dry_at = NULL,
    needs_water = FALSE,
    wilt_at = NULL,
    waters_remaining = 0
WHERE plot_id = 1;
