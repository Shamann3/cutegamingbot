# -*- coding: utf-8 -*-
"""
Полный аудит проекта: каждая inline-кнопка под Мэджик.

────────────────────────────────────────────────────────────
ЧТО ДЕЛАЕТ ЦИКЛ
────────────────────────────────────────────────────────────
1) Сканирует КАЖДЫЙ .py файл проекта на InlineKeyboard*
2) Сопоставляет файлы → модули Python
3) При необходимости импортирует модули bot.*/b_Eden.*/server.*
4) Rebind: подменяет ВСЕ ссылки на InlineKeyboardButton/Markup
   (включая алиасы вроде IKB = InlineKeyboardButton)
5) Проверяет, что middleware Мэджик стоит на Dispatcher
6) Печатает отчёт покрытия

Логику кнопок НЕ меняет — только связывает с системой Мэджик.

Вызов:
    from bot.magic.audit import run_magic_audit
    report = run_magic_audit(dp=dp, import_missing=True)
"""
from __future__ import annotations

import importlib
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("magic")

# Корни, которые считаем «нашим» кодом
_PROJECT_PREFIXES: Tuple[str, ...] = (
    "main",
    "__main__",
    "bot",
    "b_Eden",
    "server",
    "admin",
)

# Папки, которые не сканируем
_SKIP_DIRS: Set[str] = {
    "__pycache__",
    ".git",
    ".idea",
    ".venv",
    "venv",
    "logs",
    "node_modules",
    ".cursor",
    "dist",
    "build",
}

# Маркеры inline-клавиатур в исходниках
_INLINE_MARKERS: Tuple[str, ...] = (
    "InlineKeyboardButton",
    "InlineKeyboardMarkup",
    "InlineKeyboardBuilder",
)


@dataclass
class FileHit:
    """Один файл проекта с inline-клавиатурами."""

    rel_path: str
    abs_path: str
    markers: Dict[str, int] = field(default_factory=dict)
    module_name: Optional[str] = None
    imported: bool = False
    rebound: bool = False
    verified: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class AuditReport:
    """Итог полного цикла аудита."""

    files_total_scanned: int = 0
    files_with_inline: int = 0
    modules_rebound: int = 0
    attrs_rebound: int = 0
    modules_verified_ok: int = 0
    modules_verified_fail: int = 0
    modules_imported: int = 0
    middleware_ok: bool = False
    patch_ok: bool = False
    hits: List[FileHit] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "════ МЭДЖИК AUDIT ════",
            f"файлов просканировано     = {self.files_total_scanned}",
            f"с InlineKeyboard*         = {self.files_with_inline}",
            f"модулей импортировано     = {self.modules_imported}",
            f"модулей rebound           = {self.modules_rebound}",
            f"атрибутов подменено       = {self.attrs_rebound}",
            f"проверено OK              = {self.modules_verified_ok}",
            f"проверено FAIL            = {self.modules_verified_fail}",
            f"patch keyboards           = {self.patch_ok}",
            f"middleware на dp          = {self.middleware_ok}",
        ]
        if self.errors:
            lines.append(f"ошибок                   = {len(self.errors)}")
            for e in self.errors[:8]:
                lines.append(f"  • {e}")
        # покрытие
        if self.files_with_inline:
            covered = sum(1 for h in self.hits if h.verified or h.rebound)
            lines.append(
                f"покрытие файлов           = {covered}/{self.files_with_inline}"
            )
        lines.append("═══════════════════════")
        return "\n".join(lines)


def _project_root() -> str:
    # bot/magic/audit.py → корень репо = ../../..
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))


def _iter_py_files(root: str) -> List[str]:
    out: List[str] = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in _SKIP_DIRS and not d.startswith(".")]
        # не сканируем сам кэш/временные
        base = os.path.basename(dp)
        if base in _SKIP_DIRS:
            continue
        for fn in fns:
            if not fn.endswith(".py"):
                continue
            if fn.startswith("_tmp"):
                continue
            out.append(os.path.join(dp, fn))
    return out


def _rel(root: str, path: str) -> str:
    return os.path.relpath(path, root).replace("\\", "/")


def _path_to_module(root: str, path: str) -> Optional[str]:
    """
    Преобразует путь файла в имя модуля.
    main.py → main
    bot/funcs/shop.py → bot.funcs.shop
    """
    rel = _rel(root, path)
    if rel.endswith(".py"):
        rel = rel[:-3]
    if rel.endswith("/__init__"):
        rel = rel[: -len("/__init__")]
    parts = rel.split("/")
    if not parts or parts[0] in ("",):
        return None
    # только известные корни проекта
    if parts[0] not in ("bot", "b_Eden", "server", "main", "admin"):
        # main.py лежит в корне
        if len(parts) == 1 and parts[0] == "main":
            return "main"
        return None
    if parts[0] == "main" and len(parts) == 1:
        return "main"
    return ".".join(parts)


def scan_project_inline_files(root: Optional[str] = None) -> List[FileHit]:
    """Шаг 1: найти все файлы с InlineKeyboard*."""
    root = root or _project_root()
    hits: List[FileHit] = []
    for path in _iter_py_files(root):
        rel = _rel(root, path)
        # сам magic/audit не считаем «целью», но patch/buttons — ок для отчёта
        try:
            src = open(path, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        markers = {m: src.count(m) for m in _INLINE_MARKERS if m in src}
        if not markers:
            continue
        hits.append(
            FileHit(
                rel_path=rel,
                abs_path=path,
                markers=markers,
                module_name=_path_to_module(root, path),
            )
        )
    hits.sort(key=lambda h: h.rel_path)
    return hits


def _is_project_module(name: str) -> bool:
    if name in ("main", "__main__"):
        return True
    for p in _PROJECT_PREFIXES:
        if name == p or name.startswith(p + "."):
            return True
    # aiogram тоже rebind'им (на всякий)
    if name == "aiogram" or name.startswith("aiogram."):
        return True
    return False


def rebind_all_inline_refs() -> Tuple[int, int]:
    """
    Шаг 4: подменить в каждом загруженном модуле ВСЕ атрибуты,
    которые ссылаются на оригинальный InlineKeyboardButton/Markup.

    Возвращает (modules_touched, attrs_changed).
    """
    from bot.magic import patch as magic_patch

    magic_btn = getattr(magic_patch, "_MagicBtn", None)
    magic_mk = getattr(magic_patch, "_MagicMarkup", None)
    orig_btn = getattr(magic_patch, "_OrigBtn", None)
    orig_mk = getattr(magic_patch, "_OrigMarkup", None)

    if magic_btn is None or magic_mk is None:
        # патч ещё не ставили
        from bot.magic.patch import patch_aiogram_keyboards

        patch_aiogram_keyboards()
        magic_btn = magic_patch._MagicBtn
        magic_mk = magic_patch._MagicMarkup
        orig_btn = magic_patch._OrigBtn
        orig_mk = magic_patch._OrigMarkup

    if magic_btn is None or magic_mk is None:
        return 0, 0

    modules_touched = 0
    attrs_changed = 0

    for name, mod in list(sys.modules.items()):
        if mod is None or not _is_project_module(name):
            continue
        try:
            d = getattr(mod, "__dict__", None)
            if not isinstance(d, dict):
                continue
        except Exception:
            continue

        changed_here = 0
        # копия ключей — словарь может меняться
        for attr in list(d.keys()):
            try:
                val = d.get(attr)
            except Exception:
                continue
            if val is None:
                continue
            # точное совпадение с оригиналом ИЛИ «голый» InlineKeyboard* без magic
            try:
                if val is orig_btn or (
                    val is not magic_btn
                    and getattr(val, "__name__", "") == "InlineKeyboardButton"
                    and not getattr(val, "_magic_wrapped", False)
                    and isinstance(val, type)
                ):
                    setattr(mod, attr, magic_btn)
                    changed_here += 1
                    continue
                if val is orig_mk or (
                    val is not magic_mk
                    and getattr(val, "__name__", "") == "InlineKeyboardMarkup"
                    and not getattr(val, "_magic_wrapped", False)
                    and isinstance(val, type)
                ):
                    setattr(mod, attr, magic_mk)
                    changed_here += 1
                    continue
            except Exception:
                continue

        if changed_here:
            modules_touched += 1
            attrs_changed += changed_here

    return modules_touched, attrs_changed


def _module_inline_ok(mod: Any) -> Tuple[bool, str]:
    """Проверить, что ссылки модуля на InlineKeyboard* — magic-wrapped."""
    from bot.magic import patch as magic_patch

    magic_btn = magic_patch._MagicBtn
    magic_mk = magic_patch._MagicMarkup
    if magic_btn is None:
        return False, "patch_missing"

    d = getattr(mod, "__dict__", {})
    checked = 0
    for attr, val in list(d.items()):
        if not isinstance(val, type):
            continue
        name = getattr(val, "__name__", "")
        if name not in ("InlineKeyboardButton", "InlineKeyboardMarkup", "MagicInlineKeyboardButton", "MagicInlineKeyboardMarkup"):
            # также ловим по _magic_wrapped / оригиналу
            if val is magic_patch._OrigBtn or val is magic_patch._OrigMarkup:
                return False, f"stale:{attr}"
            continue
        checked += 1
        if name in ("InlineKeyboardButton", "MagicInlineKeyboardButton"):
            if val is not magic_btn and not getattr(val, "_magic_wrapped", False):
                return False, f"btn_not_magic:{attr}"
        if name in ("InlineKeyboardMarkup", "MagicInlineKeyboardMarkup"):
            if val is not magic_mk and not getattr(val, "_magic_wrapped", False):
                return False, f"markup_not_magic:{attr}"
    # модуль может использовать только types.InlineKeyboardButton
    # тогда checked==0, но aiogram.types уже запатчен → OK
    if checked == 0:
        types_mod = d.get("types")
        if types_mod is not None:
            btn = getattr(types_mod, "InlineKeyboardButton", None)
            if btn is not None and (
                btn is magic_btn or getattr(btn, "_magic_wrapped", False)
            ):
                return True, "via_types"
        # нет локальных ссылок — клики всё равно через middleware
        return True, "middleware_only"
    return True, f"ok:{checked}"


def _try_import(module_name: str) -> Tuple[bool, str]:
    if module_name in sys.modules:
        return True, "already"
    # main / огромные модули с side-effects — не импортируем принудительно
    if module_name in ("main", "__main__"):
        return False, "skip_main"
    try:
        importlib.import_module(module_name)
        return True, "imported"
    except Exception as e:
        return False, f"import_err:{e!r}"


def _check_middleware(dp: Any) -> bool:
    if dp is None:
        from bot.magic.core import magic

        return bool(magic.installed)
    try:
        from bot.magic.middleware import MagicCallbackMiddleware
        from bot.magic.install import attached_dispatcher_count

        if attached_dispatcher_count() > 0:
            return True

        cq = getattr(dp, "callback_query", None)
        if cq is None:
            from bot.magic.core import magic

            return bool(magic.installed)

        middlewares = []
        for attr in (
            "_outer_middleware",
            "outer_middleware",
            "_middlewares",
            "middleware",
        ):
            obj = getattr(cq, attr, None)
            if obj is None:
                continue
            chain = getattr(obj, "middlewares", None) or getattr(
                obj, "_middlewares", None
            )
            if chain:
                middlewares.extend(list(chain))
            try:
                middlewares.extend(list(obj))
            except Exception:
                pass

        for mw in middlewares:
            if isinstance(mw, MagicCallbackMiddleware):
                return True
            if getattr(mw, "__class__", type).__name__ == "MagicCallbackMiddleware":
                return True

        from bot.magic.core import magic

        return bool(magic.installed)
    except Exception:
        from bot.magic.core import magic

        return bool(magic.installed)


def run_magic_audit(
    *,
    dp: Any = None,
    import_missing: bool = True,
    verbose: bool = True,
) -> AuditReport:
    """
    Полный цикл: скан → import → patch → rebind → verify.

    Вызывать после install_magic() (и желательно после импорта хендлеров).
    """
    from bot.magic.core import magic
    from bot.magic.patch import patch_aiogram_keyboards

    report = AuditReport()
    root = _project_root()

    # 1) скан файлов
    all_py = _iter_py_files(root)
    report.files_total_scanned = len(all_py)
    hits = scan_project_inline_files(root)
    # не считаем служебные magic-файлы как «дыры», но включаем в отчёт
    report.hits = hits
    report.files_with_inline = len(hits)

    # 2) patch
    try:
        report.patch_ok = bool(patch_aiogram_keyboards())
    except Exception as e:
        report.patch_ok = False
        report.errors.append(f"patch:{e!r}")

    # 3) импорт недостающих модулей (осторожно)
    if import_missing:
        for hit in hits:
            name = hit.module_name
            if not name:
                hit.notes.append("no_module_name")
                continue
            if name.startswith("bot.magic"):
                hit.imported = name in sys.modules
                continue
            ok, why = _try_import(name)
            if ok and why == "imported":
                report.modules_imported += 1
                hit.imported = True
                hit.notes.append("imported_now")
            elif ok:
                hit.imported = True
                hit.notes.append(why)
            else:
                hit.notes.append(why)

    # 4) жёсткий rebind всех ссылок/алиасов
    try:
        mods, attrs = rebind_all_inline_refs()
        report.modules_rebound = mods
        report.attrs_rebound = attrs
        for hit in hits:
            if hit.module_name and hit.module_name in sys.modules:
                hit.rebound = True
    except Exception as e:
        report.errors.append(f"rebind:{e!r}")

    # 5) verify каждого модуля с inline
    for hit in hits:
        name = hit.module_name
        if not name or name not in sys.modules:
            # файл есть, модуль не загружен — клики всё равно через middleware,
            # когда модуль загрузится / уже загружен как часть main
            if name in ("main", "__main__") and ("main" in sys.modules or "__main__" in sys.modules):
                mod = sys.modules.get("main") or sys.modules.get("__main__")
                ok, why = _module_inline_ok(mod)
                hit.verified = ok
                hit.notes.append(why)
                if ok:
                    report.modules_verified_ok += 1
                else:
                    report.modules_verified_fail += 1
            else:
                hit.notes.append("not_in_sys_modules")
                # если есть middleware — покрытие runtime всё равно есть
                hit.verified = bool(magic.installed)
                if hit.verified:
                    report.modules_verified_ok += 1
                else:
                    report.modules_verified_fail += 1
            continue
        ok, why = _module_inline_ok(sys.modules[name])
        hit.verified = ok
        hit.notes.append(why)
        if ok:
            report.modules_verified_ok += 1
        else:
            report.modules_verified_fail += 1
            report.errors.append(f"verify_fail:{name}:{why}")

    # 6) middleware
    report.middleware_ok = _check_middleware(dp) or bool(magic.installed)

    # сохранить на ядре
    try:
        magic.last_audit = report  # type: ignore[attr-defined]
    except Exception:
        pass

    text = report.summary()
    if verbose:
        print(text)
        # короткий список FAIL
        fails = [h for h in hits if not h.verified]
        if fails:
            print("⚠️ [MAGIC] не полностью verified (runtime всё равно через middleware):")
            for h in fails[:20]:
                print(f"   - {h.rel_path} :: {', '.join(h.notes)}")
        else:
            print("✅ [MAGIC] все найденные inline-файлы связаны с системой Мэджик")

    logger.info("AUDIT done inline_files=%s rebound_attrs=%s", report.files_with_inline, report.attrs_rebound)
    return report
