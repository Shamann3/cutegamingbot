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
        ("124124121424124115", "Саженец табака", "sajeneztabachok", "\U0001f343"),
        ("124125898126", "Бревно", "justtree", "\U0001fab5"),
        ("124124121424124114", "Топор", "", "\U0001fa93"),
        ("124124121424124113", "Вода", "", "\U0001f4a7"),
        ("124124121424124117", "Автополив", "", "\U0001f6b0"),
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
    cr._rebuild_indexes()


cr._crops = cr._fallback_crops()
setup_mock_dex()

cases = [
    {"sajeneztree": 1},
    {"901284129481212412": 2},
    {"299": 1},
    {"Саженец дерева": 1},
    {"\U0001f331": 1},
    {"sajeneztabachok": 1, "296": 1},
    {"Саженец табака": 2},
    {"\U0001f343": 1},
]

for idx, items in enumerate(cases):
    counts = ui.plantable_seed_counts(items)
    print(f"case {idx} ->", counts)

tree = cr.get_crop_by_key("tree")
tobacco = cr.get_crop_by_key("tobacco")

assert ui.count_seed_for_crop({"sajeneztree": 1}, tree) == 1
assert ui.count_seed_for_crop({"901284129481212412": 2}, tree) == 2
assert ui.count_seed_for_crop({"Саженец дерева": 1}, tree) == 1
assert ui.count_seed_for_crop({"\U0001f331": 3}, tree) == 3
assert ui.count_seed_for_crop({"\U0001f343": 1}, tobacco) == 1
assert cr.get_crop_by_seed("299") is not None
assert cr.get_crop_by_seed("901284129481212412") is not None
assert cr.get_crop_by_seed("Саженец дерева") is not None
print("ok")
