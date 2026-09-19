from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _read(*parts: str) -> str:
    return (_ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_normalize_and_preview():
    import sys

    sys.path.insert(0, str(_ROOT / "server"))
    from game_desk.catalog import default_payload, game_meta
    from game_desk.store import merge_payload, normalize_payload, _payload_needs_seed

    def _preview(settings, game_key, pot, level):
        comm = settings.get("commission") or {}
        if not comm.get("enabled"):
            return {"commission": 0}
        game = (settings.get("games") or {}).get(game_key) or {}
        rate = float((comm.get("rateByLevel") or {}).get(str(level), 0)) * float(game.get("commissionMult") or 0)
        return {"commission": int(pot * max(0.0, min(1.0, rate)))}

    raw = default_payload()
    clean = normalize_payload(raw)
    assert clean["commission"]["enabled"] is True
    assert clean["games"]["words"]["commissionMult"] == 0.0
    assert clean["games"]["slots"]["minBet"] == 2
    assert clean["games"]["soccer"]["params"]["badShotChance"] == 0.08
    assert clean["games"]["slots"]["params"]["tripleSeven"] == 2.5
    assert clean["games"]["risk"]["params"]["homeChance"] == 0.15
    assert clean["games"]["kosti"]["params"]["maxPlayers"] == 12
    assert clean["games"]["scah"]["params"]["turnRest"] == 2.2
    assert clean["games"]["slots"]["maintenance"] is False

    nxt = merge_payload(clean, {
        "games": {
            "slots": {
                "enabled": False,
                "maintenance": True,
                "minBet": 15,
                "commissionMult": 0,
                "params": {"jamChance": 0.2, "tripleSeven": 4},
            }
        }
    })
    assert nxt["games"]["slots"]["enabled"] is False
    assert nxt["games"]["slots"]["maintenance"] is True
    assert nxt["games"]["slots"]["minBet"] == 15
    assert nxt["games"]["slots"]["commissionMult"] == 0.0
    assert nxt["games"]["slots"]["params"]["jamChance"] == 0.2
    assert nxt["games"]["slots"]["params"]["tripleSeven"] == 4
    assert nxt["games"]["kube"]["minBet"] == clean["games"]["kube"]["minBet"]
    assert nxt["games"]["kube"]["maintenance"] is False

    seeded = normalize_payload({})
    assert seeded["games"]["slots"]["minBet"] == clean["games"]["slots"]["minBet"]
    assert seeded["games"]["scah"]["params"]["turnRest"] == clean["games"]["scah"]["params"]["turnRest"]
    assert _payload_needs_seed({}, seeded) is True
    assert _payload_needs_seed(seeded, seeded) is False

    off = _preview(nxt, "slots", 100, 3)
    assert off["commission"] == 0
    on = _preview(clean, "kube", 100, 0)
    assert on["commission"] > 0
    assert game_meta("fortuna")["key"] == "fortuna_solo"
    listed = {
        "scah", "memory", "bingo", "fortuna_lobby", "kosti", "duel", "orel",
        "knb", "mines", "tic_tac_toe", "tank", "risk", "plate", "bombs",
        "trade", "balls", "provoda", "slots", "basket", "soccer", "bowling",
        "darts", "kube", "fortuna_solo",
    }
    from game_desk.catalog import GAME_BY_KEY
    assert listed <= set(GAME_BY_KEY)
    assert any(f["key"] == "homeChance" for f in GAME_BY_KEY["risk"]["fields"])
    assert any(f["key"] == "tripleSeven" for f in GAME_BY_KEY["slots"]["fields"])


def test_panel_games_is_creator_only():
    nav = _read("admin", "src", "constants", "panelNav.js")
    assert "id: 'games'" in nav
    assert "labelRu: 'Игры'" in nav
    assert nav.index("id: 'games'") > 0
    access = _read("server", "panel_access.py")
    assert '"id": "games"' in access
    assert "creatorOnly" in access
    routes = _read("server", "admin_routes.py")
    assert '"/games/overview"' in routes
    assert '"/games/settings"' in routes
    assert "_require_project_creator(admin_id)" in routes
    shell = _read("admin", "src", "pages", "PanelShell.jsx")
    assert "GamesSection" in shell
    assert "isGames && isProjectCreator" in shell
    section = _read("admin", "src", "pages", "sections", "GamesSection.jsx")
    assert "grp-page nika-page gm-page" in section
    assert "Только создатель" in section
    assert "GameAnalytics" in section
    assert "NikaMoneyChart" in section
    assert "maintenance" in section
    assert "Copyable" in section
    assert "gm-hero" not in section
    assert "gm-motif-" not in section
    assert "is-dirty" not in section
    css = _read("admin", "src", "styles", "games.css")
    assert "minmax(min(16.4rem, 100%), 1fr)" in css
    assert "grid-template-columns: 1fr" in css
    assert "border-radius: 8px" in css
    assert "position: static" in css
    assert "gm-motif-" not in css
    assert "repeating-linear-gradient" not in css
    bot_live = _read("bot", "runtime", "game_desk", "live.py")
    assert "reject_desk" in bot_live
    assert "is_maintenance" in bot_live
    assert "5462921117423384478" in bot_live
    assert "В этой игре проводят технические работы" in bot_live
    assert "Тех работы" in bot_live
    assert "render_gamehelp" in bot_live
    help_py = _read("bot", "funcs", "help.py")
    assert "_live_gamehelp" in help_py
    assert "await _live_gamehelp()" in help_py
    growth = _read("bot", "funcs", "growth_fund.py")
    assert "desk.commission_on" in growth
    group = _read("bot", "games", "group_only.py")
    assert "reject_desk" in group
    soccer = _read("bot", "tggames", "soccer.py")
    assert 'param_decimal("soccer", "badShotChance"' in soccer
    slots = _read("bot", "tggames", "slots.py")
    assert "_live_slots_multipliers" in slots
    tank = _read("bot", "games", "tank.py")
    assert "_live_tank_step" in tank
    risk = _read("bot", "games", "risk.py")
    assert "_live_risk_home" in risk
    bombs = _read("bot", "games", "bombs.py")
    assert "_live_bomb_count" in bombs
    provoda = _read("bot", "games", "provoda.py")
    assert "_live_wires_payout" in provoda
    fortuna = _read("bot", "games", "Fortuna.py")
    assert "_live_fortuna_range" in fortuna
    kosti = _read("bot", "funcs", "kosti.py")
    assert "_live_kosti_max" in kosti
    bot_cat = _read("bot", "runtime", "game_desk", "catalog.py")
    api_cat = _read("server", "game_desk", "catalog.py")
    assert '"scah"' in bot_cat and '"scah"' in api_cat
    assert "tripleSeven" in bot_cat and "tripleSeven" in api_cat
    assert "homeChance" in bot_cat and "homeChance" in api_cat
    assert "maintenance" in bot_cat and "maintenance" in api_cat
    admin = _read("server", "admin_games.py")
    assert "_load_series" in admin
    assert "dayExtrema" in admin
    sr = _read("bot", "funcs", "soft_restart.py")
    assert "_hydrate_from_bridge" in sr
    assert "hydrate first" in sr
    assert "_bridge_push_config()" in sr
    captcha = _read("bot", "handlers", "group_captcha.py")
    assert "_prompt_safe" in captcha
    assert "timeout=1.4" in captcha
    gate = _read("bot", "funcs", "group_captcha.py")
    assert "captcha user_needs timeout" in gate
    assert "_mark_fail_open" in gate
    assert "await maybe_prompt_captcha" in captcha
    assert "wait_for(maybe_prompt_captcha" not in captcha


def test_help_maintenance_marks_every_listed_game():
    import sys

    sys.path.insert(0, str(_ROOT / "bot"))
    from runtime.game_desk.live import HELP_TITLES, MAINT_HELP_HTML, apply_help_maintenance

    help_src = _read("bot", "funcs", "help.py")
    start = help_src.index("gamehelp = f'''")
    end = help_src.index("'''", start + 20)
    body = help_src[start:end]
    for title in HELP_TITLES.values():
        assert f" {title}\n" in body, title
    down = {key: True for key in HELP_TITLES}
    marked = apply_help_maintenance(body, down)
    assert marked.count(MAINT_HELP_HTML) == len(HELP_TITLES)
    once = apply_help_maintenance(marked, down)
    assert once.count(MAINT_HELP_HTML) == len(HELP_TITLES)
    none = apply_help_maintenance(body, {key: False for key in HELP_TITLES})
    assert MAINT_HELP_HTML not in none


def test_sypher_does_not_treat_empty_pg_as_saved():
    import sys

    sys.path.insert(0, str(_ROOT))
    from bot.funcs.soft_restart import _cfg_from_row, _is_persisted_config
    from bot.funcs.sr_schedule import compute_next_at

    assert _is_persisted_config(None) is False
    assert _is_persisted_config({}) is False
    assert _is_persisted_config({"foo": 1}) is False
    assert _is_persisted_config({"enabled": True, "mode": "hourly"}) is True
    assert _cfg_from_row('{"enabled": true, "mode": "hourly"}')["mode"] == "hourly"
    nxt = compute_next_at(
        {"enabled": True, "mode": "hourly", "hourly_minute": 0, "initial_delay_sec": 30, "timezone": "Europe/Moscow"},
        now_ts=1_700_000_000,
        started_at=1_700_000_000,
        first_cycle=True,
    )
    assert nxt is not None
    assert nxt > 1_700_000_000


def test_captcha_fail_open_does_not_requery():
    import sys
    import time

    sys.path.insert(0, str(_ROOT))
    from bot.funcs import group_captcha as gc

    gc._fail_open.clear()
    assert gc._fail_open_cached(1, 2) is False
    gc._mark_fail_open(1, 2)
    assert gc._fail_open_cached(1, 2) is True
    gc._fail_open[(1, 2)] = time.monotonic() - 100
    assert gc._fail_open_cached(1, 2) is False
