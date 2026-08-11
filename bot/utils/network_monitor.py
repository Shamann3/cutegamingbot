import asyncio
import socket
from datetime import datetime

import aiohttp


async def network_monitor():
    """Фоновый пинг Telegram. DNS только в thread — не блокирует event loop."""
    print("🌐 [NETWORK] monitor started")

    timeout = aiohttp.ClientTimeout(total=10)

    while True:
        try:
            # gethostbyname синхронный и может «заморозить» loop на секунды.
            ip = await asyncio.to_thread(socket.gethostbyname, "api.telegram.org")

            start = asyncio.get_running_loop().time()

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://api.telegram.org") as r:
                    dt = asyncio.get_running_loop().time() - start

                    print(
                        f"🌐 [{datetime.now().strftime('%H:%M:%S')}] "
                        f"DNS={ip} "
                        f"status={r.status} "
                        f"time={dt:.3f}s"
                    )

        except Exception as e:
            print(
                f"❌ [{datetime.now().strftime('%H:%M:%S')}] NETWORK ERROR: {repr(e)}"
            )

        await asyncio.sleep(30)
