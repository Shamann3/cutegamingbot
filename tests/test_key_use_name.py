# -*- coding: utf-8 -*-
"""Использование ключа не должно затираться локальной переменной shop_op."""
import ast
from pathlib import Path


def _shop_op():
    path = Path(__file__).resolve().parents[1] / "bot" / "funcs" / "shop.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "shop_op":
            return node
    raise AssertionError("shop_op missing")


def test_shop_op_does_not_shadow_the_key_handler():
    assigned = set()
    for node in ast.walk(_shop_op()):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == "key":
            assigned.add(node.lineno)
    assert assigned == set()
