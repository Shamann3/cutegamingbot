import asyncio
import socket
import aiohttp
from datetime import datetime


async def network_monitor():
    print("🌐 [NETWORK] monitor started")

    timeout = aiohttp.ClientTimeout(total=10)

    while True:
        try:
            ip = socket.gethostbyname("api.telegram.org")

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