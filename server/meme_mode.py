"""Шанс мемов и список людей, которым мемный режим не включается."""

from admin_soft_restart import is_project_creator

DEFAULT_CHANCE = 10
MAX_EXCLUDED = 200


def clamp_chance(value, default=DEFAULT_CHANCE):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(100, number))


def parse_excluded(raw):
    if isinstance(raw, (list, tuple)):
        parts = raw
    else:
        parts = str(raw or "").replace(",", " ").split()
    found = []
    seen = set()
    for part in parts:
        text = str(part).strip()
        if not text.isdigit():
            continue
        number = int(text)
        if number <= 0 or number in seen:
            continue
        seen.add(number)
        found.append(number)
        if len(found) >= MAX_EXCLUDED:
            break
    return found


def dump_excluded(ids):
    return " ".join(str(item) for item in parse_excluded(ids))


def creator_only(user_id):
    return is_project_creator(int(user_id))


async def read_meme_row():
    import db

    try:
        return await db.pool.fetchrow(
            "SELECT meme_chance, meme_excluded FROM system_settings WHERE id = 1"
        )
    except Exception:
        return None


async def meme_state(user_id):
    row = await read_meme_row()
    chance = clamp_chance(row["meme_chance"] if row else DEFAULT_CHANCE)
    excluded = parse_excluded(row["meme_excluded"] if row else "")
    payload = {
        "chance": chance,
        "exempt": int(user_id) in excluded,
    }
    if creator_only(user_id):
        payload["excludedIds"] = excluded
    return payload


async def save_meme_state(user_id, chance, excluded_ids):
    if not creator_only(user_id):
        return None
    import db

    clean_chance = clamp_chance(chance)
    clean_ids = dump_excluded(excluded_ids)
    await db.pool.execute(
        """
        UPDATE system_settings
        SET meme_chance = $1, meme_excluded = $2, updated_by = $3, updated_at = NOW()
        WHERE id = 1
        """,
        clean_chance,
        clean_ids,
        int(user_id),
    )
    return await meme_state(user_id)
