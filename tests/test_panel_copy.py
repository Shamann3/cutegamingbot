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
    assert "id группы" in users or "chatUsername" in users

    assert "IdentityBits" in groups
    assert 'label="id группы"' in groups
    assert "CopyableUsername" in groups

    assert "CopyableId" in nika
    assert "CopyableUsername" in nika
    assert "id группы" in nika

    assert "CopyableId" in games
    assert "IdentityBits" in farm
    assert "CopyableId" in logs
    assert 'label="id группы"' in posts

    app = _read("src", "App.jsx")
    assert "FarmEntrance" not in app
    css = _read("admin", "src", "styles", "users-nika.css")
    assert "users-page" in css
    assert "html.is-phone" in css
