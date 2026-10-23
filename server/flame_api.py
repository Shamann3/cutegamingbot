# -*- coding: utf-8 -*-
"""Вкладка создателя «Огонёк»."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admin_auth import get_signed_in_user_id
from admin_soft_restart import is_project_creator
from db import db
from flame_engine import (
    load_board,
    save_gift_drops,
    save_rewards,
    save_settings,
    save_steps,
    save_titles,
    save_warm_rewards,
    shop_catalog,
)

router = APIRouter(prefix="/admin/api/flame", tags=["flame"])


def _creator(user_id: int = Depends(get_signed_in_user_id)) -> int:
    if not is_project_creator(int(user_id)):
        raise HTTPException(status_code=403, detail="Огонёк открыт только создателю проекта")
    return int(user_id)


class SettingsBody(BaseModel):
    enabled: bool = False
    baseMessages: int = Field(200, ge=1, le=100_000)
    warmEnabled: bool = False
    warmMinDay: int = Field(3, ge=1, le=100_000)
    warmEvery: int = Field(40, ge=1, le=10_000)
    warmCap: int = Field(3, ge=1, le=50)
    warmFrom: int = Field(15, ge=0, le=23)
    warmTo: int = Field(24, ge=1, le=24)
    statusEnabled: bool = True
    profitEnabled: bool = True
    profitHour: int = Field(21, ge=0, le=23)
    minWords: int = Field(2, ge=1, le=20)
    blockDup: bool = True
    giftEnabled: bool = True
    giftMult: int = Field(1, ge=1, le=10)
    giftKutyMin: int = Field(1, ge=1, le=1_000_000)
    giftKutyMax: int = Field(3, ge=1, le=1_000_000)
    giftExtraKutyOn: bool = True
    giftExtraKutyChance: int = Field(35, ge=0, le=100)
    giftExtraKutyMin: int = Field(5, ge=0, le=1_000_000)
    giftExtraKutyMax: int = Field(25, ge=0, le=1_000_000)
    giftItemOn: bool = True
    giftItemChance: int = Field(40, ge=0, le=100)
    giftFallbackPct: int = Field(30, ge=1, le=100)
    restoreEnabled: bool = True
    restoreDays: int = Field(3, ge=1, le=30)
    restoreKuty: int = Field(500, ge=0, le=10_000_000)
    restoreItem: str = ""
    restoreItemCount: int = Field(1, ge=1, le=100)
    model_config = {"extra": "forbid"}


class StepBody(BaseModel):
    fromDay: int = Field(ge=1, le=100_000)
    messages: int = Field(ge=1, le=100_000)
    model_config = {"extra": "forbid"}


class StepsBody(BaseModel):
    steps: list[StepBody] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


class RewardBody(BaseModel):
    day: int = Field(ge=1, le=100_000)
    kind: str
    amount: int = Field(ge=1, le=1_000_000)
    itemName: str = ""
    model_config = {"extra": "forbid"}


class RewardsBody(BaseModel):
    rewards: list[RewardBody] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


class TitleBody(BaseModel):
    fromDay: int = Field(ge=1, le=100_000)
    title: str
    emojiId: str = ""
    model_config = {"extra": "forbid"}


class TitlesBody(BaseModel):
    titles: list[TitleBody] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


class WarmRewardBody(BaseModel):
    kind: str
    amount: int = Field(ge=1, le=1_000_000)
    itemName: str = ""
    weight: int = Field(1, ge=1, le=10_000)
    model_config = {"extra": "forbid"}


class WarmRewardsBody(BaseModel):
    rewards: list[WarmRewardBody] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


class GiftDropBody(BaseModel):
    kind: str
    amountMin: int = Field(1, ge=1, le=1_000_000)
    amountMax: int = Field(1, ge=1, le=1_000_000)
    itemName: str = ""
    weight: int = Field(1, ge=1, le=10_000)
    model_config = {"extra": "forbid"}


class GiftDropsBody(BaseModel):
    drops: list[GiftDropBody] = Field(default_factory=list)
    model_config = {"extra": "forbid"}


def _pool():
    return db.pool


async def _board() -> dict:
    board = await load_board(_pool())
    board["items"] = await shop_catalog(_pool())
    return board


@router.get("")
async def flame_board(_user: int = Depends(_creator)):
    return await _board()


@router.post("/settings")
async def flame_settings(body: SettingsBody, _user: int = Depends(_creator)):
    await save_settings(_pool(), body.model_dump())
    return await _board()


@router.post("/steps")
async def flame_steps(body: StepsBody, _user: int = Depends(_creator)):
    await save_steps(_pool(), [step.model_dump() for step in body.steps])
    return await _board()


@router.post("/rewards")
async def flame_rewards(body: RewardsBody, _user: int = Depends(_creator)):
    await save_rewards(_pool(), [row.model_dump() for row in body.rewards])
    return await _board()


@router.post("/titles")
async def flame_titles(body: TitlesBody, _user: int = Depends(_creator)):
    await save_titles(_pool(), [row.model_dump() for row in body.titles])
    return await _board()


@router.post("/warm-rewards")
async def flame_warm_rewards(body: WarmRewardsBody, _user: int = Depends(_creator)):
    await save_warm_rewards(_pool(), [row.model_dump() for row in body.rewards])
    return await _board()


@router.post("/gift-drops")
async def flame_gift_drops(body: GiftDropsBody, _user: int = Depends(_creator)):
    await save_gift_drops(_pool(), [row.model_dump() for row in body.drops])
    return await _board()
