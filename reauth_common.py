"""
Общая логика локальной переавторизации Telethon-сессий (main / withdraw).

Важно:
- логинимся в *_new.session, чтобы не грузить мёртвый AuthKey из старого файла;
- receive_updates=False — Telethon 1.40.0 иначе может уронить update-loop
  сразу после Signed in и сломать exit code для .bat;
- перед свежим логином чистим битый *_new, но если *_new уже валиден —
  переиспользуем без повторного кода.
"""

from __future__ import annotations

import asyncio
import re
import warnings
from pathlib import Path
from typing import Callable, Optional

from telethon import TelegramClient


def session_path(name: str) -> Path:
    return Path(f"{name}.session")


def wipe_session(name: str) -> None:
    """Удаляет session + journal/shm/wal для указанного имени."""
    for suffix in (
        ".session",
        ".session-journal",
        ".session-shm",
        ".session-wal",
    ):
        path = Path(f"{name}{suffix}")
        if path.exists():
            try:
                path.unlink()
                print(f"  · удалено: {path.name}")
            except OSError as exc:
                print(f"  · не удалось удалить {path.name}: {exc}")


def _digits(value: Optional[str]) -> str:
    return re.sub(r"\D+", "", value or "")


def _save_session(client: TelegramClient) -> None:
    if hasattr(client.session, "save"):
        client.session.save()


async def _try_reuse_existing(
    session_name: str,
    api_id: int,
    api_hash: str,
    *,
    device_model: str,
    expected_user_id: Optional[int] = None,
    expected_phone_digits: Optional[str] = None,
) -> bool:
    """
    Если *_new.session уже есть и авторизован — возвращает True.
    Иначе False (вызывающий код сделает свежий логин).
    """
    path = session_path(session_name)
    if not path.exists() or path.stat().st_size < 64:
        return False

    print(f"Проверяю существующий файл {path.name}…")
    warnings.filterwarnings(
        "ignore",
        message="Using async sessions support is an experimental feature",
        category=UserWarning,
    )
    client = TelegramClient(
        session_name,
        api_id,
        api_hash,
        receive_updates=False,
        device_model=device_model,
        system_version="Windows",
        app_version="1.0",
        lang_code="ru",
        system_lang_code="ru",
    )
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("  · файл есть, но не авторизован — будет свежий логин")
            return False

        me = None
        try:
            me = await client.get_me()
        except Exception as exc:
            print(f"  · get_me() не удался ({type(exc).__name__}): {exc}")

        if me is not None:
            actual_id = int(getattr(me, "id", 0) or 0)
            phone = _digits(getattr(me, "phone", None))
            if expected_user_id and actual_id and actual_id != int(expected_user_id):
                print(
                    f"  · чужой аккаунт id={actual_id} "
                    f"(ожидали {expected_user_id}) — свежий логин"
                )
                return False
            if expected_phone_digits and phone and phone != expected_phone_digits:
                print(
                    f"  · телефон {phone!r} ≠ ожидали {expected_phone_digits!r} "
                    "— свежий логин"
                )
                return False
            print(
                f"✅ Переиспользуем сессию: id={actual_id} "
                f"username={getattr(me, 'username', None)!r} phone={phone!r}"
            )
        else:
            print("✅ Переиспользуем сессию (профиль не прочитан, auth=OK)")

        _save_session(client)
        return True
    except Exception as exc:
        print(f"  · reuse не удался ({type(exc).__name__}): {exc}")
        return False
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def authorize_session(
    session_name: str,
    api_id: int,
    api_hash: str,
    *,
    device_model: str,
    phone: Optional[str] = None,
    expected_user_id: Optional[int] = None,
    expected_phone_digits: Optional[str] = None,
    final_session_name: str,
    force_fresh: bool = False,
) -> None:
    """
    Авторизует session_name (*_new), сохраняет файл, проверяет identity.
    """
    path = session_path(session_name)

    if force_fresh:
        print("force_fresh: чищу старый *_new…")
        wipe_session(session_name)
    else:
        reused = await _try_reuse_existing(
            session_name,
            api_id,
            api_hash,
            device_model=device_model,
            expected_user_id=expected_user_id,
            expected_phone_digits=expected_phone_digits,
        )
        if reused:
            if not path.exists() or path.stat().st_size < 64:
                raise RuntimeError(f"Файл сессии пропал после reuse: {path.resolve()}")
            print(f"✅ Файл готов: {path.name} ({path.stat().st_size} bytes)")
            print(f"Дальше bat заменит его на {final_session_name}.session")
            return

        print("Чищу непригодный *_new перед свежим логином…")
        wipe_session(session_name)

    warnings.filterwarnings(
        "ignore",
        message="Using async sessions support is an experimental feature",
        category=UserWarning,
    )

    client = TelegramClient(
        session_name,
        api_id,
        api_hash,
        receive_updates=False,
        device_model=device_model,
        system_version="Windows",
        app_version="1.0",
        lang_code="ru",
        system_lang_code="ru",
    )

    phone_arg: Optional[Callable[[], str] | str] = None
    if phone:
        # Telethon примет строку; лямбда тоже ок для повторных запросов
        phone_arg = phone
        print(f"Телефон по умолчанию: {phone}")
        print("(можно изменить, если Telethon спросит другой)")

    me = None
    try:
        if phone_arg is not None:
            await client.start(phone=phone_arg)
        else:
            await client.start()

        if not await client.is_user_authorized():
            raise RuntimeError("Клиент не авторизован после start()")

        _save_session(client)

        try:
            me = await client.get_me()
        except (asyncio.CancelledError, Exception) as exc:
            print(f"[warn] get_me() не удался ({type(exc).__name__}): {exc}")
            print("[warn] Сессия всё равно сохранена — проверяем файл…")

        if not path.exists() or path.stat().st_size < 64:
            raise RuntimeError(f"Файл сессии не создан или пуст: {path.resolve()}")

        if me is not None:
            actual_id = int(getattr(me, "id", 0) or 0)
            username = getattr(me, "username", None)
            phone_raw = getattr(me, "phone", None)
            phone_d = _digits(phone_raw)
            print(
                f"✅ Авторизован: id={actual_id} username={username!r} "
                f"phone={phone_raw!r}"
            )
            if expected_user_id and actual_id and actual_id != int(expected_user_id):
                raise RuntimeError(
                    f"Неверный аккаунт: id={actual_id}, ожидали {expected_user_id}. "
                    "Файл *_new удалён не будет — проверь номер."
                )
            if expected_phone_digits and phone_d and phone_d != expected_phone_digits:
                raise RuntimeError(
                    f"Неверный телефон: {phone_d}, ожидали {expected_phone_digits}."
                )
        else:
            print("✅ Авторизован (профиль не прочитан, сессия на диске есть)")

        print(f"✅ Новая сессия: {path.name} ({path.stat().st_size} bytes)")
        print(f"Дальше bat заменит её на {final_session_name}.session")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
        # Финальный flush на диск после disconnect
        if path.exists():
            print(f"  · файл на диске: {path.resolve()}")
