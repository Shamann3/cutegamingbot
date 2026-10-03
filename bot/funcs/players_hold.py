"""Тот же счётчик, что у панели.

Панель живёт отдельно и не импортирует пакет bot.
Код счётчика лежит в server/players_hold.py и попадает в образ API как players_hold.py.
"""
from server.players_hold import (  # noqa: F401
    add_held_game,
    fold_held_games_now,
    game_goes_to_hold,
    held_board,
    held_totals,
    public_players_gate,
)
