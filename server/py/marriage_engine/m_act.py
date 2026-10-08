# -*- coding: utf-8 -*-
def act_plan(
    effect,
    fading=False,
    you=0,
    other=0,
    need=0,
    ribbon=False,
    amount=0,
    you_spoke=False,
    both_spoke=False,
    vow_used=False,
    bridge_used=False,
    warm_used=False,
    shield=0,
    fade_extra=0,
    spark_days=0,
    spark_lost=0,
    open_today=False,
    bond="",
    is_proposer=False,
    night=False,
    morning=False,
):
    """Что сделает предмет. Сам ничего не пишет в книгу."""
    try:
        plus = int(amount or 0)
    except (TypeError, ValueError):
        plus = 0
    you, other, need = int(you or 0), int(other or 0), int(need or 0)
    effect = str(effect or "")
    plan = {
        "ok": False, "reason": "bad", "add_you": 0, "add_other": 0, "talk": "",
        "vow": False, "bridge": False, "warm": False, "ribbon": False,
        "extra": None, "shield": None, "days": None, "lost": None, "seal": False, "alert": "",
    }

    def ok(**extra):
        plan["ok"] = True
        plan["reason"] = ""
        plan.update(extra)
        return plan

    if effect == "self":
        if plus < 1:
            return plan
        from marriage_engine.look import care_got
        return ok(add_you=plus, alert=care_got("Вам", plus))
    if effect == "other":
        if plus < 1:
            return plan
        from marriage_engine.look import care_got
        return ok(add_other=plus, alert=care_got("Партнёру", plus))
    if effect == "both":
        if plus < 1:
            return plan
        from marriage_engine.look import care_got
        return ok(add_you=plus, add_other=plus, alert=care_got("Вам и партнёру", plus, each=True))
    if effect == "norm":
        if not night:
            plan["reason"] = "night"
            return plan
        gap = need - you
        if gap <= 0:
            plan["reason"] = "done"
            return plan
        return ok(add_you=gap, alert="Ночь. Ваша часть на сегодня закрыта.")
    if effect == "dawn":
        if not morning:
            plan["reason"] = "sun"
            return plan
        if not fading:
            plan["reason"] = "late"
            return plan
        if plus < 1:
            return plan
        from marriage_engine.look import care_got
        return ok(add_you=plus, alert="Утро. " + care_got("Вам", plus))
    if effect == "gap":
        if not fading:
            plan["reason"] = "calm"
            return plan
        gap = need - you
        if gap <= 0:
            plan["reason"] = "full"
            return plan
        return ok(add_you=gap, alert="Ваша вчерашняя часть закрыта.")
    if effect == "vow":
        if vow_used:
            plan["reason"] = "sworn"
            return plan
        if not you_spoke:
            plan["reason"] = "silent"
            return plan
        return ok(add_you=max(0, need - you), vow=True, alert="Клятва прочитана. Это можно сделать только один раз.")
    if effect == "mark":
        if ribbon:
            plan["reason"] = "worn"
            return plan
        return ok(ribbon=True, alert="Лента теперь на вас. В профиле видно, что вы в браке.")
    if effect == "propose":
        if str(bond or "") in ("propose", "family"):
            plan["reason"] = "said"
            return plan
        return ok(bond="propose", set_proposer=True, alert="Вы сделали предложение. Теперь можно подарить кольцо.")
    if effect == "ring":
        stage = str(bond or "")
        if stage == "family":
            plan["reason"] = "kept" if not is_proposer else "home"
            return plan
        if stage != "propose":
            plan["reason"] = "wait"
            return plan
        if not is_proposer:
            plan["reason"] = "giver"
            return plan
        return ok(bond="family", transfer=True, alert="Кольцо теперь у партнёра. Вы стали семьёй.")
    if effect == "seed":
        plan["reason"] = "field"
        return plan
    if effect == "pantry":
        plan["reason"] = "cook"
        return plan
    return plan


def _hour(moment):
    from datetime import datetime, timedelta, timezone
    msk = timezone(timedelta(hours=3))
    if not isinstance(moment, datetime):
        return None
    moment = moment if moment.tzinfo else moment.replace(tzinfo=msk)
    return moment.astimezone(msk).hour


def moon_up(moment, cfg=None):
    """Луна в окне из панели. По умолчанию с 21:00 до 6:00 по Москве."""
    from marriage_engine.look import clocks, hour_hits
    times = clocks(cfg)
    return hour_hits(_hour(moment), times["moon_from_h"], times["moon_to_h"])


def dawn_up(moment, cfg=None):
    """Рассвет в окне из панели. По умолчанию с 6:00 до 10:00 по Москве."""
    from marriage_engine.look import clocks, hour_hits
    times = clocks(cfg)
    return hour_hits(_hour(moment), times["dawn_from_h"], times["dawn_to_h"])
