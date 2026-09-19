from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _read(*parts: str) -> str:
    return (_ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_copy_guard_blocks_everything_except_ids():
    main = _read("admin", "src", "main.jsx")
    assert "installPanelCopyGuard" in main
    assert "no-copy.css" in main

    css = _read("admin", "src", "styles", "no-copy.css")
    assert "user-select: none !important" in css
    assert "[data-copyable]" in css
    assert "user-select: text !important" in css

    guard = _read("admin", "src", "lib", "guardPanelCopy.js")
    assert "onCopyCut" in guard
    assert "contextmenu" in guard
    assert "isCopyableNode" in guard
    assert "isTextEntryEvent" in guard

    copyable = _read("admin", "src", "components", "Copyable.jsx")
    assert 'data-copyable="1"' in copyable
    assert "export function CopyableId" in copyable
    assert "export function CopyableUsername" in copyable
    assert "export function IdentityBits" in copyable


def test_user_and_group_ids_are_copyable():
    users = _read("admin", "src", "pages", "sections", "UsersSection.jsx")
    groups = _read("admin", "src", "pages", "sections", "GroupsStudioSection.jsx")
    nika = _read("admin", "src", "pages", "sections", "NikaSection.jsx")
    games = _read("admin", "src", "pages", "sections", "GamesSection.jsx")
    farm = _read("admin", "src", "pages", "sections", "FarmSection.jsx")
    logs = _read("admin", "src", "pages", "sections", "LogsSection.jsx")
    posts = _read("admin", "src", "pages", "sections", "GroupPostsPanel.jsx")

    assert "IdentityBits" in users
    assert "CopyableId" in users
    assert "CopyableUsername" in users
    assert "grp-page nika-page users-page" in users
    assert "nika-seg" in users
    assert "useIsPhone" in users
    assert "users-search-actions" in users
    assert "users-search-input" in users
    assert "id группы" in users or "chatUsername" in users

    assert "IdentityBits" in groups
    assert 'label="id группы"' in groups
    assert "CopyableUsername" in groups

    assert "CopyableId" in nika
    prg = _read("admin", "src", "pages", "sections", "PrGroupsSection.jsx")
    assert "CopyableId" in prg
    assert "Пиар в группах" in prg
    assert "id группы" in prg
    assert "Тихий долив" in prg
    nav = _read("admin", "src", "constants", "panelNav.js")
    assert "prGroups" in nav
    assert "Пиар в группах" in nav
    assert "CopyableUsername" in nika
    assert "id группы" in nika
    assert "Сбор лишнего" in nika
    assert "sweep_speed" in nika
    assert "Мгновенно" in nika
    assert "t.me/" in nika
    assert "SweepSpeedPicker" in nika
    assert "now_sweep" in nika
    assert "Снять" in nika
    nika_css = _read("admin", "src", "styles", "nika.css")
    assert "border-radius: 10px !important" in nika_css
    assert "border-radius: 999px !important" not in nika_css
    assert "elite-support-btn" in _read("admin", "src", "components", "EliteTopbar.jsx")

    assert "CopyableId" in games
    assert "IdentityBits" in farm
    assert "CopyableId" in logs
    assert 'label="id группы"' in posts

    app = _read("src", "App.jsx")
    assert "FarmEntrance" not in app
    css = _read("admin", "src", "styles", "users-nika.css")
    assert "users-page" in css
    assert "html.is-phone" in css
    assert "max-height: 48px" in css

    main = _read("admin", "src", "main.jsx")
    assert "phone-thumb.css" in main
    thumb = _read("admin", "src", "styles", "phone-thumb.css")
    assert "panel-thumb-dock" in thumb
    assert "display: none !important" in thumb
    assert "elite-support-btn" in thumb
    assert "overflow-y: auto" in thumb
    assert "e-invert-bg" in thumb
    assert "e-invert-text" in thumb
    assert "overscroll-behavior-y: auto" in thumb
    for needle in (
        "panel-economy",
        "panel-market",
        "panel-farm",
        "support-section",
        "staff-section",
        "tt-page",
        "bq-root",
        "ach-page",
        "gm-page",
        "analytics-section",
        "admin-modal-actions",
        "support-reply-send-btn",
    ):
        assert needle in thumb, needle

    shell = _read("admin", "src", "pages", "PanelShell.jsx")
    assert "panel-thumb-dock" not in shell
    assert "panel-thumb-menu" not in shell
    topbar = _read("admin", "src", "components", "EliteTopbar.jsx")
    assert "elite-support-btn" in topbar
    assert "Поддержка" in topbar
    assert topbar.index("elite-support-btn") < topbar.index("elite-menu-btn")

    farm_main = _read("src", "main.jsx")
    assert "farm-thumb.css" in farm_main
    farm_css = _read("src", "styles", "farm-thumb.css")
    for needle in (
        "trade-module",
        "shop-exchange",
        "market-exchange",
        "quests-module",
        "profile-shell",
        "settings-module",
        "craft-module",
        "inventory-module",
        "quests-action-btn--claim",
        "craft-action-btn",
        "shop-sheet-switch",
    ):
        assert needle in farm_css, needle
    tabs = _read("src", "components", "TabBar.jsx")
    assert tabs.index("{ id: 'farm', label: 'Ферма' }") > tabs.index("{ id: 'quests', label: 'Задания' }")
    swipe = _read("src", "hooks", "useSwipeTabs.js")
    assert "['quests', 'trade', 'profile', 'farm']" in swipe
