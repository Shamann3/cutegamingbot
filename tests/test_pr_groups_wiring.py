from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_wired_into_bot_and_panel():
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "attach_pr_groups" in main
    assert "prg:hub" in main
    assert "_pr_wait_photo_filter" in main
    assert "looks_like_confirm" in main
    assert "Пиар в группах" in main

    access = (ROOT / "server" / "panel_access.py").read_text(encoding="utf-8")
    assert "prGroups" in access

    routes = (ROOT / "server" / "admin_routes.py").read_text(encoding="utf-8")
    assert "pr_groups_router" in routes

    shell = (ROOT / "admin" / "src" / "pages" / "PanelShell.jsx").read_text(encoding="utf-8")
    assert "PrGroupsSection" in shell
    assert "isPrGroups" in shell


def test_gift_lock_hooks_exist():
    transfer = (ROOT / "bot" / "db_create" / "db.py").read_text(encoding="utf-8")
    assert "gift_blocks_other_spend" in transfer
    gbl = (ROOT / "bot" / "funcs" / "group_balance_level.py").read_text(encoding="utf-8")
    assert "maybe_grant_gift" in gbl
    chat = (ROOT / "bot" / "handlers" / "chatbalance.py").read_text(encoding="utf-8")
    assert "seed_lock_for_chat" in chat
    fund = (ROOT / "bot" / "funcs" / "growth_fund.py").read_text(encoding="utf-8")
    assert "note_commission" in fund
    assert "source_chat_id" in fund
    core = (ROOT / "bot" / "funcs" / "pr_groups.py").read_text(encoding="utf-8")
    assert "fulfill_accept" in core
    assert "seed_applied" in core
    assert "before_ts" in core
    assert "gift_claw_active" in core
    bal = (ROOT / "bot" / "db_create" / "db.py").read_text(encoding="utf-8")
    assert "gift_claw_active" in bal
    handlers = (ROOT / "bot" / "handlers" / "pr_groups.py").read_text(encoding="utf-8")
    assert "start_pr_ticker" in handlers
    assert "confirm_token" in handlers
    assert "text_not_creator" in handlers
    admin = (ROOT / "server" / "admin_pr_groups.py").read_text(encoding="utf-8")
    assert "CLAIM_COLUMNS" in admin
    assert "alreadyKnown" in admin
    ui = (ROOT / "admin" / "src" / "pages" / "sections" / "PrGroupsSection.jsx").read_text(encoding="utf-8")
    assert "previewSplit" in ui
    assert "overBudget" in ui
