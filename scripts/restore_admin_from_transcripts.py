"""Extract admin/ files from Cursor agent transcripts (Write tool calls)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT_DIR = Path(
    r"C:\Users\user\.cursor\projects\c-Users-user-Desktop-cutefarmer\agent-transcripts"
)


def normalize_rel(path: str) -> str | None:
    p = path.replace("\\", "/")
    marker = "cutefarmer/"
    if marker not in p.lower():
        return None
    rel = p.split(marker, 1)[1]
    if not rel.startswith("admin/"):
        return None
    return rel


def main() -> None:
    files: dict[str, str] = {}
    for jsonl in TRANSCRIPT_DIR.rglob("*.jsonl"):
        try:
            lines = jsonl.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line in lines:
            if "Write" not in line or "admin" not in line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = obj.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_use" or block.get("name") != "Write":
                    continue
                inp = block.get("input", {})
                path = inp.get("path", "")
                rel = normalize_rel(path)
                if not rel:
                    continue
                body = inp.get("contents", "")
                if body:
                    files[rel] = body

    print(f"Found {len(files)} admin files")
    for rel in sorted(files):
        target = ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[rel], encoding="utf-8", newline="\n")
        print(f"  wrote {rel} ({len(files[rel])} bytes)")


if __name__ == "__main__":
    main()
