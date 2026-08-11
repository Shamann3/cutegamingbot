# -*- coding: utf-8 -*-
"""Safe TECH_CHAT / home log sends — never raise on Telegram errors."""


async def safe_send_tech_log(
    bot,
    chat_id,
    *,
    html: str,
    reply_markup=None,
    fallback_html: str = "",
    tag: str = "TECH_LOG",
) -> None:
    """Send premium log; on any error try fallback without markup; never raise."""
    try:
        await bot.send_message(
            chat_id,
            html,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        if not fallback_html:
            return
        try:
            await bot.send_message(
                chat_id,
                fallback_html,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as e2:
            print(f"[{tag}] {e2!r}")
