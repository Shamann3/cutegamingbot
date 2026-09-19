from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _read(*parts: str) -> str:
    return (_ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_normalize_and_preview():
    import sys

    sys.path.insert(0, str(_ROOT / "server"))
    from game_desk.catalog import default_payload, game_meta
    from game_desk.store import merge_payload, normalize_payload

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

    nxt = merge_payload(clean, {"games": {"slots": {"enabled": False, "minBet": 15, "commissionMult": 0, "params": {"jamChance": 0.2, "tripleSeven": 4}}}})
    assert nxt["games"]["slots"]["enabled"] is False
    assert nxt["games"]["slots"]["minBet"] == 15
    assert nxt["games"]["slots"]["commissionMult"] == 0.0
    assert nxt["games"]["slots"]["params"]["jamChance"] == 0.2
    assert nxt["games"]["slots"]["params"]["tripleSeven"] == 4
    assert nxt["games"]["kube"]["minBet"] == clean["games"]["kube"]["minBet"]

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
    assert GAME_BY_KEY["soccer"]["theme"]["motif"] == "grass"
    assert GAME_BY_KEY["scah"]["theme"]["motif"] == "board"
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
    assert "gm-hero" in section
    assert "gm-motif-" in section
    assert "is-dirty" in section
    assert "Copyable" in section
    css = _read("admin", "src", "styles", "games.css")
    assert "minmax(min(16.4rem, 100%), 1fr)" in css
    assert "grid-template-columns: 1fr" in css
    assert ".gm-page.is-dirty" in css
    for motif in ("board", "wood", "cookie", "wheel", "felt", "grass", "roulette", "blast"):
        assert f"gm-motif-{motif}" in css
    bot_live = _read("bot", "runtime", "game_desk", "live.py")
    assert "reject_desk" in bot_live
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
