import time
from telethon.client.users import UserMethods

def install_telethon_logger(client):

    original_call = UserMethods.__call__

    async def patched_call(self, request, ordered=False):

        start = time.perf_counter()

        try:
            result = await original_call(self, request, ordered)

            elapsed = time.perf_counter() - start

            print(
                f"[TELETHON] OK {type(request).__name__} "
                f"{elapsed:.3f}s"
            )

            return result

        except Exception as e:

            elapsed = time.perf_counter() - start

            print(
                f"[TELETHON] ERROR {type(request).__name__} "
                f"{elapsed:.3f}s "
                f"{type(e).__name__}: {e}"
            )

            raise

    UserMethods.__call__ = patched_call