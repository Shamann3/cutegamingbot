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
    assert "!isPrGroups" in shell
    core = (ROOT / "bot" / "funcs" / "pr_groups.py").read_text(encoding="utf-8")
    assert "prg:chk" in core
    assert "prg:undo" in core
    assert "how_keyboard" in core
    assert "photo_keyboard" in core
    assert "image_file_id" in core
    assert "pop_photo" in core
    handlers = (ROOT / "bot" / "handlers" / "pr_groups.py").read_text(encoding="utf-8")
    assert "on_undo" in handlers
    assert "looks_like_help" in handlers
    assert "_album_used" in handlers
    assert "_resume_claim_screen" in handlers


def test_image_file_id_accepts_photo_and_png():
    from types import SimpleNamespace

    from bot.funcs.pr_groups import image_file_id, photo_noise_kind

    photo = SimpleNamespace(
        photo=[SimpleNamespace(file_id="p1")],
        document=None, video=None, video_note=None, sticker=None, animation=None, text=None,
    )
    assert image_file_id(photo) == "p1"
    doc = SimpleNamespace(
        photo=None,
        document=SimpleNamespace(file_id="d1", mime_type="image/png", file_name="a.png"),
        video=None, video_note=None, sticker=None, animation=None, text=None,
    )
    assert image_file_id(doc) == "d1"
    noise = SimpleNamespace(
        photo=None, document=None, video=SimpleNamespace(file_id="v"),
        video_note=None, sticker=None, animation=None, text=None,
    )
    assert image_file_id(noise) == ""
    assert photo_noise_kind(noise) == "video"


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
