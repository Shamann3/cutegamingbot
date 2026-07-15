# Циклические посты в группы — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an admin create multiple independent recurring "post" campaigns (text + optional photo + unlimited inline buttons) that fire on their own interval into one or more Telegram groups (`chat_id`), fully manageable (create/edit/pause/resume/delete/run-now) with per-group delivery history.

**Architecture:** New DB tables (`group_post_campaigns`, `group_post_log`), a new `server/group_posts.py` module (validation + CRUD + send execution) following the exact shape of the existing `server/admin_broadcast.py`, wired into the already-running 30s tick in `server/event_scheduler.py`. Sending goes through `server/telegram_notify.py`, extended with a generic inline-keyboard builder and photo-sending (upload-once-cache-`file_id`, matching the existing `_upload_photo_to_telegram` pattern already used elsewhere in `server/admin_routes.py`). New admin REST endpoints + a new `GroupPostsPanel.jsx` component, added as a second tab inside the existing Broadcast section.

**Tech Stack:** FastAPI + asyncpg (server/), React + Vite (admin/), Telegram Bot HTTP API (no polling/webhook involved — pure outbound HTTP calls, consistent with how DM broadcasts already work).

## Global Constraints

- No automated test suite exists anywhere in this repo (zero `test_*.py` files, no `pytest` in requirements, no JS test runner configured) — see "Verification approach" below for how this plan adapts.
- **Never add a `REFERENCES` foreign key from new tables to existing ones** without verifying the referenced column's constraint in the real production DB first. `broadcast_recipients` (added 2026-07-15) had its FK dropped after `InvalidForeignKeyError` crash-looped the whole `api` service in production — `broadcast_runs.id` unexpectedly had no usable unique constraint in the live DB despite `schema.sql` saying `PRIMARY KEY`. Both new tables in this plan are FK-free by design; do not add one during implementation.
- Buttons only support `url` and `web_app` types — no `callback_data` (would need a live Telegram update listener, which `server/` does not run; see `server/game_bot.py`'s own comment on this).
- DigitalOcean App Platform containers have no persistent disk across deploys/restarts — photo bytes MUST go into Postgres (`BYTEA`), never the filesystem.
- Reuse `require_admin_permission("manage_broadcast")` for every new endpoint — same permission that already gates the Broadcast tab, no new permission tier.
- **Do not deploy.** Every task ends with a commit, never a `git push`. The final section of this plan lists the exact commands the project owner will run themselves.

## Verification approach (read this before Task 1)

This repo has no test framework. Every "verify" step in this plan is one of exactly three kinds, all real commands you actually run, not aspirational placeholders:

1. **Python syntax/import check** — `cd server && python -c "import <module>"` run from `server/`. This sandbox's system Python already has every dependency this project needs (`fastapi`, `asyncpg`, `aiohttp`, `python-dotenv`, etc.) importable with no DB connection required at import time — `db.py` only *defines* a connection pool object, it doesn't connect until `db.connect()` is awaited inside the app lifespan. If `python -c "import X"` fails, something is actually broken; fix it before moving on.
2. **Pure-function assertions** — for the handful of functions with no DB/network dependency (`build_inline_keyboard`, `_normalize_chat_ids`, `_normalize_buttons`), run inline `python -c` scripts with real `assert` statements against the real imported function. These genuinely execute and genuinely fail loudly if wrong.
3. **Frontend build** — `cd admin && npx vite build --logLevel warn`. Silent output = success; any output = read it, it's an error.

What this plan **cannot** verify in this environment: actual DB writes/reads (no live Postgres here), actual Telegram API calls (would hit real chats), actual browser rendering (no running backend to point the dev server at). Those get verified by the project owner after they deploy — that's an intentional, explicit gap, not an oversight.

---

## File Structure

| File | Responsibility |
|---|---|
| `server/schema.sql` | Modify — append `group_post_campaigns` + `group_post_log` table definitions |
| `server/telegram_notify.py` | Modify — generalize the single-button helper into `build_inline_keyboard()`, add photo-sending (bytes-upload-once + file_id-reuse) |
| `server/group_posts.py` | Create — validation, CRUD, send execution, scheduler-callable entry point (mirrors `server/admin_broadcast.py`'s shape) |
| `server/event_scheduler.py` | Modify — call the new campaign-firing function from the existing 30s `_tick()` |
| `server/admin_routes.py` | Modify — REST endpoints (list/create/update/pause/resume/run-now/delete/log) |
| `admin/src/lib/adminClient.js` | Modify — API client functions + a general multipart-form upload helper |
| `admin/src/pages/sections/GroupPostsPanel.jsx` | Create — campaign list, create/edit form, button-row builder, per-campaign delivery log |
| `admin/src/pages/sections/BroadcastSection.jsx` | Modify — add a two-tab switcher ("Рассылка игрокам" / "Посты в группы") |
| `admin/src/index.css` | Modify — styles for the tab switcher and the button-row builder |

---

### Task 1: Database schema

**Files:**
- Modify: `server/schema.sql` (append at end of file)

**Interfaces:**
- Produces: tables `group_post_campaigns` (columns: `id, admin_user_id, label, chat_ids, telegram_text, photo_bytes, photo_mime, photo_file_id, buttons_json, interval_minutes, status, next_fire_at, total_sent, last_error, created_at, updated_at`) and `group_post_log` (columns: `id, campaign_id, chat_id, status, fail_reason, created_at`), both auto-applied on next server start (see `server/db.py:226`, which executes the whole `schema.sql` file on every boot).

- [ ] **Step 1: Append the new tables to `server/schema.sql`**

Open `server/schema.sql`, scroll to the very end of the file, and append:

```sql

-- Циклические посты в группы (см. docs/superpowers/specs/2026-07-15-group-post-campaigns-design.md).
-- Без FK на существующие таблицы намеренно — см. broadcast_recipients выше и
-- инцидент 2026-07-15 (InvalidForeignKeyError уронил старт всего api).
CREATE TABLE IF NOT EXISTS group_post_campaigns (
    id BIGSERIAL PRIMARY KEY,
    admin_user_id BIGINT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    chat_ids BIGINT[] NOT NULL,
    telegram_text TEXT NOT NULL DEFAULT '',
    photo_bytes BYTEA,
    photo_mime TEXT,
    photo_file_id TEXT,
    buttons_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    interval_minutes INT NOT NULL CHECK (interval_minutes >= 1),
    status TEXT NOT NULL DEFAULT 'active',
    next_fire_at TIMESTAMPTZ,
    total_sent INT NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS group_post_campaigns_active_idx
    ON group_post_campaigns (next_fire_at) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS group_post_log (
    id BIGSERIAL PRIMARY KEY,
    campaign_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    status TEXT NOT NULL,
    fail_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS group_post_log_campaign_idx
    ON group_post_log (campaign_id, id);
```

- [ ] **Step 2: Review checklist (no automated SQL check available — see "Verification approach")**

Manually confirm, reading the appended block:
- Every `CREATE TABLE` / `CREATE INDEX` has `IF NOT EXISTS`.
- Neither table has a `REFERENCES` clause.
- `interval_minutes` has a `CHECK (>= 1)` so a bad request can never create a zero/negative-interval campaign at the DB layer, not just in application code.

- [ ] **Step 3: Commit**

```bash
git add server/schema.sql
git commit -m "feat(server): add group_post_campaigns/group_post_log tables"
```

---

### Task 2: Generic inline keyboard + photo sending in `telegram_notify.py`

**Files:**
- Modify: `server/telegram_notify.py`

**Interfaces:**
- Consumes: `TelegramSendResult` dataclass (already exists, from the 2026-07-15 broadcast-reliability fix), `BOT_TOKEN` from `config`.
- Produces:
  - `build_inline_keyboard(rows: list[list[dict]]) -> str | None` — `rows` is `[[{"text": str, "url": str, "type": "url"|"web_app"}, ...], ...]`; returns a JSON string for Telegram's `reply_markup` field, or `None` if every row/button was filtered out as invalid.
  - `send_telegram_photo_bytes(photo_bytes: bytes, *, chat_id: str, caption: str = "", filename: str = "photo.jpg", content_type: str = "image/jpeg", token: str | None = None, buttons: list[list[dict]] | None = None) -> TelegramSendResult` — `TelegramSendResult.file_id` is populated on success.
  - `send_telegram_photo_by_file_id(file_id: str, *, chat_id: str, caption: str = "", token: str | None = None, buttons: list[list[dict]] | None = None) -> TelegramSendResult`
  - `send_telegram_message(...)` gains a new optional `buttons: list[list[dict]] | None = None` kwarg — when given, it takes priority over the existing `cta_text`/`cta_url` pair (which keeps working unchanged for existing callers in `admin_broadcast.py`).
  - `TelegramSendResult` gains a new field `file_id: str | None = None`.

- [ ] **Step 1: Replace the whole file**

`server/telegram_notify.py` currently ends right after `send_telegram_message` (the async wrapper). Read the current file first to confirm nothing else was added since 2026-07-15 (it shouldn't have been — this is the only place group posts touch it), then replace its full contents with:

```python
"""Отправка сообщений в Telegram (группа + тема)."""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from config import BOT_TOKEN

logger = logging.getLogger("cute-farm.telegram")


@dataclass
class TelegramSendResult:
    """Итог попытки отправки. ok=False не бросает исключение - вызывающий код
    сам решает, критично ли это (для рассылок - да, для fire-and-forget
    уведомлений - обычно нет)."""

    ok: bool
    category: str | None = None  # "blocked" | "chat_not_found" | "deactivated" | "rate_limited" | "other"
    error_code: int | None = None
    description: str | None = None
    file_id: str | None = None  # заполняется на успешный sendPhoto с сырыми байтами


def _classify_error(error_code: int | None, description: str) -> str:
    desc = (description or "").lower()
    if error_code == 403 and "deactivated" in desc:
        return "deactivated"
    if error_code == 403:
        return "blocked"
    if error_code == 400 and ("chat not found" in desc or "user not found" in desc):
        return "chat_not_found"
    if error_code == 429:
        return "rate_limited"
    return "other"


def build_inline_keyboard(rows: list[list[dict]]) -> str | None:
    """rows: [[{"text": str, "url": str, "type": "url"|"web_app"}, ...], ...].
    Пустые/невалидные строки и кнопки без text/url молча пропускаются - вызывающий
    код (group_posts.py) уже провалидировал структуру при сохранении, здесь -
    последняя защита перед отправкой в Telegram. Возвращает JSON для
    reply_markup или None, если после фильтрации кнопок не осталось."""
    keyboard: list[list[dict]] = []
    for row in rows or []:
        buttons = []
        for btn in row or []:
            text = str((btn or {}).get("text") or "").strip()
            url = str((btn or {}).get("url") or "").strip()
            if not text or not url:
                continue
            if (btn or {}).get("type") == "web_app":
                buttons.append({"text": text, "web_app": {"url": url}})
            else:
                buttons.append({"text": text, "url": url})
        if buttons:
            keyboard.append(buttons)
    if not keyboard:
        return None
    return json.dumps({"inline_keyboard": keyboard})


def _webapp_button_markup(cta_text: str, cta_url: str) -> str | None:
    """Инлайн-кнопка с web_app - открывает вебапп прямо в Telegram, не во внешнем
    браузере. Работает только в личке с ботом (что и есть кейс DM-рассылок -
    chat_id=user_id)."""
    return build_inline_keyboard([[{"text": cta_text, "url": cta_url, "type": "web_app"}]])


def send_telegram_message_sync(
    text: str,
    *,
    chat_id: str,
    thread_id: int | None = None,
    token: str | None = None,
    cta_text: str | None = None,
    cta_url: str | None = None,
    buttons: list[list[dict]] | None = None,
) -> TelegramSendResult:
    bot_token = token or BOT_TOKEN
    if not bot_token or not chat_id:
        return TelegramSendResult(ok=False, category="other", description="Missing bot token or chat_id")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    if thread_id is not None:
        payload["message_thread_id"] = str(thread_id)
    reply_markup = build_inline_keyboard(buttons) if buttons else None
    if reply_markup is None and cta_text and cta_url:
        reply_markup = _webapp_button_markup(cta_text, cta_url)
    if reply_markup:
        payload["reply_markup"] = reply_markup
    body = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            response.read()
        return TelegramSendResult(ok=True)
    except urllib.error.HTTPError as exc:
        error_code = exc.code
        description = str(exc)
        try:
            raw = exc.read()
            parsed = json.loads(raw) if raw else {}
            error_code = int(parsed.get("error_code", error_code))
            description = str(parsed.get("description", description))
        except Exception:
            pass
        category = _classify_error(error_code, description)
        logger.warning(
            "Telegram HTTP error (chat_id=%s): %s %s", chat_id, error_code, description
        )
        return TelegramSendResult(ok=False, category=category, error_code=error_code, description=description)
    except Exception as exc:
        logger.exception("Telegram send failed (chat_id=%s)", chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))


async def send_telegram_message(
    text: str,
    *,
    chat_id: str,
    thread_id: int | None = None,
    token: str | None = None,
    cta_text: str | None = None,
    cta_url: str | None = None,
    buttons: list[list[dict]] | None = None,
) -> TelegramSendResult:
    try:
        return await asyncio.to_thread(
            send_telegram_message_sync,
            text,
            chat_id=chat_id,
            thread_id=thread_id,
            token=token,
            cta_text=cta_text,
            cta_url=cta_url,
            buttons=buttons,
        )
    except Exception as exc:
        logger.exception("Telegram send failed (chat_id=%s)", chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))


async def send_telegram_photo_bytes(
    photo_bytes: bytes,
    *,
    chat_id: str,
    caption: str = "",
    filename: str = "photo.jpg",
    content_type: str = "image/jpeg",
    token: str | None = None,
    buttons: list[list[dict]] | None = None,
) -> TelegramSendResult:
    """Первая отправка фото кампании - грузит бинарник в Telegram, возвращает
    file_id (в TelegramSendResult.file_id) для дальнейшего переиспользования
    без реаплоада, см. send_telegram_photo_by_file_id. Использует aiohttp, как
    уже существующий server/admin_routes.py::_upload_photo_to_telegram - здесь
    реальная загрузка файла, не просто форма, urllib для этого неудобен."""
    import aiohttp

    bot_token = token or BOT_TOKEN
    if not bot_token or not chat_id:
        return TelegramSendResult(ok=False, category="other", description="Missing bot token or chat_id")

    data = aiohttp.FormData()
    data.add_field("chat_id", chat_id)
    if caption:
        data.add_field("caption", caption)
        data.add_field("parse_mode", "HTML")
    reply_markup = build_inline_keyboard(buttons or [])
    if reply_markup:
        data.add_field("reply_markup", reply_markup)
    data.add_field("photo", photo_bytes, filename=filename, content_type=content_type)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                data=data,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                result = await resp.json()
    except Exception as exc:
        logger.exception("Telegram sendPhoto (bytes) failed (chat_id=%s)", chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))

    if not result.get("ok"):
        error_code = result.get("error_code")
        description = result.get("description", "")
        category = _classify_error(error_code, description)
        logger.warning("Telegram sendPhoto error (chat_id=%s): %s %s", chat_id, error_code, description)
        return TelegramSendResult(ok=False, category=category, error_code=error_code, description=description)

    sizes = result.get("result", {}).get("photo", [])
    file_id = sizes[-1]["file_id"] if sizes else None
    return TelegramSendResult(ok=True, file_id=file_id)


def send_telegram_photo_by_file_id_sync(
    file_id: str,
    *,
    chat_id: str,
    caption: str = "",
    token: str | None = None,
    buttons: list[list[dict]] | None = None,
) -> TelegramSendResult:
    """Повторные отправки того же фото - без реаплоада, обычный form-post как
    у send_telegram_message_sync (photo=file_id - это просто текстовое поле,
    не файл)."""
    bot_token = token or BOT_TOKEN
    if not bot_token or not chat_id:
        return TelegramSendResult(ok=False, category="other", description="Missing bot token or chat_id")

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": file_id}
    if caption:
        payload["caption"] = caption
        payload["parse_mode"] = "HTML"
    reply_markup = build_inline_keyboard(buttons or [])
    if reply_markup:
        payload["reply_markup"] = reply_markup
    body = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            response.read()
        return TelegramSendResult(ok=True, file_id=file_id)
    except urllib.error.HTTPError as exc:
        error_code = exc.code
        description = str(exc)
        try:
            raw = exc.read()
            parsed = json.loads(raw) if raw else {}
            error_code = int(parsed.get("error_code", error_code))
            description = str(parsed.get("description", description))
        except Exception:
            pass
        category = _classify_error(error_code, description)
        logger.warning("Telegram sendPhoto error (chat_id=%s): %s %s", chat_id, error_code, description)
        return TelegramSendResult(ok=False, category=category, error_code=error_code, description=description)
    except Exception as exc:
        logger.exception("Telegram sendPhoto (file_id) failed (chat_id=%s)", chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))


async def send_telegram_photo_by_file_id(
    file_id: str,
    *,
    chat_id: str,
    caption: str = "",
    token: str | None = None,
    buttons: list[list[dict]] | None = None,
) -> TelegramSendResult:
    try:
        return await asyncio.to_thread(
            send_telegram_photo_by_file_id_sync,
            file_id,
            chat_id=chat_id,
            caption=caption,
            token=token,
            buttons=buttons,
        )
    except Exception as exc:
        logger.exception("Telegram sendPhoto (file_id) failed (chat_id=%s)", chat_id)
        return TelegramSendResult(ok=False, category="other", description=str(exc))
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
cd server && python -c "import telegram_notify; print('import OK')"
```
Expected: `import OK`

- [ ] **Step 3: Verify `build_inline_keyboard` behavior with real assertions**

```bash
cd server && python -c "
from telegram_notify import build_inline_keyboard
import json

assert build_inline_keyboard([]) is None
assert build_inline_keyboard([[]]) is None
assert build_inline_keyboard([[{'text': '', 'url': 'https://x'}]]) is None
assert build_inline_keyboard([[{'text': 'x', 'url': ''}]]) is None

result = build_inline_keyboard([
    [{'text': 'Open', 'url': 'https://a', 'type': 'web_app'}],
    [{'text': 'A', 'url': 'https://b'}, {'text': 'B', 'url': 'https://c', 'type': 'url'}],
])
parsed = json.loads(result)
assert parsed == {
    'inline_keyboard': [
        [{'text': 'Open', 'web_app': {'url': 'https://a'}}],
        [{'text': 'A', 'url': 'https://b'}, {'text': 'B', 'url': 'https://c'}],
    ]
}, parsed
print('build_inline_keyboard OK')
"
```
Expected: `build_inline_keyboard OK`

- [ ] **Step 4: Verify existing DM-broadcast CTA behavior still works (regression check)**

`admin_broadcast.py` calls `send_telegram_message(..., cta_text=..., cta_url=...)` with no `buttons` kwarg — confirm that path still builds a single web_app button, unchanged from before this task:

```bash
cd server && python -c "
from telegram_notify import _webapp_button_markup
import json
result = json.loads(_webapp_button_markup('Открыть', 'https://example.com'))
assert result == {'inline_keyboard': [[{'text': 'Открыть', 'web_app': {'url': 'https://example.com'}}]]}, result
print('CTA regression OK')
"
```
Expected: `CTA regression OK`

- [ ] **Step 5: Commit**

```bash
git add server/telegram_notify.py
git commit -m "feat(server): generic inline keyboard builder + photo sending in telegram_notify"
```

---

### Task 3: `server/group_posts.py` — validation + CRUD

**Files:**
- Create: `server/group_posts.py`

**Interfaces:**
- Consumes: `db` from `db.py` (`db.pool` — asyncpg pool, already connected by the time any of these functions run inside a request).
- Produces (used by Task 4 and Task 5):
  - `_normalize_chat_ids(raw: str | list) -> list[int]` — raises `ValueError` on bad input.
  - `_normalize_buttons(raw: list) -> list[list[dict]]` — never raises, silently drops invalid buttons/rows.
  - `_campaign_row(row) -> dict` — asyncpg Record → JSON-friendly dict (camelCase keys).
  - `async def list_campaigns() -> list[dict]`
  - `async def get_campaign(campaign_id: int) -> dict | None`
  - `async def create_campaign(*, admin_user_id: int, label: str, chat_ids, telegram_text: str, buttons: list | None, interval_minutes: int, photo_bytes: bytes | None = None, photo_mime: str | None = None) -> dict` — raises `ValueError` on bad input.
  - `async def update_campaign(campaign_id: int, *, label=None, chat_ids=None, telegram_text=None, buttons=None, interval_minutes=None, photo_bytes=None, photo_mime=None, clear_photo=False) -> dict` — raises `ValueError`.
  - `async def set_campaign_status(campaign_id: int, status: str) -> dict` — `status` must be `"active"` or `"paused"`, raises `ValueError` otherwise or if not found.
  - `async def delete_campaign(campaign_id: int) -> None` — raises `ValueError` if not found.

- [ ] **Step 1: Write the file**

```python
"""Admin: циклические посты в группы проекта (см.
docs/superpowers/specs/2026-07-15-group-post-campaigns-design.md)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from db import db

logger = logging.getLogger("cute-farm.admin.group_posts")

_UTC = timezone.utc


def _normalize_chat_ids(raw: Any) -> list[int]:
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.replace(",", "\n").split("\n")]
    else:
        parts = [str(p).strip() for p in (raw or [])]
    ids: list[int] = []
    for part in parts:
        if not part:
            continue
        try:
            cid = int(part)
        except ValueError:
            raise ValueError(f"Некорректный chat_id: {part!r}")
        if cid not in ids:
            ids.append(cid)
    if not ids:
        raise ValueError("Укажите хотя бы одну группу (chat_id)")
    return ids


def _normalize_buttons(raw: Any) -> list[list[dict]]:
    rows: list[list[dict]] = []
    for row in raw or []:
        buttons: list[dict] = []
        for btn in row or []:
            text = str((btn or {}).get("text") or "").strip()
            url = str((btn or {}).get("url") or "").strip()
            btn_type = (btn or {}).get("type") or "url"
            if not text or not url:
                continue
            if btn_type not in ("url", "web_app"):
                btn_type = "url"
            buttons.append({"text": text[:64], "url": url[:512], "type": btn_type})
        if buttons:
            rows.append(buttons)
    return rows


def _campaign_row(row) -> dict:
    buttons = row["buttons_json"]
    if isinstance(buttons, str):
        buttons = json.loads(buttons) if buttons else []
    return {
        "id": int(row["id"]),
        "adminUserId": int(row["admin_user_id"]),
        "label": row["label"] or "",
        "chatIds": list(row["chat_ids"] or []),
        "telegramText": row["telegram_text"] or "",
        "hasPhoto": row["photo_bytes"] is not None,
        "buttons": buttons or [],
        "intervalMinutes": int(row["interval_minutes"]),
        "status": row["status"],
        "nextFireAt": row["next_fire_at"].isoformat() if row["next_fire_at"] else None,
        "totalSent": int(row["total_sent"] or 0),
        "lastError": row["last_error"],
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


_CAMPAIGN_FIELDS = """
    id, admin_user_id, label, chat_ids, telegram_text, photo_bytes, photo_mime,
    photo_file_id, buttons_json, interval_minutes, status, next_fire_at,
    total_sent, last_error, created_at, updated_at
"""


async def list_campaigns() -> list[dict]:
    rows = await db.pool.fetch(
        f"SELECT {_CAMPAIGN_FIELDS} FROM group_post_campaigns ORDER BY created_at DESC"
    )
    return [_campaign_row(r) for r in rows]


async def get_campaign(campaign_id: int) -> dict | None:
    row = await db.pool.fetchrow(
        f"SELECT {_CAMPAIGN_FIELDS} FROM group_post_campaigns WHERE id = $1", campaign_id
    )
    return _campaign_row(row) if row else None


async def create_campaign(
    *,
    admin_user_id: int,
    label: str,
    chat_ids: Any,
    telegram_text: str,
    buttons: list | None,
    interval_minutes: int,
    photo_bytes: bytes | None = None,
    photo_mime: str | None = None,
) -> dict:
    ids = _normalize_chat_ids(chat_ids)
    btns = _normalize_buttons(buttons or [])
    text_clean = (telegram_text or "").strip()
    if not text_clean and not photo_bytes:
        raise ValueError("Укажите текст поста или фото")
    if interval_minutes < 1:
        raise ValueError("Интервал должен быть не меньше 1 минуты")

    row = await db.pool.fetchrow(
        """
        INSERT INTO group_post_campaigns (
            admin_user_id, label, chat_ids, telegram_text, photo_bytes, photo_mime,
            buttons_json, interval_minutes, status
        )
        VALUES ($1, $2, $3::bigint[], $4, $5, $6, $7::jsonb, $8, 'active')
        RETURNING id
        """,
        admin_user_id,
        (label or "").strip()[:120],
        ids,
        text_clean,
        photo_bytes,
        photo_mime,
        json.dumps(btns, ensure_ascii=False),
        int(interval_minutes),
    )
    return await get_campaign(int(row["id"]))


async def update_campaign(
    campaign_id: int,
    *,
    label: str | None = None,
    chat_ids: Any = None,
    telegram_text: str | None = None,
    buttons: list | None = None,
    interval_minutes: int | None = None,
    photo_bytes: bytes | None = None,
    photo_mime: str | None = None,
    clear_photo: bool = False,
) -> dict:
    existing = await get_campaign(campaign_id)
    if not existing:
        raise ValueError("Кампания не найдена")

    sets: list[str] = []
    params: list[Any] = []
    idx = 1

    def add(field: str, value: Any, cast: str = "") -> None:
        nonlocal idx
        sets.append(f"{field} = ${idx}{cast}")
        params.append(value)
        idx += 1

    if label is not None:
        add("label", label.strip()[:120])
    if chat_ids is not None:
        add("chat_ids", _normalize_chat_ids(chat_ids), "::bigint[]")
    if telegram_text is not None:
        add("telegram_text", telegram_text.strip())
    if buttons is not None:
        add("buttons_json", json.dumps(_normalize_buttons(buttons), ensure_ascii=False), "::jsonb")
    if interval_minutes is not None:
        if interval_minutes < 1:
            raise ValueError("Интервал должен быть не меньше 1 минуты")
        add("interval_minutes", int(interval_minutes))
    if photo_bytes is not None:
        add("photo_bytes", photo_bytes)
        add("photo_mime", photo_mime)
        add("photo_file_id", None)  # новое фото - сбрасываем кэш file_id
    elif clear_photo:
        add("photo_bytes", None)
        add("photo_mime", None)
        add("photo_file_id", None)

    if not sets:
        return existing

    add("updated_at", datetime.now(_UTC))
    params.append(campaign_id)
    await db.pool.execute(
        f"UPDATE group_post_campaigns SET {', '.join(sets)} WHERE id = ${idx}",
        *params,
    )
    return await get_campaign(campaign_id)


async def set_campaign_status(campaign_id: int, status: str) -> dict:
    if status not in ("active", "paused"):
        raise ValueError("Неверный статус")
    row = await db.pool.fetchrow(
        "UPDATE group_post_campaigns SET status = $2, updated_at = NOW() WHERE id = $1 RETURNING id",
        campaign_id, status,
    )
    if not row:
        raise ValueError("Кампания не найдена")
    return await get_campaign(campaign_id)


async def delete_campaign(campaign_id: int) -> None:
    result = await db.pool.execute("DELETE FROM group_post_campaigns WHERE id = $1", campaign_id)
    if result == "DELETE 0":
        raise ValueError("Кампания не найдена")
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
cd server && python -c "import group_posts; print('import OK')"
```
Expected: `import OK`

- [ ] **Step 3: Verify the two pure validators with real assertions**

```bash
cd server && python -c "
from group_posts import _normalize_chat_ids, _normalize_buttons

assert _normalize_chat_ids('-100123, -100456\n-100123') == [-100123, -100456]

try:
    _normalize_chat_ids('abc')
    raise SystemExit('should have raised on garbage input')
except ValueError:
    pass

try:
    _normalize_chat_ids('')
    raise SystemExit('should have raised on empty input')
except ValueError:
    pass

assert _normalize_buttons([
    [{'text': 'A', 'url': 'https://a'}],
    [{'text': '', 'url': 'https://b'}],
]) == [[{'text': 'A', 'url': 'https://a', 'type': 'url'}]]

assert _normalize_buttons([]) == []
print('validators OK')
"
```
Expected: `validators OK`

- [ ] **Step 4: Commit**

```bash
git add server/group_posts.py
git commit -m "feat(server): group post campaigns - validation and CRUD"
```

---

### Task 4: Sending logic + scheduler wiring

**Files:**
- Modify: `server/group_posts.py` (append)
- Modify: `server/event_scheduler.py`

**Interfaces:**
- Consumes: `send_telegram_message`, `send_telegram_photo_bytes`, `send_telegram_photo_by_file_id` from `telegram_notify.py` (Task 2); `_CAMPAIGN_FIELDS`, `get_campaign` from Task 3.
- Produces: `async def run_campaign_now(campaign_id: int) -> dict` (raises `ValueError` if not found) — returns `{"sent": int, "failed": int, "fileId": str | None}`; `async def list_campaign_log(campaign_id: int, *, limit: int = 50, offset: int = 0) -> dict`; `async def _fire_group_post_campaigns() -> None` — called from `event_scheduler._tick()`.

- [ ] **Step 1: Append sending logic to `server/group_posts.py`**

Add `asyncio` and `timedelta` to the imports at the top of the file:

```python
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from db import db
from telegram_notify import (
    send_telegram_message,
    send_telegram_photo_bytes,
    send_telegram_photo_by_file_id,
)
```

(This replaces the smaller import block from Task 3 — `json`, `logging`, `datetime`/`timezone` stay, `timedelta` and `asyncio` are new, and the two `telegram_notify` imports are new.)

Then append to the end of the file:

```python
TELEGRAM_SEND_DELAY = 0.04  # тот же троттлинг, что у admin_broadcast.py
POST_LOG_FLUSH_SIZE = 100


async def _flush_post_log(campaign_id: int, batch: list[tuple[int, str, str | None]]) -> None:
    """batch: (chat_id, status, fail_reason). Bulk-insert через UNNEST - тот же
    паттерн, что у admin_broadcast.py::_flush_recipient_log."""
    if not batch:
        return
    chat_ids = [b[0] for b in batch]
    statuses = [b[1] for b in batch]
    reasons = [b[2] for b in batch]
    try:
        await db.pool.execute(
            """
            INSERT INTO group_post_log (campaign_id, chat_id, status, fail_reason)
            SELECT $1, c, s, r
            FROM UNNEST($2::bigint[], $3::text[], $4::text[]) AS t(c, s, r)
            """,
            campaign_id, chat_ids, statuses, reasons,
        )
    except Exception:
        logger.exception("Failed to log group post recipients (campaign_id=%s)", campaign_id)


async def _execute_group_post_send(row) -> dict:
    """row: asyncpg Record с полями из _CAMPAIGN_FIELDS. Шлёт пост во все
    chat_ids кампании, возвращает {"sent": int, "failed": int, "fileId": str|None}."""
    campaign_id = int(row["id"])
    chat_ids: list[int] = list(row["chat_ids"] or [])
    text = row["telegram_text"] or ""
    buttons = row["buttons_json"]
    if isinstance(buttons, str):
        buttons = json.loads(buttons) if buttons else []
    photo_bytes = row["photo_bytes"]
    photo_mime = row["photo_mime"] or "image/jpeg"
    file_id = row["photo_file_id"]

    sent = 0
    failed = 0
    log_batch: list[tuple[int, str, str | None]] = []
    new_file_id: str | None = None

    for chat_id in chat_ids:
        if photo_bytes is not None and not file_id and new_file_id is None:
            result = await send_telegram_photo_bytes(
                photo_bytes,
                chat_id=str(chat_id),
                caption=text,
                content_type=photo_mime,
                buttons=buttons,
            )
            if result.ok and result.file_id:
                new_file_id = result.file_id
        elif photo_bytes is not None:
            result = await send_telegram_photo_by_file_id(
                file_id or new_file_id,
                chat_id=str(chat_id),
                caption=text,
                buttons=buttons,
            )
        else:
            result = await send_telegram_message(text, chat_id=str(chat_id), buttons=buttons)

        if result.ok:
            sent += 1
            log_batch.append((chat_id, "sent", None))
        else:
            failed += 1
            log_batch.append((chat_id, "failed", result.category or "other"))

        if len(log_batch) >= POST_LOG_FLUSH_SIZE:
            await _flush_post_log(campaign_id, log_batch)
            log_batch.clear()
        await asyncio.sleep(TELEGRAM_SEND_DELAY)

    await _flush_post_log(campaign_id, log_batch)

    updates = ["total_sent = total_sent + $2", "updated_at = NOW()"]
    params: list[Any] = [campaign_id, sent]
    idx = 3
    if new_file_id:
        updates.append(f"photo_file_id = ${idx}")
        params.append(new_file_id)
        idx += 1
    if failed and failed == len(chat_ids):
        updates.append(f"last_error = ${idx}")
        params.append(f"Не доставлено ни в одну группу ({failed}/{len(chat_ids)})")
        idx += 1
    elif sent:
        updates.append("last_error = NULL")

    await db.pool.execute(
        f"UPDATE group_post_campaigns SET {', '.join(updates)} WHERE id = $1",
        *params,
    )
    return {"sent": sent, "failed": failed, "fileId": new_file_id}


async def _fire_group_post_campaigns() -> None:
    """Вызывается из event_scheduler._tick() каждые 30с."""
    now = datetime.now(_UTC)
    due = await db.pool.fetch(
        """
        SELECT id, interval_minutes, next_fire_at
        FROM group_post_campaigns
        WHERE status = 'active' AND next_fire_at IS NOT NULL AND next_fire_at <= $1
        """,
        now,
    )
    for candidate in due:
        campaign_id = int(candidate["id"])
        interval = int(candidate["interval_minutes"])
        prev_fire_at = candidate["next_fire_at"]
        claimed = await db.pool.fetchrow(
            """
            UPDATE group_post_campaigns
            SET next_fire_at = $3
            WHERE id = $1 AND next_fire_at = $2
            RETURNING id
            """,
            campaign_id, prev_fire_at, now + timedelta(minutes=interval),
        )
        if not claimed:
            continue  # другой тик/воркер уже забрал этот запуск
        row = await db.pool.fetchrow(
            f"SELECT {_CAMPAIGN_FIELDS} FROM group_post_campaigns WHERE id = $1",
            campaign_id,
        )
        if not row or row["status"] != "active":
            continue
        try:
            result = await _execute_group_post_send(row)
            logger.info(
                "Group post campaign fired: id=%s sent=%s failed=%s",
                campaign_id, result["sent"], result["failed"],
            )
        except Exception:
            logger.exception("Group post campaign failed (id=%s)", campaign_id)

    # Кампании без next_fire_at (только что созданные) - выставляем расписание,
    # не стреляем сразу (та же логика, что у ежедневной ротации в admin_broadcast.py).
    fresh = await db.pool.fetch(
        "SELECT id, interval_minutes FROM group_post_campaigns WHERE status = 'active' AND next_fire_at IS NULL"
    )
    for row in fresh:
        await db.pool.execute(
            "UPDATE group_post_campaigns SET next_fire_at = $2 WHERE id = $1 AND next_fire_at IS NULL",
            int(row["id"]), now + timedelta(minutes=int(row["interval_minutes"])),
        )


async def run_campaign_now(campaign_id: int) -> dict:
    """Кнопка «Отправить сейчас» - не трогает next_fire_at."""
    row = await db.pool.fetchrow(
        f"SELECT {_CAMPAIGN_FIELDS} FROM group_post_campaigns WHERE id = $1",
        campaign_id,
    )
    if not row:
        raise ValueError("Кампания не найдена")
    return await _execute_group_post_send(row)


async def list_campaign_log(campaign_id: int, *, limit: int = 50, offset: int = 0) -> dict:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    total = int(
        await db.pool.fetchval(
            "SELECT COUNT(*)::int FROM group_post_log WHERE campaign_id = $1", campaign_id,
        ) or 0
    )
    rows = await db.pool.fetch(
        """
        SELECT chat_id, status, fail_reason, created_at
        FROM group_post_log
        WHERE campaign_id = $1
        ORDER BY id DESC
        LIMIT $2 OFFSET $3
        """,
        campaign_id, limit, offset,
    )
    return {
        "total": total,
        "items": [
            {
                "chatId": int(r["chat_id"]),
                "status": r["status"],
                "failReason": r["fail_reason"],
                "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }
```

- [ ] **Step 2: Verify it still imports cleanly**

```bash
cd server && python -c "import group_posts; print('import OK')"
```
Expected: `import OK`

- [ ] **Step 3: Wire into `server/event_scheduler.py`**

Open `server/event_scheduler.py` and find the `_tick()` function (it currently calls `_fire_scheduled_broadcasts()`, `_fire_daily_rotation_broadcast()`, `_advance_recurring_quests()`, `_send_harvest_notifications()`, then purges old game events). Change it from:

```python
async def _tick() -> None:
    await _fire_scheduled_broadcasts()
    await _fire_daily_rotation_broadcast()
    await _advance_recurring_quests()
    await _send_harvest_notifications()
    from game_events_maintenance import maybe_purge_old_game_events
    await maybe_purge_old_game_events()
```

to:

```python
async def _tick() -> None:
    await _fire_scheduled_broadcasts()
    await _fire_daily_rotation_broadcast()
    await _fire_group_post_campaigns()
    await _advance_recurring_quests()
    await _send_harvest_notifications()
    from game_events_maintenance import maybe_purge_old_game_events
    await maybe_purge_old_game_events()
```

Then add `_fire_group_post_campaigns` as a thin wrapper right after `_tick()` (matching how `_fire_daily_rotation_broadcast` does its import inline to avoid a module-level circular import between `event_scheduler.py` and `group_posts.py`):

```python
async def _fire_group_post_campaigns() -> None:
    from group_posts import _fire_group_post_campaigns as _run
    await _run()
```

(Yes, this means `event_scheduler.py` ends up with a local function and an imported function sharing the same name inside it — that's intentional and matches the existing `_fire_daily_rotation_broadcast` pattern already in this file for `admin_broadcast.start_daily_rotation_broadcast`; keep it consistent rather than renaming one side.)

- [ ] **Step 4: Verify `event_scheduler.py` still imports cleanly**

```bash
cd server && python -c "import event_scheduler; print('import OK')"
```
Expected: `import OK`

- [ ] **Step 5: Commit**

```bash
git add server/group_posts.py server/event_scheduler.py
git commit -m "feat(server): execute + schedule group post campaigns"
```

---

### Task 5: REST endpoints in `admin_routes.py`

**Files:**
- Modify: `server/admin_routes.py`

**Interfaces:**
- Consumes: `create_campaign`, `delete_campaign`, `get_campaign`, `list_campaign_log`, `list_campaigns`, `run_campaign_now`, `set_campaign_status`, `update_campaign` from `group_posts.py` (Tasks 3-4).
- Produces: `GET/POST /admin/api/group-posts`, `PATCH/DELETE /admin/api/group-posts/{id}`, `POST /admin/api/group-posts/{id}/pause`, `/resume`, `/run-now`, `GET /admin/api/group-posts/{id}/log`.

- [ ] **Step 1: Add the import**

Near the top of `server/admin_routes.py`, alongside the existing `from admin_broadcast import (...)` block, add:

```python
from group_posts import (
    create_campaign,
    delete_campaign,
    get_campaign,
    list_campaign_log,
    list_campaigns,
    run_campaign_now,
    set_campaign_status,
    update_campaign,
)
```

- [ ] **Step 2: Add the routes**

Find the end of the existing broadcast routes block (right after the `/broadcast/daily-rotation/run-now` endpoint added 2026-07-15, before `/logs/overview`) and insert:

```python
@router.get("/group-posts")
async def admin_group_posts_list(
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    return {"items": await list_campaigns()}


@router.post("/group-posts")
async def admin_group_posts_create(
    label: str = Form(default=""),
    chat_ids: str = Form(...),
    telegram_text: str = Form(default=""),
    buttons: str = Form(default="[]"),
    interval_minutes: int = Form(...),
    photo: UploadFile | None = File(default=None),
    admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        buttons_data = json.loads(buttons) if buttons else []
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Некорректный формат кнопок")

    photo_bytes = None
    photo_mime = None
    if photo is not None and photo.filename:
        photo_bytes = await photo.read()
        photo_mime = photo.content_type or "image/jpeg"
        if len(photo_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Фото больше 10МБ")

    try:
        return await create_campaign(
            admin_user_id=admin_id,
            label=label,
            chat_ids=chat_ids,
            telegram_text=telegram_text,
            buttons=buttons_data,
            interval_minutes=interval_minutes,
            photo_bytes=photo_bytes,
            photo_mime=photo_mime,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/group-posts/{campaign_id}")
async def admin_group_posts_update(
    campaign_id: int,
    label: str | None = Form(default=None),
    chat_ids: str | None = Form(default=None),
    telegram_text: str | None = Form(default=None),
    buttons: str | None = Form(default=None),
    interval_minutes: int | None = Form(default=None),
    photo: UploadFile | None = File(default=None),
    clear_photo: bool = Form(default=False),
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    buttons_data = None
    if buttons is not None:
        try:
            buttons_data = json.loads(buttons)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Некорректный формат кнопок")

    photo_bytes = None
    photo_mime = None
    if photo is not None and photo.filename:
        photo_bytes = await photo.read()
        photo_mime = photo.content_type or "image/jpeg"
        if len(photo_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Фото больше 10МБ")

    try:
        return await update_campaign(
            campaign_id,
            label=label,
            chat_ids=chat_ids,
            telegram_text=telegram_text,
            buttons=buttons_data,
            interval_minutes=interval_minutes,
            photo_bytes=photo_bytes,
            photo_mime=photo_mime,
            clear_photo=clear_photo,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/group-posts/{campaign_id}/pause")
async def admin_group_posts_pause(
    campaign_id: int,
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        return await set_campaign_status(campaign_id, "paused")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/group-posts/{campaign_id}/resume")
async def admin_group_posts_resume(
    campaign_id: int,
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        return await set_campaign_status(campaign_id, "active")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/group-posts/{campaign_id}/run-now")
async def admin_group_posts_run_now(
    campaign_id: int,
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        return await run_campaign_now(campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/group-posts/{campaign_id}")
async def admin_group_posts_delete(
    campaign_id: int,
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        await delete_campaign(campaign_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/group-posts/{campaign_id}/log")
async def admin_group_posts_log(
    campaign_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    campaign = await get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    return await list_campaign_log(campaign_id, limit=limit, offset=offset)
```

`Form`, `File`, `UploadFile`, `Query`, `HTTPException`, `Depends` and `json` are all already imported at the top of `admin_routes.py` (confirmed — `File`/`Form`/`UploadFile` are used by the existing `/appeals/{appeal_id}/upload` endpoint, `json` is used throughout the broadcast routes). No new imports needed beyond the `group_posts` block from Step 1.

- [ ] **Step 3: Verify it imports cleanly**

```bash
cd server && python -c "import admin_routes; print('import OK')"
```
Expected: `import OK`

- [ ] **Step 4: Commit**

```bash
git add server/admin_routes.py
git commit -m "feat(server): REST endpoints for group post campaigns"
```

---

### Task 6: Admin API client

**Files:**
- Modify: `admin/src/lib/adminClient.js`

**Interfaces:**
- Consumes: existing `adminFetch(path, {method, body})` (JSON requests), existing `_uploadHeaders()` helper (already defined, used by `_uploadFile`).
- Produces: `fetchGroupPostCampaigns()`, `createGroupPostCampaign(fields)`, `updateGroupPostCampaign(id, fields)`, `pauseGroupPostCampaign(id)`, `resumeGroupPostCampaign(id)`, `runGroupPostCampaignNow(id)`, `deleteGroupPostCampaign(id)`, `fetchGroupPostCampaignLog(id, {limit, offset})`.

- [ ] **Step 1: Add a general multipart-form helper next to the existing `_uploadFile`**

Find `_uploadFile` in `admin/src/lib/adminClient.js` (it's specialized for exactly `file` + `text` fields, used by appeal/ticket/evidence uploads). Right after it, add a more general version for arbitrary field sets:

```js
async function _uploadForm(path, method, fields) {
  const form = new FormData()
  for (const [key, value] of Object.entries(fields)) {
    if (value === undefined || value === null) continue
    form.append(key, value)
  }
  const prefix = import.meta.env.VITE_ADMIN_API_PREFIX || '/admin/api'
  const resp = await fetch(`${prefix}${path}`, { method, headers: _uploadHeaders(), body: form })
  if (!resp.ok) { const e = await resp.json().catch(() => ({})); throw new Error(e.detail || 'Ошибка запроса') }
  return resp.json()
}
```

- [ ] **Step 2: Add the group-posts API functions**

At the end of the file, after the existing `saveDailyRotationSettings`/`runDailyRotationNow`/`fetchBroadcastRunRecipients` block, add:

```js
export async function fetchGroupPostCampaigns() {
  return adminFetch('/group-posts')
}

export async function createGroupPostCampaign({ label, chatIds, telegramText, buttons, intervalMinutes, photoFile }) {
  return _uploadForm('/group-posts', 'POST', {
    label: label || '',
    chat_ids: chatIds,
    telegram_text: telegramText || '',
    buttons: JSON.stringify(buttons || []),
    interval_minutes: String(intervalMinutes),
    ...(photoFile ? { photo: photoFile } : {}),
  })
}

export async function updateGroupPostCampaign(campaignId, { label, chatIds, telegramText, buttons, intervalMinutes, photoFile, clearPhoto }) {
  const fields = {}
  if (label !== undefined) fields.label = label
  if (chatIds !== undefined) fields.chat_ids = chatIds
  if (telegramText !== undefined) fields.telegram_text = telegramText
  if (buttons !== undefined) fields.buttons = JSON.stringify(buttons)
  if (intervalMinutes !== undefined) fields.interval_minutes = String(intervalMinutes)
  if (photoFile) fields.photo = photoFile
  if (clearPhoto) fields.clear_photo = 'true'
  return _uploadForm(`/group-posts/${campaignId}`, 'PATCH', fields)
}

export async function pauseGroupPostCampaign(campaignId) {
  return adminFetch(`/group-posts/${campaignId}/pause`, { method: 'POST', body: {} })
}

export async function resumeGroupPostCampaign(campaignId) {
  return adminFetch(`/group-posts/${campaignId}/resume`, { method: 'POST', body: {} })
}

export async function runGroupPostCampaignNow(campaignId) {
  return adminFetch(`/group-posts/${campaignId}/run-now`, { method: 'POST', body: {} })
}

export async function deleteGroupPostCampaign(campaignId) {
  return adminFetch(`/group-posts/${campaignId}`, { method: 'DELETE' })
}

export async function fetchGroupPostCampaignLog(campaignId, { limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  return adminFetch(`/group-posts/${campaignId}/log?${params}`)
}
```

- [ ] **Step 3: Verify the frontend still builds**

```bash
cd admin && npx vite build --logLevel warn
```
Expected: no output (silent success — this build already caught real errors earlier in this project's history, it's not a rubber-stamp check).

- [ ] **Step 4: Commit**

```bash
git add admin/src/lib/adminClient.js
git commit -m "feat(admin): API client for group post campaigns"
```

---

### Task 7: `GroupPostsPanel.jsx`

**Files:**
- Create: `admin/src/pages/sections/GroupPostsPanel.jsx`

**Interfaces:**
- Consumes: every function from Task 6, `AdminActionModal` (existing component, same props as used elsewhere in `BroadcastSection.jsx`: `open, title, description, confirmText, danger, loading, onConfirm, onCancel`).
- Produces: `export default function GroupPostsPanel()` — a fully self-contained component with no required props, mounted by Task 8.

- [ ] **Step 1: Write the file**

```jsx
import { useCallback, useEffect, useState } from 'react'
import AdminActionModal from '../../components/AdminActionModal'
import {
  createGroupPostCampaign,
  deleteGroupPostCampaign,
  fetchGroupPostCampaignLog,
  fetchGroupPostCampaigns,
  pauseGroupPostCampaign,
  resumeGroupPostCampaign,
  runGroupPostCampaignNow,
  updateGroupPostCampaign,
} from '../../lib/adminClient'

const FAIL_REASON_LABEL = {
  blocked: 'бота удалили/кикнули из группы',
  chat_not_found: 'группа не найдена',
  deactivated: 'группа недоступна',
  rate_limited: 'лимит Telegram (повторится позже)',
  other: 'другая ошибка',
}

function formatDate(iso) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('ru-RU')
  } catch {
    return iso
  }
}

function ButtonsBuilder({ rows, onChange }) {
  const updateRow = (rowIdx, nextRow) => {
    onChange(rows.map((row, i) => (i === rowIdx ? nextRow : row)))
  }
  const addRow = () => onChange([...rows, [{ text: '', url: '', type: 'url' }]])
  const removeRow = (rowIdx) => onChange(rows.filter((_, i) => i !== rowIdx))
  const addButton = (rowIdx) => updateRow(rowIdx, [...rows[rowIdx], { text: '', url: '', type: 'url' }])
  const removeButton = (rowIdx, btnIdx) => updateRow(rowIdx, rows[rowIdx].filter((_, i) => i !== btnIdx))
  const updateButton = (rowIdx, btnIdx, field, value) => {
    updateRow(rowIdx, rows[rowIdx].map((btn, i) => (i === btnIdx ? { ...btn, [field]: value } : btn)))
  }

  return (
    <div className="panel-grouppost-buttons">
      {rows.map((row, rowIdx) => (
        <div key={rowIdx} className="panel-grouppost-button-row">
          {row.map((btn, btnIdx) => (
            <div key={btnIdx} className="panel-grouppost-button">
              <input
                className="panel-users-input"
                placeholder="Текст кнопки"
                value={btn.text}
                onChange={(e) => updateButton(rowIdx, btnIdx, 'text', e.target.value)}
              />
              <input
                className="panel-users-input"
                placeholder="https://..."
                value={btn.url}
                onChange={(e) => updateButton(rowIdx, btnIdx, 'url', e.target.value)}
              />
              <select
                className="panel-users-input"
                value={btn.type}
                onChange={(e) => updateButton(rowIdx, btnIdx, 'type', e.target.value)}
              >
                <option value="url">Ссылка</option>
                <option value="web_app">WebApp</option>
              </select>
              <button type="button" className="panel-users-btn panel-users-btn-danger" onClick={() => removeButton(rowIdx, btnIdx)}>
                ✕
              </button>
            </div>
          ))}
          <div className="panel-grouppost-row-actions">
            <button type="button" className="panel-users-btn panel-users-btn-sm" onClick={() => addButton(rowIdx)}>
              + кнопка в ряд
            </button>
            <button type="button" className="panel-users-btn panel-users-btn-sm panel-users-btn-danger" onClick={() => removeRow(rowIdx)}>
              Убрать ряд
            </button>
          </div>
        </div>
      ))}
      <button type="button" className="panel-users-btn" onClick={addRow}>
        + новый ряд кнопок
      </button>
    </div>
  )
}

function CampaignLog({ campaignId }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)

  const load = useCallback(async ({ append = false, offset = 0 } = {}) => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchGroupPostCampaignLog(campaignId, { limit: 50, offset })
      setTotal(data.total ?? 0)
      setItems((prev) => (append ? [...prev, ...(data.items || [])] : data.items || []))
      setLoaded(true)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить историю')
    } finally {
      setLoading(false)
    }
  }, [campaignId])

  useEffect(() => {
    if (!loaded && !loading) load({ offset: 0 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, loading])

  return (
    <div className="panel-grouppost-log">
      {error && <p className="panel-shelf-error">{error}</p>}
      {loading && items.length === 0 && <p className="panel-shelf-muted">Загрузка…</p>}
      {!loading && loaded && items.length === 0 && <p className="panel-shelf-muted">Пока пусто</p>}
      {items.length > 0 && (
        <ul className="panel-broadcast-recipients-list">
          {items.map((item, i) => (
            <li key={`${item.chatId}-${item.createdAt}-${i}`} className="panel-broadcast-recipient-row">
              <span className="panel-broadcast-recipient-name">Группа {item.chatId}</span>
              <span className="panel-shelf-muted">{formatDate(item.createdAt)}</span>
              <span className={`panel-broadcast-recipient-status panel-broadcast-recipient-status-${item.status}`}>
                {item.status === 'sent' ? 'Доставлено' : 'Ошибка'}
                {item.failReason && ` · ${FAIL_REASON_LABEL[item.failReason] || item.failReason}`}
              </span>
            </li>
          ))}
        </ul>
      )}
      {items.length < total && (
        <button
          type="button"
          className="panel-users-btn panel-broadcast-recipients-more"
          disabled={loading}
          onClick={() => load({ append: true, offset: items.length })}
        >
          {loading ? '…' : `Показать ещё (${items.length}/${total})`}
        </button>
      )}
    </div>
  )
}

function CampaignCard({ campaign, onEdit, onPause, onResume, onDelete, onRunNow, busy, expanded, onToggle }) {
  return (
    <article className={`panel-broadcast-run-card panel-broadcast-run-card-${campaign.status === 'active' ? 'running' : 'pending'}`}>
      <div className="panel-broadcast-run-head">
        <div className="panel-broadcast-run-main">
          <div className="panel-broadcast-run-title-row">
            <span className="panel-broadcast-run-id">#{campaign.id}</span>
            <h4 className="panel-broadcast-run-title">{campaign.label || `Кампания #${campaign.id}`}</h4>
            <span className={`panel-broadcast-status panel-broadcast-status-${campaign.status === 'active' ? 'running' : 'cancelled'}`}>
              {campaign.status === 'active' ? 'Активна' : 'На паузе'}
            </span>
          </div>
          <p className="panel-shelf-muted panel-broadcast-run-meta">
            {campaign.chatIds.length} {campaign.chatIds.length === 1 ? 'группа' : 'групп'}
            {' · '}каждые {campaign.intervalMinutes} мин
            {' · '}отправлено {campaign.totalSent} раз
            {campaign.nextFireAt && ` · след. отправка ${formatDate(campaign.nextFireAt)}`}
          </p>
          {campaign.lastError && <p className="panel-shelf-error">{campaign.lastError}</p>}
        </div>
        <div className="panel-broadcast-run-actions">
          {campaign.status === 'active' ? (
            <button type="button" className="panel-users-btn" disabled={busy} onClick={() => onPause(campaign)}>Пауза</button>
          ) : (
            <button type="button" className="panel-users-btn" disabled={busy} onClick={() => onResume(campaign)}>Возобновить</button>
          )}
          <button type="button" className="panel-users-btn" disabled={busy} onClick={() => onRunNow(campaign)}>▶ Сейчас</button>
          <button type="button" className="panel-users-btn" disabled={busy} onClick={() => onEdit(campaign)}>Изменить</button>
          <button type="button" className="panel-users-btn panel-users-btn-danger" disabled={busy} onClick={() => onDelete(campaign)}>Удалить</button>
          <button type="button" className="panel-users-btn" onClick={onToggle}>{expanded ? 'Свернуть' : 'История'}</button>
        </div>
      </div>
      {expanded && (
        <div className="panel-broadcast-history-details">
          <p className="panel-shelf-label">Текст поста</p>
          <pre className="panel-broadcast-preview-telegram">{campaign.telegramText || '(пусто, только фото)'}</pre>
          {campaign.hasPhoto && <p className="panel-shelf-muted">📷 Фото прикреплено</p>}
          <p className="panel-shelf-label">История отправок</p>
          <CampaignLog campaignId={campaign.id} />
        </div>
      )}
    </article>
  )
}

const emptyForm = {
  label: '',
  chatIdsText: '',
  telegramText: '',
  buttons: [],
  intervalMinutes: '10',
  photoFile: null,
  clearPhoto: false,
}

export default function GroupPostsPanel() {
  const [campaigns, setCampaigns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [expandedId, setExpandedId] = useState(null)

  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try {
      const data = await fetchGroupPostCampaigns()
      setCampaigns(data.items || [])
    } catch (err) {
      setError(err.message || 'Не удалось загрузить кампании')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setEditingId(null)
    setForm(emptyForm)
    setFormOpen(true)
  }

  const openEdit = (campaign) => {
    setEditingId(campaign.id)
    setForm({
      label: campaign.label,
      chatIdsText: campaign.chatIds.join(', '),
      telegramText: campaign.telegramText,
      buttons: campaign.buttons,
      intervalMinutes: String(campaign.intervalMinutes),
      photoFile: null,
      clearPhoto: false,
    })
    setFormOpen(true)
  }

  const handleSave = async () => {
    const interval = Number(form.intervalMinutes)
    if (!Number.isFinite(interval) || interval < 1) {
      setError('Интервал должен быть не меньше 1 минуты')
      return
    }
    if (!form.chatIdsText.trim()) {
      setError('Укажите хотя бы одну группу')
      return
    }
    setSaving(true)
    setError('')
    try {
      if (editingId) {
        await updateGroupPostCampaign(editingId, {
          label: form.label,
          chatIds: form.chatIdsText,
          telegramText: form.telegramText,
          buttons: form.buttons,
          intervalMinutes: interval,
          photoFile: form.photoFile,
          clearPhoto: form.clearPhoto,
        })
        setInfo('Кампания обновлена')
      } else {
        await createGroupPostCampaign({
          label: form.label,
          chatIds: form.chatIdsText,
          telegramText: form.telegramText,
          buttons: form.buttons,
          intervalMinutes: interval,
          photoFile: form.photoFile,
        })
        setInfo('Кампания создана')
      }
      setFormOpen(false)
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось сохранить кампанию')
    } finally {
      setSaving(false)
    }
  }

  const handlePause = async (campaign) => {
    setBusyId(campaign.id)
    setError('')
    try {
      await pauseGroupPostCampaign(campaign.id)
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось поставить на паузу')
    } finally {
      setBusyId(null)
    }
  }

  const handleResume = async (campaign) => {
    setBusyId(campaign.id)
    setError('')
    try {
      await resumeGroupPostCampaign(campaign.id)
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось возобновить')
    } finally {
      setBusyId(null)
    }
  }

  const handleRunNow = async (campaign) => {
    setBusyId(campaign.id)
    setError('')
    setInfo('')
    try {
      const result = await runGroupPostCampaignNow(campaign.id)
      setInfo(`Отправлено сейчас: успешно ${result.sent}, ошибок ${result.failed}`)
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось отправить')
    } finally {
      setBusyId(null)
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    setError('')
    try {
      await deleteGroupPostCampaign(deleteTarget.id)
      setDeleteTarget(null)
      setInfo('Кампания удалена')
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось удалить')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="panel-broadcast">
      <AdminActionModal
        open={deleteTarget != null}
        title={`Удалить кампанию «${deleteTarget?.label || deleteTarget?.id}»?`}
        description="Циклическая отправка остановится немедленно. Действие необратимо."
        confirmText="Удалить"
        danger
        loading={deleting}
        onConfirm={confirmDelete}
        onCancel={() => { if (!deleting) setDeleteTarget(null) }}
      />

      <article className="panel-shelf panel-shelf-page">
        <p className="panel-shelf-label">Group Posts · Посты в группы</p>
        <h2 className="panel-page-title">Циклические посты в группы</h2>
        <p className="panel-page-lead">Текст + фото + кнопки, на повторяющемся интервале, в выбранные chat_id</p>
        {error && <p className="panel-shelf-error">{error}</p>}
        {info && <p className="panel-users-info">{info}</p>}
        <button type="button" className="panel-users-btn panel-users-btn-primary" onClick={openCreate}>
          + Новая кампания
        </button>
      </article>

      {formOpen && (
        <article className="panel-shelf">
          <p className="panel-shelf-label">{editingId ? `Кампания #${editingId}` : 'Новая кампания'}</p>
          <div className="panel-economy-settings-form">
            <label className="panel-economy-field">
              <span>Название (для себя)</span>
              <input className="panel-users-input" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} maxLength={120} />
            </label>
            <label className="panel-economy-field">
              <span>Группы (chat_id через запятую или с новой строки)</span>
              <textarea className="panel-users-input panel-broadcast-textarea" value={form.chatIdsText} onChange={(e) => setForm({ ...form, chatIdsText: e.target.value })} rows={2} />
            </label>
            <label className="panel-economy-field">
              <span>Текст поста (HTML)</span>
              <textarea className="panel-users-input panel-broadcast-textarea" value={form.telegramText} onChange={(e) => setForm({ ...form, telegramText: e.target.value })} rows={4} maxLength={2000} />
            </label>
            <label className="panel-economy-field">
              <span>Фото (необязательно)</span>
              <input type="file" accept="image/*" onChange={(e) => setForm({ ...form, photoFile: e.target.files?.[0] || null })} />
            </label>
            {editingId && (
              <label className="panel-market-check">
                <input type="checkbox" checked={form.clearPhoto} onChange={(e) => setForm({ ...form, clearPhoto: e.target.checked })} />
                Убрать текущее фото
              </label>
            )}
            <label className="panel-economy-field">
              <span>Кнопки</span>
              <ButtonsBuilder rows={form.buttons} onChange={(buttons) => setForm({ ...form, buttons })} />
            </label>
            <label className="panel-economy-field">
              <span>Интервал (минуты)</span>
              <input className="panel-users-input" value={form.intervalMinutes} onChange={(e) => setForm({ ...form, intervalMinutes: e.target.value.replace(/[^\d]/g, '') })} maxLength={6} />
            </label>
            <div className="panel-broadcast-rotation-actions">
              <button type="button" className="panel-users-btn panel-users-btn-primary" disabled={saving} onClick={handleSave}>
                {saving ? '…' : editingId ? 'Сохранить изменения' : 'Создать кампанию'}
              </button>
              <button type="button" className="panel-users-btn" disabled={saving} onClick={() => setFormOpen(false)}>
                Отмена
              </button>
            </div>
          </div>
        </article>
      )}

      <article className="panel-shelf">
        <p className="panel-shelf-label">Кампании</p>
        {loading && <p className="panel-shelf-muted">Загрузка…</p>}
        {!loading && campaigns.length === 0 && <p className="panel-shelf-muted">Пока нет кампаний</p>}
        <div className="panel-broadcast-history-list">
          {campaigns.map((campaign) => (
            <CampaignCard
              key={campaign.id}
              campaign={campaign}
              busy={busyId === campaign.id}
              expanded={expandedId === campaign.id}
              onToggle={() => setExpandedId((prev) => (prev === campaign.id ? null : campaign.id))}
              onEdit={openEdit}
              onPause={handlePause}
              onResume={handleResume}
              onRunNow={handleRunNow}
              onDelete={setDeleteTarget}
            />
          ))}
        </div>
      </article>
    </div>
  )
}
```

- [ ] **Step 2: Verify the frontend still builds**

```bash
cd admin && npx vite build --logLevel warn
```
Expected: no output. If it errors, the most likely cause is a typo in a JSX tag or a missing import — read the Vite error, it names the exact file/line.

- [ ] **Step 3: Commit**

```bash
git add admin/src/pages/sections/GroupPostsPanel.jsx
git commit -m "feat(admin): GroupPostsPanel component"
```

---

### Task 8: Wire into `BroadcastSection.jsx` as a second tab + styles

**Files:**
- Modify: `admin/src/pages/sections/BroadcastSection.jsx`
- Modify: `admin/src/index.css`

**Interfaces:**
- Consumes: `GroupPostsPanel` default export from Task 7.

- [ ] **Step 1: Import `GroupPostsPanel` and add tab state**

At the top of `admin/src/pages/sections/BroadcastSection.jsx`, add the import right after the existing `AdminSelect` import:

```js
import GroupPostsPanel from './GroupPostsPanel'
```

Inside `export default function BroadcastSection() {`, right after the line `const [overview, setOverview] = useState(null)` (the very first state declaration), add:

```js
  const [activeTab, setActiveTab] = useState('players')
```

- [ ] **Step 2: Wrap the existing return in a tab switcher**

Find the component's final `return (` — it starts with `<div className="panel-broadcast">` and is immediately followed by the two `<AdminActionModal>` elements (the cancel-run and send-confirm modals). Change:

```jsx
  return (
    <div className="panel-broadcast">
      <AdminActionModal
        open={cancelTarget != null}
```

to:

```jsx
  return (
    <>
      <div className="panel-broadcast-tabs">
        <button
          type="button"
          className={`panel-broadcast-tab-btn${activeTab === 'players' ? ' panel-broadcast-tab-btn-active' : ''}`}
          onClick={() => setActiveTab('players')}
        >
          Рассылка игрокам
        </button>
        <button
          type="button"
          className={`panel-broadcast-tab-btn${activeTab === 'groups' ? ' panel-broadcast-tab-btn-active' : ''}`}
          onClick={() => setActiveTab('groups')}
        >
          Посты в группы
        </button>
      </div>
      {activeTab === 'players' && (
      <div className="panel-broadcast">
      <AdminActionModal
        open={cancelTarget != null}
```

(Deliberately keeping the original indentation of everything below unchanged — only the opening lines shift. Re-indenting the entire ~400-line block is unnecessary churn and makes this diff much harder to review; JSX doesn't care about indentation.)

Then find the very end of the component — the last two lines are:

```jsx
      </article>
    </div>
  )
}
```

Change them to:

```jsx
      </article>
      </div>
      )}
      {activeTab === 'groups' && <GroupPostsPanel />}
    </>
  )
}
```

- [ ] **Step 3: Verify the frontend builds**

```bash
cd admin && npx vite build --logLevel warn
```
Expected: no output. A mismatched JSX tag from Step 2's wrapping is the most likely failure mode here — if it errors, count the opening `<div className="panel-broadcast">` / `<>` against their closing tags first.

- [ ] **Step 4: Add tab-switcher and button-builder CSS**

Open `admin/src/index.css`, find the `.panel-broadcast-run-fail-reasons` rule (added 2026-07-15, right after the `.panel-broadcast-rotation-grid` media query), and add after it:

```css
.panel-broadcast-tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.85rem;
}

.panel-broadcast-tab-btn {
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  font-size: 0.85rem;
}

.panel-broadcast-tab-btn-active {
  border-color: #eab308;
  color: #eab308;
}

.panel-grouppost-buttons {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.panel-grouppost-button-row {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.5rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 0.5rem;
}

.panel-grouppost-button {
  display: grid;
  grid-template-columns: minmax(6rem, 1fr) minmax(8rem, 1.4fr) 7rem auto;
  gap: 0.4rem;
  align-items: center;
}

@media (max-width: 720px) {
  .panel-grouppost-button {
    grid-template-columns: 1fr;
  }
}

.panel-grouppost-row-actions {
  display: flex;
  gap: 0.5rem;
}
```

- [ ] **Step 5: Verify the frontend still builds after the CSS change**

```bash
cd admin && npx vite build --logLevel warn
```
Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add admin/src/pages/sections/BroadcastSection.jsx admin/src/index.css
git commit -m "feat(admin): wire group post campaigns into the Broadcast tab"
```

---

## Self-Review

**Spec coverage** (against `docs/superpowers/specs/2026-07-15-group-post-campaigns-design.md`):
- ✅ Group source only by `chat_id` — `_normalize_chat_ids`, no `chat` table lookups anywhere.
- ✅ Multiple independent simultaneous campaigns — each campaign has its own `next_fire_at`/`interval_minutes`, `_fire_group_post_campaigns` iterates all due ones independently, atomic per-campaign claim.
- ✅ Photo upload-once-reuse-`file_id` — `send_telegram_photo_bytes` / `send_telegram_photo_by_file_id` split, `photo_file_id` cached in Task 3/4.
- ✅ New photo on edit resets cached `file_id` — `update_campaign`'s `if photo_bytes is not None: add("photo_file_id", None)`.
- ✅ Unlimited button rows/buttons, url + web_app types — `ButtonsBuilder`, `_normalize_buttons`.
- ✅ Free-form minute interval — plain `<input>` + `CHECK (interval_minutes >= 1)` at the DB layer too.
- ✅ New message every cycle, no delete-then-repost — `_execute_group_post_send` never issues a delete call.
- ✅ Pause/resume/edit/delete/run-now, per-group delivery log — full CRUD + `group_post_log` + `CampaignLog` viewer.
- ✅ No FK on new tables — verified in Task 1.
- ✅ `require_admin_permission("manage_broadcast")` on every endpoint — Task 5.
- ✅ No deploy — every task step list ends in `git commit`, never `git push`; see the handoff section below for the commands the project owner runs themselves.

**Placeholder scan:** no "TBD"/"add appropriate error handling"/"similar to Task N" found in the task steps above — the multipart-file-handling logic that's repeated between `create` and `update` routes in Task 5 is written out in full both times, not referenced.

**Type consistency check:**
- `TelegramSendResult.file_id` (Task 2) is read as `result.file_id` in `_execute_group_post_send` (Task 4) — matches.
- `buttons_json` is stored via `json.dumps(...)` (Task 3) and read back with an `isinstance(x, str)` guard before `json.loads` in both `_campaign_row` (Task 3) and `_execute_group_post_send` (Task 4) — matches the exact pattern already used for `filter_json`/`channels_json` in `admin_broadcast.py`, so asyncpg returning either a `str` or an already-decoded value (depends on codec registration) is handled either way.
- Frontend field names (`chatIds`, `telegramText`, `intervalMinutes`, `photoFile`, `clearPhoto` in Task 6/7) map 1:1 to what the Task 6 `_uploadForm` calls send as form fields (`chat_ids`, `telegram_text`, `interval_minutes`, `photo`, `clear_photo`), which match the `Form(...)`/`File(...)` parameter names in Task 5's routes exactly.

## Handoff — what YOU run after implementation (no auto-deploy)

Once all 8 tasks are committed locally, review the full diff yourself, then:

```bash
git push origin main
```

That's it — every service in `.do/app.yaml` has `deploy_on_push: true`, so pushing to `main` triggers DigitalOcean to rebuild `api`, `frontend`, and `bots`, and `server/db.py` applies the new `schema.sql` tables automatically on the next `api` container boot (same mechanism as every previous migration in this project).

**After the deploy goes green** (check DO → Activity, same as the 2026-07-15 incident check), do a manual smoke test before trusting it with real groups:
1. Open the admin panel → Рассылка → **Посты в группы** tab.
2. Create a test campaign targeting a throwaway/test group's `chat_id`, interval `1440` (once a day, so it won't actually auto-fire during your test), no photo, one button.
3. Click **▶ Сейчас** and confirm the message actually lands in that group with the button working.
4. Expand **История** on that campaign and confirm the delivery shows up as `Доставлено`.
5. Only after that — create real campaigns with real intervals.
