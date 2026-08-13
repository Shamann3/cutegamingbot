# -*- coding: utf-8 -*-
"""Generate bot/runtime/callback_registry_generated.py from full repo scan."""
from __future__ import annotations

import collections
import pathlib
import re
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKIP = {"__pycache__", ".git", "venv", ".venv", "node_modules", ".cursor"}
# Не ИМПОРТИРУЕМ при bootstrap (circular / отдельный процесс / orphan).
# В карту prefix/exact их handlers ВСЁ РАВНО попадают (hot-dispatch).
SKIP_IMPORT_MODULES = {
    "main",  # circular — handlers уже на dp при старте
    "bot.magic.fallback",
    "bot.runtime.callback_bootstrap",
    "bot.runtime.callback_registry_generated",
    "bot.runtime._scan_callbacks",
    "bot.runtime._gen_callback_registry",
    "server.support_bot",  # отдельный бот
    "b_Eden.Garden_of_Eden",  # отдельный dispatcher
}
# Полностью игнор при скане карт
SKIP_SCAN_MODULES = {
    "bot.magic.fallback",
    "bot.runtime.callback_bootstrap",
    "bot.runtime.callback_registry_generated",
    "bot.runtime._scan_callbacks",
    "bot.runtime._gen_callback_registry",
}

DEC = re.compile(
    r"@(?P<target>[\w.]*)callback_query\((?P<filt>.*?)\)\s*\n\s*async def (?P<fn>\w+)",
    re.S,
)
START = re.compile(r"startswith\(\s*['\"]([^'\"]+)['\"]")
START_TUP = re.compile(r"startswith\(\s*\(([^)]+)\)")
EQ = re.compile(
    r"(?:c\.data|call\.data|callback_query\.data|query\.data)\s*==\s*['\"]([^'\"]+)['\"]"
)
IN_LIST = re.compile(r"(?:c\.data|call\.data).*?\bin\s*\[([^\]]+)\]")
FDATA_EQ = re.compile(r"F\.data\s*==\s*['\"]([^'\"]+)['\"]")
FDATA_START = re.compile(r"F\.data\.startswith\(\s*['\"]([^'\"]+)['\"]")
STR_LIT = re.compile(r"['\"]([^'\"]+)['\"]")


# Handlers с кастомными фильтрами (не startswith в декораторе) — вручную.
# Иначе greq/prep/spd после рестарта не попадут в hot-dispatch.
MANUAL_PREFIX: dict[str, tuple[str, str]] = {
    "greq:": ("main", "gift_send_request"),
    "sts:gr:": ("main", "gift_send_request"),
    "gift_send_request_": ("main", "gift_send_request"),
    "prep:": ("main", "send_request_callback"),
    "sts:ps:": ("main", "send_request_callback"),
    "preparationsend_": ("main", "send_request_callback"),
    "spd:": ("main", "speedconc_request_callback"),
    "speedconc_": ("main", "speedconc_request_callback"),
    "skipcb:": ("main", "gift_send_request"),  # gift filter раньше; prep тоже умеет
}


def scan():
    modules: set[str] = set()
    # pattern -> (module, fn, kind)  longest/first wins later
    prefix_map: dict[str, tuple[str, str]] = {}
    exact_map: dict[str, tuple[str, str]] = {}

    # manual first (can be overridden by real startswith if present)
    prefix_map.update(MANUAL_PREFIX)

    for p in ROOT.rglob("*.py"):
        if any(x in p.parts for x in SKIP):
            continue
        name = p.name
        if name.startswith("_scan") or name.startswith("_gen"):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "callback_query" not in text or "@" not in text:
            continue
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        mod = rel[:-3].replace("/", ".")
        if mod in SKIP_SCAN_MODULES:
            continue

        for m in DEC.finditer(text):
            if mod not in SKIP_IMPORT_MODULES:
                modules.add(mod)
            filt = m.group("filt")
            fn = m.group("fn")
            for s in START.findall(filt):
                prefix_map.setdefault(s, (mod, fn))
            for tup in START_TUP.findall(filt):
                for s in STR_LIT.findall(tup):
                    prefix_map.setdefault(s, (mod, fn))
            for s in EQ.findall(filt):
                exact_map.setdefault(s, (mod, fn))
            for block in IN_LIST.findall(filt):
                for s in STR_LIT.findall(block):
                    exact_map.setdefault(s, (mod, fn))
            for s in FDATA_EQ.findall(filt):
                exact_map.setdefault(s, (mod, fn))
            for s in FDATA_START.findall(filt):
                prefix_map.setdefault(s, (mod, fn))

    return sorted(modules), prefix_map, exact_map


def py_str(s: str) -> str:
    return repr(s)


def main() -> None:
    modules, prefix_map, exact_map = scan()
    out = ROOT / "bot" / "runtime" / "callback_registry_generated.py"

    lines = [
        "# -*- coding: utf-8 -*-",
        '"""AUTO-GENERATED — do not edit by hand.',
        "",
        "Источник: сканер всех @callback_query в репозитории.",
        "Пересобрать: python -m bot.runtime._gen_callback_registry",
        '"""',
        "from __future__ import annotations",
        "",
        "from typing import Dict, List, Tuple",
        "",
        f"# modules with @callback_query: {len(modules)}",
        "CALLBACK_MODULES: Tuple[str, ...] = (",
    ]
    for m in modules:
        lines.append(f"    {py_str(m)},")
    lines.append(")")
    lines.append("")
    lines.append(f"# prefix -> (module, handler): {len(prefix_map)}")
    lines.append("PREFIX_HANDLERS: Dict[str, Tuple[str, str]] = {")
    for pat in sorted(prefix_map.keys(), key=lambda x: (-len(x), x)):
        mod, fn = prefix_map[pat]
        lines.append(f"    {py_str(pat)}: ({py_str(mod)}, {py_str(fn)}),")
    lines.append("}")
    lines.append("")
    lines.append(f"# exact callback_data -> (module, handler): {len(exact_map)}")
    lines.append("EXACT_HANDLERS: Dict[str, Tuple[str, str]] = {")
    for pat in sorted(exact_map.keys()):
        mod, fn = exact_map[pat]
        lines.append(f"    {py_str(pat)}: ({py_str(mod)}, {py_str(fn)}),")
    lines.append("}")
    lines.append("")
    lines.append("def all_known_prefixes() -> List[str]:")
    lines.append("    return sorted(PREFIX_HANDLERS.keys(), key=len, reverse=True)")
    lines.append("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"wrote {out.name}: modules={len(modules)} "
        f"prefixes={len(prefix_map)} exact={len(exact_map)}"
    )


if __name__ == "__main__":
    main()
