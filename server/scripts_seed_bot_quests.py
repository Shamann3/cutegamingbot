"""Seed recommended TG quest pack via the SAME create_challenge path as admin UI / +заданиеч.

Usage (from server/):
  python scripts_seed_bot_quests.py
"""
from __future__ import annotations

import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except Exception:
    pass


async def main() -> None:
    from db import db
    from admin_bot_quests import seed_recommended_pack

    await db.connect()
    try:
        result = await seed_recommended_pack()
        print("chat:", result.get("chat"))
        print("subTask id:", (result.get("subTask") or {}).get("id"))
        print(
            "created:", result.get("ok"),
            "updated:", result.get("updatedCount"),
            "errors:", result.get("failed"),
        )
        for row in result.get("created") or []:
            print(
                f"  + #{row.get('id')} {row.get('startAmount')}->{row.get('targetAmount')}"
                f" +{row.get('rewardAmount')} free={row.get('free')} chat={row.get('targetChatRef')}"
            )
        for row in result.get("updated") or []:
            print(
                f"  ~ #{row.get('id')} synced {row.get('startAmount')}->{row.get('targetAmount')}"
                f" +{row.get('rewardAmount')} free={row.get('free')} chat={row.get('targetChatRef')}"
            )
        for row in result.get("errors") or []:
            print(f"  ! err {row.get('label')}: {row.get('error')}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
