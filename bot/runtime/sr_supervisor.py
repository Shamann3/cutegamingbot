# -*- coding: utf-8 -*-
"""PID-1 супервизор бота: soft-restart без «дыры» как при rolling-деплое.

Порядок handoff (как на DO: новый рядом со старым, потом смена):
  1) текущий бот пишет handoff_request
  2) супервизор поднимает НОВЫЙ процесс (warmup: БД/код, без polling/Telethon)
  3) новый пишет child_ready
  4) супервизор просит старый отпустить очередь (release_old)
  5) старый гасит polling/Telethon и выходит
  6) супервизор даёт child_go → новый начинает polling

Пока идёт warmup (шаги 2–3), старый бот всё ещё обслуживает людей.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

DIR = Path(os.environ.get("SR_DIR", "/tmp/cg_sr"))
_FILES = (
    "handoff_request",
    "child_ready",
    "child_go",
    "release_old",
    "old_released",
    "pkl_flushed",
)


def _log(msg: str) -> None:
    print(f"[SR-SUP] {msg}", flush=True)


def _clear(*names: str) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    for name in names or _FILES:
        p = DIR / name
        try:
            p.unlink()
        except FileNotFoundError:
            pass
        except Exception as e:
            _log(f"unlink {name}: {e!r}")


def _exists(name: str) -> bool:
    return (DIR / name).exists()


def _touch(name: str, text: str = "1") -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / name).write_text(text, encoding="utf-8")


def _spawn(cmd: list[str], *, handoff_child: bool) -> subprocess.Popen:
    env = os.environ.copy()
    env["SR_SUPERVISOR"] = "1"
    env["SR_DIR"] = str(DIR)
    if handoff_child:
        env["SR_HANDOFF_CHILD"] = "1"
        # Уже внутри контейнера; Telethon/polling ждём по child_go
        env["USERBOT_CONNECT_DELAY_SEC"] = "0"
        env["BOT_POLLING_START_DELAY"] = "0"
    else:
        env.pop("SR_HANDOFF_CHILD", None)
    _log("spawn " + ("handoff-child" if handoff_child else "primary") + f" cmd={cmd!r}")
    return subprocess.Popen(cmd, env=env)


def _wait_file(name: str, proc: subprocess.Popen, timeout: float) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if _exists(name):
            return True
        if proc.poll() is not None:
            return False
        time.sleep(0.15)
    return _exists(name)


def _stop_proc(proc: subprocess.Popen, timeout: float = 45.0) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
    except Exception as e:
        _log(f"signal old: {e!r}")
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return
        time.sleep(0.1)
    _log("old still alive — kill")
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=10)
    except Exception:
        pass


def _do_handoff(old: subprocess.Popen, cmd: list[str]) -> subprocess.Popen:
    _log("handoff: start warmup child (old still serving)")
    _clear("child_ready", "child_go", "release_old", "old_released")
    warm = _spawn(cmd, handoff_child=True)

    if not _wait_file("child_ready", warm, timeout=180.0):
        _log("handoff: warmup failed/timeout — abort, keep old")
        _stop_proc(warm, timeout=10.0)
        _clear("handoff_request", "child_ready", "child_go", "release_old", "old_released")
        return old

    _log("handoff: child ready → release old (old will flush pkl first)")
    _touch("release_old")
    # Старый: flush pkl → stop polling → old_released. Без flush кнопки умрут.
    if not _wait_file("old_released", old, timeout=60.0):
        _log("handoff: old_released timeout — SIGTERM")
    if not _exists("pkl_flushed"):
        _log("handoff: WARN pkl_flushed missing — buttons may be stale")
    _stop_proc(old, timeout=20.0)

    # Пауза: Redis settle + Telethon session file / TCP
    time.sleep(1.2)
    _touch("child_go")
    _clear("handoff_request", "release_old", "old_released", "pkl_flushed")
    _log("handoff: child_go — new instance adopts Redis and takes traffic")
    return warm


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = [sys.executable, "-u", "main.py"]

    # Если передали `python -u main.py` — ок; если только main.py — добавим python
    if argv[0].endswith(".py"):
        argv = [sys.executable, "-u", *argv]

    _log(f"PID-1 supervisor up dir={DIR} cmd={argv!r}")
    _clear()
    _touch("supervisor_alive")

    child = _spawn(argv, handoff_child=False)

    while True:
        try:
            if _exists("handoff_request") and child.poll() is None:
                child = _do_handoff(child, argv)
                continue

            code = child.poll()
            if code is not None:
                _log(f"child exited code={code} — restart in 1s (no deploy wait)")
                time.sleep(1.0)
                _clear()
                _touch("supervisor_alive")
                child = _spawn(argv, handoff_child=False)
                continue

            time.sleep(0.2)
        except KeyboardInterrupt:
            _log("KeyboardInterrupt — stopping child")
            _stop_proc(child)
            return 0
        except Exception as e:
            _log(f"loop error: {type(e).__name__}: {e}")
            time.sleep(1.0)


if __name__ == "__main__":
    raise SystemExit(main())
