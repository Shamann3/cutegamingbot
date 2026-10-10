"""Кто может стать рефералом. Чистая проверка, без базы и Telegram."""


def _num(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bound_id(invitee: dict | None) -> int | None:
    if not invitee:
        return None
    for key in ("refferer_id", "refcheck_ref_user_id"):
        raw = invitee.get(key)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def invitee_already_used(invitee: dict | None) -> bool:
    """Человек уже открывал бота: игра, первый /start или пройденная проверка."""
    if not invitee:
        return False
    if _num(invitee.get("usersref")) == 1:
        return True
    if _num(invitee.get("wins")) > 0 or _num(invitee.get("loose")) > 0:
        return True
    if _num(invitee.get("refcheckgame")) == 1:
        return True
    if invitee.get("bot_first_start_at"):
        return True
    if invitee.get("registered_at"):
        return True
    return False


def referral_verdict(
    *,
    user_id: int,
    referrer_id: int,
    referrer_exists: bool,
    invitee: dict | None,
) -> str:
    """
    ok — первый вход, приглашение можно записать.
    self — своя ссылка.
    bad — битый id.
    no_inviter — пригласившего нет в боте.
    same — эта же ссылка уже сработала.
    taken — пригласил другой человек.
    used — бот уже открывали раньше.
    """
    try:
        user_id = int(user_id)
        referrer_id = int(referrer_id)
    except (TypeError, ValueError):
        return "bad"
    if user_id <= 0 or referrer_id <= 0:
        return "bad"
    if user_id == referrer_id:
        return "self"
    if not referrer_exists:
        return "no_inviter"
    bound = _bound_id(invitee)
    if bound == referrer_id:
        return "same"
    if bound is not None:
        return "taken"
    if invitee_already_used(invitee):
        return "used"
    return "ok"
