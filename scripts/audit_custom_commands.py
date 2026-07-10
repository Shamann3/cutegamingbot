"""Аудит покрытия custom_commands обработчиками в main.py.

Идея: команда «работает», если в диспетчере есть ветка, которая её ловит.
Диспетчер ловит текст двумя способами:
  • ПРЕФИКС:  text.startswith(keyword)          -> keyword префикс команды
  • ТОЧНО:    message.text in {...} / == "..."   -> полное совпадение

Скрипт извлекает из main.py:
  1) множество custom_commands (гейт),
  2) все keyword'ы префиксных веток (startswith),
  3) все строки точных веток (in / ==),
и печатает команды, которые НЕ ловятся ни одной веткой — их и надо чинить.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main.py"

# Выражения слева, которые считаем «текстом входящего сообщения».
LEFT_TEXT_EXPRS = {
    "message.text", "message.text.lower()", "message.text.lower().strip()",
    "text", "text.lower()", "text_lower", "tl", "txt", "msg_text",
    "message.text.strip()", "message.text.strip().lower()",
}


def _str_elts(node: ast.AST) -> list[str]:
    out = []
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        for e in node.elts:
            if isinstance(e, ast.Constant) and isinstance(e.value, str):
                out.append(e.value)
    return out


def main() -> int:
    src = MAIN.read_text(encoding="utf-8")
    tree = ast.parse(src)

    # NAME -> список строковых литералов (аккумулируем все присваивания).
    name_strings: dict[str, list[str]] = {}
    custom: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, (ast.Set, ast.List, ast.Tuple)):
            strs = _str_elts(node.value)
            if not strs:
                continue
            for t in node.targets:
                if isinstance(t, ast.Name):
                    name_strings.setdefault(t.id, []).extend(strs)
                    if t.id == "custom_commands":
                        custom = strs

    if not custom:
        print("!! custom_commands set not found")
        return 2

    K_prefix: set[str] = set()
    K_exact: set[str] = set()

    for node in ast.walk(tree):
        # --- startswith(...) ---
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "startswith":
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    K_prefix.add(a.value)
                elif isinstance(a, (ast.Tuple, ast.List, ast.Set)):
                    K_prefix.update(_str_elts(a))
                elif isinstance(a, ast.Name):
                    K_prefix.update(name_strings.get(a.id, []))

        # --- any(... .startswith(x) for x in COLLECTION) ---
        if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
            has_sw = any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "startswith"
                for n in ast.walk(node.elt)
            )
            if has_sw:
                for gen in node.generators:
                    it = gen.iter
                    if isinstance(it, ast.Name):
                        K_prefix.update(name_strings.get(it.id, []))
                    else:
                        K_prefix.update(_str_elts(it))

        # --- message.text in {...}  /  message.text == "..." ---
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            try:
                left_src = ast.unparse(node.left)
            except Exception:
                left_src = ""
            if left_src in LEFT_TEXT_EXPRS:
                comp = node.comparators[0]
                if isinstance(node.ops[0], ast.In):
                    if isinstance(comp, ast.Name):
                        K_exact.update(name_strings.get(comp.id, []))
                    else:
                        K_exact.update(_str_elts(comp))
                elif isinstance(node.ops[0], ast.Eq):
                    if isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                        K_exact.add(comp.value)

    prefixes = sorted({k.lower() for k in K_prefix if k})
    exact = {k.lower() for k in K_exact}

    uncovered = []
    for c in custom:
        cl = c.lower()
        if cl in exact:
            continue
        if any(cl.startswith(k) for k in prefixes):
            continue
        uncovered.append(c)

    total = len(custom)
    uniq = len(set(custom))
    lines = [
        f"custom_commands: {total} записей ({uniq} уникальных)",
        f"keyword'ов префиксных веток: {len(prefixes)}",
        f"строк точных веток:          {len(exact)}",
        f"НЕ покрыто ни одной веткой:  {len(uncovered)}",
        "-" * 60,
    ]
    for c in uncovered:
        lines.append(c)
    report = "\n".join(lines) + "\n"
    out = Path(__file__).resolve().parent / "audit_report.txt"
    out.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
