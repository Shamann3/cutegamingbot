import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

import content_registry as cr
import user_items as ui
from dex_catalog import DexEntry, dex_catalog


def setup_mock_dex() -> None:
    entries = [
        ("901284129481212412", "Саженец дерева", "sajeneztree", "\U0001f331"),
        ("124124121424124114", "Топор", "", "\U0001fa93"),
    ]
    dex_catalog._by_id.clear()
    dex_catalog._alias_to_id.clear()
    dex_catalog._alias_lower.clear()
    dex_catalog._by_emoji.clear()
    for item_id, name, name1, emoji in entries:
        entry = DexEntry(id=item_id, name=name, name1=name1, emoji=emoji)
        dex_catalog._by_id[item_id] = entry
        for alias in (item_id, name, name1, emoji):
            if alias:
                dex_catalog._register_alias(alias, item_id)
        if emoji and emoji not in dex_catalog._by_emoji:
            dex_catalog._by_emoji[emoji] = item_id
    dex_catalog.link_farm_item_aliases()


cr._crops = cr._fallback_crops()
setup_mock_dex()
cr._rebuild_indexes()

items = {"124124121424124114": 2, "295": 0}
axe_count = ui.count_item_in_storage(items, "295")
print("axe count via config id:", axe_count)
assert axe_count == 2

items_by_name = {"Топор": 1, "\U0001fa93": 1}
assert ui.count_item_in_storage(items_by_name, "295") == 2

from content_registry import crops_for_client

crops = crops_for_client(items)
tree = next(c for c in crops if c["key"] == "tree")
tool = tree["harvestTool"]
print("harvest tool owned:", tool["owned"], "name:", tool["name"])
assert tool["owned"] is True
assert tool["name"] == "Топор"
print("ok")
