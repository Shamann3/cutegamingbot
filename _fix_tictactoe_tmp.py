import re

path = r"C:\Users\Asus\PycharmProjects\support-bot-main\CuteUpdate1\bot\design\inlinetictactoe.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# Разбиваем на блоки по декоратору, чтобы не трогать help_hide (там answer()
# уже стоит правильно, с содержательным текстом, прямо перед edit_message_text).
blocks = re.split(r"(?=@dp\.callback_query)", text)

pattern_dbcall = re.compile(r"( *)await inline_add_or_update_user_info\(")
pattern_alert = re.compile(
    r'await call\.answer\(\s*"\U0001F979 Вы уже находитесь в этой вкладке"\s*,?\s*show_alert=True\s*\)'
)

count_inserted = 0
count_alert = 0
out_blocks = []
for block in blocks:
    is_hide = "help_hide" in block.split("\n", 3)[0] if block.startswith("@dp.callback_query") else False
    # определяем по содержимому: help_hide фильтруется по data == 'help_hide'
    is_hide_block = "c.data == 'help_hide'" in block

    if not is_hide_block:
        m = pattern_dbcall.search(block)
        if m and "await call.answer()" not in block.split("await inline_add_or_update_user_info(")[0][-80:]:
            indent = m.group(1)
            block = pattern_dbcall.sub(
                f"{indent}await call.answer()  # мгновенный акт нажатия - до DB-записи и edit_message_text\n{indent}await inline_add_or_update_user_info(",
                block,
                count=1,
            )
            count_inserted += 1

    new_block, n = pattern_alert.subn(
        "pass  # ack уже отправлен раньше в обработчике - не дублируем answer()",
        block,
    )
    count_alert += n
    out_blocks.append(new_block)

text = "".join(out_blocks)
with open(path, "w", encoding="utf-8") as f:
    f.write(text)

print("inserted answer() calls:", count_inserted)
print("replaced alert lines:", count_alert)
