"""Статическая проверка вызова команд бота.

Идея: команды из custom_commands в main.py диспатчатся длинной цепочкой блоков,
каждый из которых ЛЕНИВО импортирует свой обработчик, например:

    from bot.tggames.slots import tgslots

Если такой импорт сломан (нет модуля или нет символа) — соответствующая команда
падает в рантайме. Скрипт разбирает main.py (и при желании другие файлы) через AST
и проверяет, что каждый `from <локальный модуль> import <имя>` и `import <модуль>`
реально резолвится: файл существует и символ в нём определён на верхнем уровне.

Ничего не исполняет (безопасно). Возвращает код 1, если есть проблемы.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]

# Чтобы find_spec('main') и другие корневые модули резолвились корректно.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Пакеты, которые считаем «локальными» (проверяем строго по файлам проекта).
LOCAL_TOP_LEVEL = {"bot", "server", "b_Eden", "scripts"}


def _module_to_path(module: str) -> Tuple[Path, bool] | Tuple[None, None]:
    """Возвращает (path, is_package) для локального модуля или (None, None).

    Поддерживает namespace-пакеты (каталог без __init__.py) — тогда is_package=True,
    а path указывает на каталог.
    """
    parts = module.split(".")
    base = ROOT.joinpath(*parts)
    pkg_init = base / "__init__.py"
    mod_file = base.with_suffix(".py")
    if pkg_init.is_file():
        return pkg_init, True
    if mod_file.is_file():
        return mod_file, False
    if base.is_dir():
        # namespace package (без __init__.py) — импорт подмодулей всё равно работает
        return base, True
    return None, None


_top_names_cache: Dict[str, Set[str]] = {}
_has_star_cache: Dict[str, bool] = {}


def _module_top_level(module: str) -> Tuple[Set[str], bool]:
    """Имена верхнего уровня модуля + флаг наличия `from x import *`."""
    if module in _top_names_cache:
        return _top_names_cache[module], _has_star_cache[module]

    path, _is_pkg = _module_to_path(module)
    names: Set[str] = set()
    has_star = False
    if path is None:
        _top_names_cache[module] = names
        _has_star_cache[module] = False
        return names, False

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        _top_names_cache[module] = names
        _has_star_cache[module] = False
        return names, False

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
                elif isinstance(t, (ast.Tuple, ast.List)):
                    for e in t.elts:
                        if isinstance(e, ast.Name):
                            names.add(e.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import):
            for a in node.names:
                names.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if any(a.name == "*" for a in node.names):
                has_star = True
            for a in node.names:
                if a.name != "*":
                    names.add(a.asname or a.name)

    _top_names_cache[module] = names
    _has_star_cache[module] = has_star
    return names, has_star


def _is_local(module: str) -> bool:
    return module.split(".")[0] in LOCAL_TOP_LEVEL


def _installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _optional_import_lines(tree: ast.AST) -> Set[int]:
    """Строки импортов, находящихся в теле try: (опциональные, с фолбэком)."""
    lines: Set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, (ast.Import, ast.ImportFrom)):
                        lines.add(sub.lineno)
    return lines


def check_file(py: Path) -> List[str]:
    problems: List[str] = []
    tree = ast.parse(py.read_text(encoding="utf-8"))
    optional_lines = _optional_import_lines(tree)

    # Имена верхнего уровня самого проверяемого файла (для self-import `from main ...`).
    self_module = py.stem  # 'main.py' -> 'main'
    self_names: Set[str] = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            self_names.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    self_names.add(t.id)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # относительные импорты — пропускаем
            if node.lineno in optional_lines:
                continue  # опциональный импорт в try/except
            module = node.module or ""
            if not module:
                continue

            # self-import: `from main import X` внутри main.py
            if module == self_module:
                for a in node.names:
                    if a.name != "*" and a.name not in self_names:
                        problems.append(
                            f"L{node.lineno}: сам файл не содержит '{a.name}' "
                            f"(self-import из '{module}')"
                        )
                continue

            if _is_local(module):
                path, is_pkg = _module_to_path(module)
                if path is None:
                    problems.append(f"L{node.lineno}: модуль не найден: '{module}'")
                    continue
                # namespace-пакет (каталог без __init__.py): имена = подмодули/подпакеты
                if is_pkg and path.is_dir():
                    for a in node.names:
                        if a.name == "*":
                            continue
                        sub_py = path / f"{a.name}.py"
                        sub_pkg = path / a.name
                        if not sub_py.is_file() and not sub_pkg.is_dir():
                            problems.append(
                                f"L{node.lineno}: в пакете '{module}' нет '{a.name}'"
                            )
                    continue
                names, has_star = _module_top_level(module)
                if has_star:
                    continue  # from x import * — судить строго нельзя
                for a in node.names:
                    if a.name == "*":
                        continue
                    if a.name not in names:
                        problems.append(
                            f"L{node.lineno}: '{module}' не экспортирует '{a.name}'"
                        )
            else:
                base = module.split(".")[0]
                if not _installed(module) and not _installed(base):
                    problems.append(
                        f"L{node.lineno}: сторонний модуль не установлен: '{module}'"
                    )
        elif isinstance(node, ast.Import):
            if node.lineno in optional_lines:
                continue
            for a in node.names:
                module = a.name
                if module == self_module:
                    continue
                if _is_local(module):
                    path, _is_pkg = _module_to_path(module)
                    if path is None:
                        problems.append(f"L{node.lineno}: модуль не найден: '{module}'")
                elif not _installed(module) and not _installed(module.split(".")[0]):
                    problems.append(
                        f"L{node.lineno}: сторонний модуль не установлен: '{module}'"
                    )
    return problems


def main() -> int:
    targets = [ROOT / "main.py"]
    if len(sys.argv) > 1:
        targets = [Path(p) for p in sys.argv[1:]]

    total = 0
    for py in targets:
        if not py.is_file():
            print(f"[skip] нет файла: {py}")
            continue
        probs = check_file(py)
        # Дедуп с сохранением порядка.
        seen: Set[str] = set()
        uniq = [p for p in probs if not (p in seen or seen.add(p))]
        if uniq:
            print(f"\n=== {py.name}: найдено проблем импорта: {len(uniq)} ===")
            for p in uniq:
                print("  " + p)
            total += len(uniq)
        else:
            print(f"[ok] {py.name}: все импорты резолвятся")

    print(f"\nИТОГО проблем: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
