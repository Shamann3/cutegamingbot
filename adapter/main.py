import asyncio
import inspect
import os
import runpy
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOCAL_TOKEN_FILE = BASE_DIR / "bot_token.txt"
BRIDGE_SOURCE_MAIN = BASE_DIR.parent.parent / "адаптеррр" / "main.py"


def load_adapter_token() -> str:
    env_token = os.getenv("ADAPTER_BOT_TOKEN", "").strip()
    if env_token:
        return env_token

    if LOCAL_TOKEN_FILE.exists():
        file_token = LOCAL_TOKEN_FILE.read_text(encoding="utf-8").strip()
        if file_token:
            return file_token

    raise RuntimeError(
        "Adapter token is missing. Set ADAPTER_BOT_TOKEN or adapter/bot_token.txt"
    )


def resolve_bridge_source_main() -> Path:
    src_main = BRIDGE_SOURCE_MAIN.resolve()
    if not src_main.exists():
        raise RuntimeError(f"Adapter source is missing: {src_main}")
    return src_main


async def main():
    adapter_token = load_adapter_token()

    # Не даём адаптеру унаследовать токены основного процесса.
    os.environ.pop("BOT_TOKEN", None)
    os.environ.pop("ADAPTER_BOT_TOKEN", None)
    os.environ["BOT_TOKEN"] = adapter_token

    src_main = resolve_bridge_source_main()
    loaded = runpy.run_path(str(src_main))
    bridge_main = loaded.get("main")
    if not callable(bridge_main):
        raise RuntimeError(f"Bridge source has no callable main(): {src_main}")

    result = bridge_main()
    if not inspect.isawaitable(result):
        raise RuntimeError(f"Bridge main() must be async: {src_main}")
    await result


if __name__ == "__main__":
    asyncio.run(main())
