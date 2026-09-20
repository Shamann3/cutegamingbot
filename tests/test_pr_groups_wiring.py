from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_wired_into_bot_and_panel():
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "attach_pr_groups" in main
    assert "prg:hub" in main
    assert "_pr_wait_photo_filter" in main
    assert "_pr_wait_link_filter" in main
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
    assert "choose_keyboard" in core
    assert "Я владелец группы" in core
    assert "Я рекомендую бот в группах" in core
    assert "startgroup" in core
    assert "is_waiting_link" in core
    assert "photo_keyboard" in core
    assert "image_file_id" in core
    assert "pop_photo" in core
    assert "prg:n:" in core
    assert "card_keyboard" in core
    assert "Сдать ещё группу" in core
    assert "Заработки" in core
    assert "Мои группы" in core
    assert "Назад, в главное меню" in core
    handlers = (ROOT / "bot" / "handlers" / "pr_groups.py").read_text(encoding="utf-8")
    assert "on_undo" in handlers
    assert "looks_like_help" in handlers
    assert "_album_used" in handlers
    assert "_resume_claim_screen" in handlers
    assert "on_wait_link" in handlers
    assert "_resolve_group_and_begin" in handlers
    assert "prg:cant" in (ROOT / "bot" / "funcs" / "pr_groups.py").read_text(encoding="utf-8")
    assert "_begin_proofs" in handlers
    assert "on_cant_add" in handlers
    assert "text_choose_role" in handlers
    assert "_show_mine" in handlers
    assert "_show_card" in handlers
    assert "text_earnings" in handlers
    assert "text_group_card" in handlers
    assert "on_continue_claim" in handlers
    assert "text_after_proofs_reco" in handlers
    assert "text_forward_no_group" in handlers
    assert "extract_group_ref" in handlers
    assert "_forwarded_group" not in handlers
    assert "chat_id_from_ref" in handlers
    assert "questions_stars" in core
    assert "PR_TASKS" in core


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


def _kb_texts(markup) -> list[str]:
    return [btn.text for row in markup.inline_keyboard for btn in row]


def _kb_datas(markup) -> list[str]:
    return [getattr(btn, "callback_data", None) or "" for row in markup.inline_keyboard for btn in row]


def test_every_pr_screen_has_back():
    from bot.funcs import pr_groups as pr

    screens = [
        pr.entry_keyboard(),
        pr.entry_keyboard(mine=True),
        pr.choose_keyboard(),
        pr.how_keyboard(),
        pr.how_keyboard(intent=pr.ROLE_RECO, no_public=True, no_admin=True),
        pr.how_public_keyboard(),
        pr.how_admin_keyboard(intent=pr.ROLE_RECO),
        pr.add_group_keyboard(),
        pr.add_group_keyboard(intent=pr.ROLE_RECO),
        pr.cant_add_keyboard(),
        pr.switch_to_reco_keyboard(),
        pr.switch_to_owner_keyboard(),
        pr.role_keyboard(),
        pr.groups_keyboard([{"title": "g", "chat_id": 1}]),
        pr.photo_keyboard(0),
        pr.photo_keyboard(2),
        pr.hub_only_keyboard(),
        pr.after_cancel_keyboard(),
        pr.after_owner_keyboard(),
        pr.after_reco_keyboard("x"),
        pr.after_reco_keyboard(""),
        pr.joined_keyboard(),
        pr.pending_keyboard(),
        pr.mine_keyboard([]),
        pr.mine_keyboard([{"id": 1, "chat_title": "a", "status": "pending", "role": "reco"}]),
        pr.mine_keyboard(
            [{"id": 1, "chat_title": "a", "status": "live", "role": "reco", "paid_kut": 12}],
            live=True,
        ),
        pr.card_keyboard({"id": 1, "status": "photos", "chat_username": "x"}),
        pr.card_keyboard({"id": 2, "status": "live"}),
        pr.resume_keyboard("pending"),
        pr.resume_keyboard("photos"),
        pr.resume_keyboard("wait_confirm"),
    ]
    for kb in screens:
        texts = _kb_texts(kb)
        assert texts[-1].startswith("Назад"), texts
    entry = pr.entry_keyboard()
    entry_texts = _kb_texts(entry)
    assert "Я владелец группы" in entry_texts
    assert "Я рекомендую бот в группах" in entry_texts
    assert "Начать" not in entry_texts
    assert "Заработки" not in entry_texts
    assert "Мои группы" not in entry_texts
    pending_hub = _kb_texts(pr.entry_keyboard(mine=True))
    assert "Мои группы" in pending_hub
    assert "Заработки" not in pending_hub
    live_hub = _kb_texts(pr.entry_keyboard(mine=True, live=True))
    assert "Заработки" in live_hub
    assert "Мои группы" not in live_hub
    assert pr.PR_TASKS in _kb_datas(entry)
    assert pr.PR_TASKS == "questions_stars"
    photo = pr.photo_keyboard(2)
    assert "Другое фото" in _kb_texts(photo)
    assert any(text.startswith("Назад") for text in _kb_texts(photo))
    after = _kb_texts(pr.after_owner_keyboard())
    assert "Мои группы" in after
    mine = _kb_texts(pr.mine_keyboard([{"id": 1, "chat_title": "Друзья", "status": "live", "role": "reco", "paid_kut": 9}]))
    assert "Сдать ещё группу" in mine
    assert any("Друзья" in text for text in mine)


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
    assert "стол" not in ui.lower()
    assert "баланс чата" in ui
    assert "баланс группы" in ui
    logic = (ROOT / "server" / "pr_groups_logic.py").read_text(encoding="utf-8")
    assert "стол" not in logic.lower()
    assert "стол" not in core.lower()
    assert "стол" not in handlers.lower()
