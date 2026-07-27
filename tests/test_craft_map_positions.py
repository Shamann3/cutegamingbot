"""Проверка сериализации позиций карты крафта (чистый хелпер, без БД)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from craft_map import serialize_positions


def test_serialize_positions_maps_rows_to_dict():
    rows = [
        {"item_id": 5, "x": 10.0, "y": -3.5},
        {"item_id": "12", "x": 0.0, "y": 0.0},
    ]
    assert serialize_positions(rows) == {
        "5": {"x": 10.0, "y": -3.5},
        "12": {"x": 0.0, "y": 0.0},
    }


def test_serialize_positions_empty():
    assert serialize_positions([]) == {}


if __name__ == "__main__":
    test_serialize_positions_maps_rows_to_dict()
    test_serialize_positions_empty()
    print("ok")
