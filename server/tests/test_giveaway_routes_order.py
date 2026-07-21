"""Розыгрыши: порядок регистрации маршрутов.

FastAPI сопоставляет пути в порядке регистрации. Литеральные маршруты
(/api/giveaways/history, /api/giveaways/winners-feed) ДОЛЖНЫ быть
зарегистрированы раньше динамического /api/giveaways/{giveaway_id}, иначе
GET /api/giveaways/history матчится на {giveaway_id}, "history" не парсится
как int → 422 «Неверный формат запроса», и вкладка «Прошедшие» падает.
"""
import os

os.environ.setdefault("PRODUCTION", "false")

from app import app


def _giveaway_route_paths():
    return [r.path for r in app.router.routes if getattr(r, "path", "").startswith("/api/giveaways")]


def test_literal_giveaway_routes_registered_before_param_route():
    paths = _giveaway_route_paths()
    param_idx = paths.index("/api/giveaways/{giveaway_id}")
    history_idx = paths.index("/api/giveaways/history")
    winners_idx = paths.index("/api/giveaways/winners-feed")
    assert history_idx < param_idx, (
        "/api/giveaways/history зарегистрирован после /{giveaway_id} — "
        f"порядок {paths}"
    )
    assert winners_idx < param_idx, (
        "/api/giveaways/winners-feed зарегистрирован после /{giveaway_id} — "
        f"порядок {paths}"
    )
