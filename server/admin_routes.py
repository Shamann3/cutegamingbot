from datetime import date
import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator

from config import ADMIN_TOTP_VALID_WINDOW, PROJECT_CREATOR_ID, owner_user_ids
from admin_auth import (
    build_otpauth_uri,
    create_setup_token,
    generate_totp_secret,
    get_admin_user_id,
    get_any_telegram_user_id,
    issue_admin_token,
    require_admin_session,
    totp_qr_data_url,
    totp_code_now,
    normalize_totp_code,
    normalize_totp_secret,
    classify_admin_key,
    validate_login_key,
    verify_admin_token,
    verify_totp,
    force_reauth,
    store_session_fingerprint,
    _fresh_login_key,
    _get_client_ip,
    _key_matches,
)
from admin_db import (
    accept_rules,
    approve_application,
    add_penalty_to_current_salary,
    add_salary_payment,
    add_shift,
    add_staff_note,
    add_strike,
    approve_salary,
    cancel_salary,
    change_member_role,
    cleanup_expired_pending,
    count_pending_salary_approvals,
    count_unpaid_salaries,
    claim_kut_salary,
    create_invite_token,
    create_pending_payout,
    delete_application_question,
    delete_pending_payout,
    delete_shift,
    delete_staff_note,
    find_valid_invite_token,
    get_leaderboard,
    get_member_card,
    get_member_stats,
    get_pending_payout,
    list_application_questions,
    list_invite_tokens,
    list_payments,
    list_pending_payouts,
    list_shifts,
    list_staff_notes,
    list_strikes,
    list_unpaid,
    hard_delete_invite_token,
    remove_strike,
    revoke_invite_token,
    set_availability,
    upsert_application_question,
    confirm_admin_registration,
    create_admin_account,
    create_application,
    create_complaint,
    create_salary_appeal,
    current_week_start,
    delete_pending_registration,
    list_role_history,
    set_member_curator,
    get_admin_account,
    get_admin_totp_secret,
    get_dashboard_stats,
    get_latest_application,
    get_pending_registration,
    get_pending_registration_by_token,
    update_pending_totp_secret,
    get_salary_owner,
    list_applications,
    list_complaints,
    list_complaints_for_target,
    list_my_salaries,
    list_open_appeals,
    list_salaries_for_week,
    list_salaries_for_period,
    list_staff_actions,
    list_staff_members,
    log_staff_action,
    pay_salary,
    reject_application,
    resolve_complaint,
    resolve_salary_appeal,
    delete_suspended_member,
    save_pending_registration,
    submit_complaint_evidence,
    suspend_member,
    take_complaint,
    unsuspend_member,
    upsert_salary,
)
from admin_permissions import (
    ROLE_JUNIOR,
    ROLE_LABELS,
    ROLE_MODERATOR,
    ROLE_OWNER,
    ROLE_SENIOR,
    get_admin_account_security,
    require_active_admin,
    require_admin_permission,
    require_admin_role,
    require_any_admin_permission,
)
from config import ADMIN_BOT_TOKEN, ADMIN_ENABLED, ADMIN_JWT_SECRET, ADMIN_SESSION_MINUTES, INTERNAL_API_KEY
from admin_appeals import (
    get_appeal_messages, list_appeals, resolve_appeal,
    send_appeal_message, take_appeal,
)
from admin_moderation import (
    delete_log, get_player_history, get_moderator_stats, get_proof_url,
    get_recent_logs, list_moderation_logs, unban_player,
)
from staff_notify import notify_owners, notify_staff
from admin_session_cache import get_admin_session_minutes_cached
from presence import get_day_analytics, get_online_summary, get_range_analytics
from system_settings import get_maintenance_enabled, set_maintenance_enabled
from admin_users import (
    admin_adjust_balance,
    admin_adjust_item,
    admin_reset_onboarding,
    admin_set_banned,
    delete_player_note,
    export_player_profile,
    get_player_ban_history,
    get_player_inventory,
    get_player_quest_info,
    get_user_admin_profile,
    get_user_audit_history,
    list_player_notes,
    search_users,
    upsert_player_note,
)
from admin_economy import (
    bulk_grant_kut,
    get_economy_overview,
    get_economy_stats,
    list_dex_items,
    update_dex_item,
)
from economy_settings import get_economy_settings_payload, update_economy_settings
from admin_market import (
    admin_cancel_listing,
    get_market_overview,
    list_active_listings,
)
from admin_farm import (
    get_farm_overview,
    get_user_farm_admin,
    global_farm_restart,
    reset_user_plots,
)
from admin_quests import create_quest, delete_quest, update_quest
from admin_giveaways import (
    cancel_giveaway,
    complete_giveaway,
    create_giveaway,
    list_giveaways_admin,
    update_giveaway,
)
from admin_bot_quests import (
    bulk_create_challenges,
    bulk_upsert_sub_tasks,
    create_challenge,
    delete_challenge,
    delete_sub_task,
    get_overview as bot_quests_overview,
    list_challenges,
    list_quest_payouts,
    list_sub_tasks,
    patch_challenge,
    patch_sub_task,
    seed_recommended_pack,
    upsert_sub_task,
)
from admin_group_balance_level import (
    get_chat_level as gbl_get_chat_level,
    get_overview as gbl_overview,
    reset_settings as gbl_reset_settings,
    save_settings as gbl_save_settings,
    set_chat_level as gbl_set_chat_level,
)
from admin_soft_restart import (
    apply_preset as sr_apply_preset,
    is_project_creator as sr_is_creator,
    overview as sr_overview,
    queue_restart as sr_queue_restart,
    save_settings as sr_save_settings,
)
from admin_achievements import (
    list_catalog as ach_list_catalog,
    overview as ach_overview,
    remove_item as ach_remove_item,
    save_item as ach_save_item,
    grant_official_to_user as ach_grant_official,
    grant_free_to_user as ach_grant_free,
    list_user_achievements as ach_list_user,
    revoke_from_user as ach_revoke,
)
from admin_content import (
    create_craft_recipe,
    create_crop,
    create_dex_item,
    delete_craft_recipe,
    delete_crop,
    delete_dex_item,
    get_content_overview,
    get_craft_map,
    get_dex_item_full,
    list_dex_items_admin,
    save_craft_map_positions,
    update_craft_recipe,
    update_crop,
    update_dex_item_meta,
)
from farm_settings import get_farm_settings_payload, update_farm_settings
from system_settings_admin import get_all_settings, get_settings_history, update_settings
from admin_broadcast import list_scheduled_broadcasts
from quest_registry import all_quests
from admin_broadcast import (
    cancel_broadcast,
    count_recipients,
    delete_template,
    get_broadcast_overview,
    get_broadcast_run,
    list_broadcast_history,
    list_broadcast_recipients,
    preview_broadcast,
    run_daily_rotation_now,
    save_template,
    start_broadcast,
    DAILY_ROTATION_TEMPLATES,
)
from admin_logs import get_logs_overview, list_audit_logs, list_system_logs, list_p2p_transfers
from admin_cute_history import get_user_cute_history
from error_reporter import schedule_security_alert
from group_posts import (
    create_campaign,
    delete_campaign,
    get_campaign,
    get_campaign_photo,
    list_campaign_log,
    list_campaigns,
    list_known_chats,
    run_campaign_now,
    set_campaign_status,
    update_campaign,
)
from admin_accounts import get_account_profile, list_recent_accounts, search_accounts
from admin_analytics import (
    get_craft_analytics,
    get_farm_analytics,
    get_market_analytics,
    get_quest_analytics,
    get_retention_analytics,
)
from admin_audit import list_admin_audit, list_admin_action_types, log_admin_action
from ip_ban import add_ip_ban, list_ip_bans, remove_ip_ban

router = APIRouter(prefix="/admin/api", tags=["admin"])
logger = logging.getLogger(__name__)


def _parse_dt(value: str | None):
    """Parse ISO 8601 string → timezone-aware datetime or None."""
    if not value:
        return None
    from datetime import datetime, timezone
    s = value.strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Неверный формат даты: {s!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class RegisterStartBody(BaseModel):
    inviteKey: str = Field(min_length=1, max_length=128)
    model_config = {"extra": "forbid"}


class RegisterConfirmBody(BaseModel):
    setupToken: str = Field(min_length=16, max_length=128)
    totp: str = Field(min_length=1, max_length=16)
    model_config = {"extra": "forbid"}

    @field_validator("totp")
    @classmethod
    def normalize_totp(cls, value: str) -> str:
        from admin_auth import normalize_totp_code

        code = normalize_totp_code(value)
        if len(code) != 6:
            raise ValueError("Код должен содержать 6 цифр")
        return code


class LoginBody(BaseModel):
    loginKey: str = Field(min_length=1, max_length=128)
    totp: str = Field(min_length=1, max_length=16)
    model_config = {"extra": "forbid"}

    @field_validator("totp")
    @classmethod
    def normalize_totp(cls, value: str) -> str:
        from admin_auth import normalize_totp_code

        code = normalize_totp_code(value)
        if len(code) != 6:
            raise ValueError("Код должен содержать 6 цифр")
        return code


class LoginKeyBody(BaseModel):
    loginKey: str = Field(min_length=1, max_length=128)
    model_config = {"extra": "forbid"}


PAYOUT_TYPES = {"crypto", "kut", "stars", "card", "other"}


class ApplicationBody(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)
    payoutType: str = Field(min_length=1, max_length=32)
    payoutDetails: str = Field(default="", max_length=300)
    model_config = {"extra": "forbid"}


ASSIGNABLE_ROLES = {ROLE_MODERATOR, ROLE_JUNIOR, ROLE_SENIOR}


class ApproveApplicationBody(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    model_config = {"extra": "forbid"}


class RejectApplicationBody(BaseModel):
    reason: str = Field(default="", max_length=300)
    model_config = {"extra": "forbid"}


SALARY_PAYOUT_TYPES = {"crypto", "kut", "stars", "card", "other"}
SALARY_PERIOD_TYPES = {"day", "week", "month", "year", "custom"}

class SalaryGiftItem(BaseModel):
    giftId: int = Field(ge=0)
    giftEmoji: str = Field(default="⭐", max_length=32)
    hasUpgrade: int = Field(default=0, ge=0, le=1)
    stars: int = Field(ge=1, le=100_000_000)
    model_config = {"extra": "forbid"}


class SetSalaryBody(BaseModel):
    userId: int = Field(ge=1)
    baseAmount: int = Field(ge=0, le=100_000_000)
    coefficient: float = Field(default=1.0, ge=0, le=10)
    bonus: int = Field(default=0, ge=0, le=100_000_000)
    bonusReason: str = Field(default="", max_length=300)
    penalty: int = Field(default=0, ge=0, le=100_000_000)
    penaltyReason: str = Field(default="", max_length=300)
    note: str = Field(default="", max_length=300)
    payoutType: str = Field(default="other", max_length=32)
    periodType: str = Field(default="week", max_length=16)
    periodStart: str | None = Field(default=None, max_length=32)
    periodEnd: str | None = Field(default=None, max_length=32)
    giftId: int | None = Field(default=None, ge=0)
    giftEmoji: str | None = Field(default=None, max_length=32)
    hasUpgrade: int | None = Field(default=None, ge=0, le=1)
    starsUsername: str | None = Field(default=None, max_length=64)
    gifts: list[SalaryGiftItem] | None = None
    model_config = {"extra": "forbid"}


class PaySalaryBody(BaseModel):
    amount: int | None = Field(default=None, ge=1, le=100_000_000)  # None = весь остаток
    method: str | None = Field(default=None, max_length=32)
    kind: str = Field(default="payment", pattern=r"^(payment|advance)$")
    txid: str = Field(default="", max_length=300)
    proof: str = Field(default="", max_length=600)
    starsMethod: str | None = Field(default=None, max_length=16)  # auto|fragment|userbot
    starsUsername: str | None = Field(default=None, max_length=64)
    giftId: int | None = Field(default=None, ge=0)
    giftEmoji: str | None = Field(default=None, max_length=32)
    hasUpgrade: int | None = Field(default=None, ge=0, le=1)
    gifts: list[SalaryGiftItem] | None = None
    model_config = {"extra": "forbid"}


class PayoutSettingsBody(BaseModel):
    cosignKut: int | None = Field(default=None, ge=0, le=100_000_000)
    cosignStars: int | None = Field(default=None, ge=0, le=100_000_000)
    cosignCrypto: int | None = Field(default=None, ge=0, le=100_000_000)
    cosignCard: int | None = Field(default=None, ge=0, le=100_000_000)
    cosignOther: int | None = Field(default=None, ge=0, le=100_000_000)
    defaultStarsMethod: str | None = Field(default=None, max_length=16)
    model_config = {"extra": "forbid"}


class StaffPayoutProfileBody(BaseModel):
    payoutType: str | None = Field(default=None, max_length=32)
    payoutDetails: str | None = Field(default=None, max_length=500)
    starsUsername: str | None = Field(default=None, max_length=64)
    cryptoNetwork: str | None = Field(default=None, max_length=64)
    cryptoAddress: str | None = Field(default=None, max_length=256)
    cardBank: str | None = Field(default=None, max_length=128)
    cardNumber: str | None = Field(default=None, max_length=64)
    cardHolder: str | None = Field(default=None, max_length=128)
    cardSbpPhone: str | None = Field(default=None, max_length=32)
    model_config = {"extra": "forbid"}


class SetBonusBody(BaseModel):
    userId: int = Field(ge=1)
    amount: int = Field(ge=1, le=100_000_000)
    reason: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=300)
    payoutType: str = Field(default="other", max_length=32)
    model_config = {"extra": "forbid"}


class PayBonusBody(BaseModel):
    amount: int | None = Field(default=None, ge=1, le=100_000_000)
    method: str | None = Field(default=None, max_length=32)
    kind: str = Field(default="payment", pattern=r"^(payment|advance)$")
    txid: str = Field(default="", max_length=300)
    proof: str = Field(default="", max_length=600)
    model_config = {"extra": "forbid"}


class ContractTemplateBody(BaseModel):
    id: int | None = Field(default=None, ge=1)
    name: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=20_000)
    payoutType: str | None = Field(default=None, max_length=32)
    enabled: bool = True
    sortOrder: int = Field(default=0, ge=0, le=10_000)
    model_config = {"extra": "forbid"}


class RenderContractBody(BaseModel):
    templateId: int = Field(ge=1)
    userId: int = Field(ge=1)
    amount: int = Field(ge=0, le=100_000_000)
    payoutType: str = Field(default="crypto", max_length=32)
    periodLabel: str = Field(default="", max_length=100)
    model_config = {"extra": "forbid"}


ASSIGNABLE_STAFF_ROLES = {"moderator", "junior_admin", "senior_admin"}


class ChangeRoleBody(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    reason: str = Field(default="", max_length=300)
    model_config = {"extra": "forbid"}


class SetCuratorBody(BaseModel):
    curatorId: int | None = Field(default=None)
    model_config = {"extra": "forbid"}


class AppealBody(BaseModel):
    reason: str = Field(min_length=1, max_length=600)
    model_config = {"extra": "forbid"}


class ResolveAppealBody(BaseModel):
    resolution: str = Field(default="", max_length=600)
    model_config = {"extra": "forbid"}


class MaintenanceBody(BaseModel):
    enabled: bool
    model_config = {"extra": "forbid"}


class UserBalanceBody(BaseModel):
    delta: int = Field(ge=-1_000_000_000, le=1_000_000_000)
    note: str = Field(default="", max_length=256)
    model_config = {"extra": "forbid"}


class UserItemBody(BaseModel):
    itemId: str = Field(min_length=1, max_length=128)
    delta: int = Field(ge=-1_000_000, le=1_000_000)
    note: str = Field(default="", max_length=256)
    model_config = {"extra": "forbid"}


class UserBanBody(BaseModel):
    banned: bool
    reason: str = Field(default="", max_length=512)
    evidence: str = Field(default="", max_length=2000)
    proofMediaId: str = Field(default="", max_length=256)
    model_config = {"extra": "forbid"}


class ComplaintBody(BaseModel):
    targetAdminId: int = Field(ge=1)
    subject: str = Field(default="", max_length=300)
    reason: str = Field(min_length=1, max_length=2000)
    model_config = {"extra": "forbid"}


class ComplaintEvidenceBody(BaseModel):
    evidence: str = Field(min_length=1, max_length=2000)
    model_config = {"extra": "forbid"}


class ComplaintResolveBody(BaseModel):
    resolution: str = Field(default="", max_length=2000)
    penalty: int = Field(default=0, ge=0, le=100_000_000)  # авто-штраф к зарплате
    strike: bool = False  # выдать страйк
    model_config = {"extra": "forbid"}


class StaffNoteBody(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    model_config = {"extra": "forbid"}


class StrikeBody(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    model_config = {"extra": "forbid"}


class AvailabilityBody(BaseModel):
    availability: str = Field(pattern=r"^(active|vacation|afk)$")
    until: str | None = Field(default=None, max_length=40)
    model_config = {"extra": "forbid"}


class ShiftBody(BaseModel):
    userId: int = Field(ge=1)
    startsAt: str = Field(min_length=4, max_length=40)
    endsAt: str = Field(min_length=4, max_length=40)
    note: str = Field(default="", max_length=300)
    model_config = {"extra": "forbid"}


class QuestionBody(BaseModel):
    id: int | None = None
    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=1, max_length=300)
    type: str = Field(default="text", pattern=r"^(text|textarea)$")
    required: bool = True
    sortOrder: int = Field(default=0, ge=0, le=999)
    enabled: bool = True
    model_config = {"extra": "forbid"}


class EconomySettingsBody(BaseModel):
    defaultBalance: int | None = Field(default=None, ge=0, le=10_000_000)
    clearCost: int | None = Field(default=None, ge=0, le=1_000_000)
    model_config = {"extra": "forbid"}


class DexItemPatchBody(BaseModel):
    price: int | None = Field(default=None, ge=0, le=99_999_999)
    dis: int | None = Field(default=None, ge=0, le=99_999_999)
    remains: int | None = Field(default=None, ge=0, le=99_999_999)
    model_config = {"extra": "forbid"}


class BulkGrantBody(BaseModel):
    delta: int = Field(ge=-1_000_000, le=1_000_000)
    target: str = Field(default="all", pattern=r"^(all|online)$")
    note: str = Field(default="", max_length=256)
    model_config = {"extra": "forbid"}


class MarketCancelBody(BaseModel):
    reason: str = Field(default="", max_length=256)
    model_config = {"extra": "forbid"}


class FarmSettingsBody(BaseModel):
    treeGrowSeconds: int | None = Field(default=None, ge=30, le=86_400)
    tobaccoGrowSeconds: int | None = Field(default=None, ge=30, le=86_400)
    maxPlots: int | None = Field(default=None, ge=1, le=100)
    plotPriceStep: int | None = Field(default=None, ge=1, le=1_000_000)
    waterIntervalSeconds: int | None = Field(default=None, ge=30, le=3600)
    wiltGraceSeconds: int | None = Field(default=None, ge=10, le=3600)
    waterCostPerUse: int | None = Field(default=None, ge=0, le=10)
    model_config = {"extra": "forbid"}


class HarvestDropBody(BaseModel):
    itemId: str = Field(min_length=1, max_length=128)
    minAmount: int = Field(default=1, ge=1, le=999)
    maxAmount: int = Field(default=1, ge=1, le=999)
    chancePercent: int = Field(default=100, ge=1, le=100)
    model_config = {"extra": "forbid"}


class CropCreateBody(BaseModel):
    key: str = Field(min_length=2, max_length=50)
    displayName: str = Field(min_length=1, max_length=120)
    seedItemId: str = Field(min_length=1, max_length=128)
    growSeconds: int = Field(ge=30, le=86_400)
    harvestToolItemId: str | None = Field(default=None, max_length=128)
    harvestToolCost: int = Field(default=1, ge=1, le=99)
    waterItemId: str | None = Field(default=None, max_length=128)
    waterCostPerUse: int | None = Field(default=None, ge=1, le=99)
    spriteKey: str = Field(default="generic", max_length=32)
    enabled: bool = True
    harvestDrops: list[HarvestDropBody] = Field(min_length=1, max_length=20)
    model_config = {"extra": "forbid"}


class CropUpdateBody(BaseModel):
    displayName: str | None = Field(default=None, max_length=120)
    seedItemId: str | None = Field(default=None, max_length=128)
    growSeconds: int | None = Field(default=None, ge=30, le=86_400)
    harvestToolItemId: str | None = Field(default=None, max_length=128)
    harvestToolCost: int | None = Field(default=None, ge=1, le=99)
    waterItemId: str | None = Field(default=None, max_length=128)
    waterCostPerUse: int | None = Field(default=None, ge=1, le=99)
    spriteKey: str | None = Field(default=None, max_length=32)
    enabled: bool | None = None
    harvestDrops: list[HarvestDropBody] | None = Field(default=None, max_length=20)
    clearHarvestTool: bool = False
    clearWaterItem: bool = False
    model_config = {"extra": "forbid"}


class DexItemCreateBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    emoji: str = Field(default="📦", max_length=16)
    name1: str = Field(default="", max_length=120)
    price: int = Field(default=0, ge=0, le=99_999_999)
    dis: int = Field(default=0, ge=0, le=99_999_999)
    remains: int = Field(default=0, ge=0, le=99_999_999)
    sorting: str | None = Field(default=None, max_length=64)
    bio: str = Field(default="", max_length=1000)
    use: str = Field(default="", max_length=500)
    bonus: str = Field(default="", max_length=500)
    craft: str = Field(default="", max_length=500)
    model_config = {"extra": "forbid"}


class DexItemMetaBody(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    emoji: str | None = Field(default=None, max_length=16)
    name1: str | None = Field(default=None, max_length=120)
    price: int | None = Field(default=None, ge=0, le=99_999_999)
    dis: int | None = Field(default=None, ge=0, le=99_999_999)
    remains: int | None = Field(default=None, ge=0, le=99_999_999)
    sorting: str | None = Field(default=None, max_length=32)
    bio: str | None = Field(default=None, max_length=500)
    model_config = {"extra": "forbid"}


class CraftMapPositionItem(BaseModel):
    itemId: str = Field(min_length=1, max_length=64)
    x: float
    y: float
    model_config = {"extra": "forbid"}


class CraftMapPositionsBody(BaseModel):
    positions: list[CraftMapPositionItem] = Field(default_factory=list, max_length=5000)
    model_config = {"extra": "forbid"}


class CraftRecipeCreateBody(BaseModel):
    key: str = Field(min_length=2, max_length=50)
    displayName: str = Field(default="", max_length=120)
    resultItemId: str = Field(min_length=1, max_length=128)
    ingredientAId: str = Field(min_length=1, max_length=128)
    ingredientBId: str = Field(min_length=1, max_length=128)
    successPercent: int = Field(default=100, ge=1, le=100)
    enabled: bool = True
    remains: int = Field(default=0, ge=0)
    resultQty: int = Field(default=1, ge=1)
    model_config = {"extra": "forbid"}


class CraftRecipeUpdateBody(BaseModel):
    displayName: str | None = Field(default=None, max_length=120)
    resultItemId: str | None = Field(default=None, max_length=128)
    ingredientAId: str | None = Field(default=None, max_length=128)
    ingredientBId: str | None = Field(default=None, max_length=128)
    successPercent: int | None = Field(default=None, ge=1, le=100)
    enabled: bool | None = None
    remains: int | None = Field(default=None, ge=0)
    resultQty: int | None = Field(default=None, ge=1)
    model_config = {"extra": "forbid"}


class QuestRewardBody(BaseModel):
    kind: str = Field(min_length=3, max_length=8)
    amount: int = Field(default=1, ge=1, le=999_999)
    itemId: str | None = Field(default=None, max_length=128)
    model_config = {"extra": "forbid"}


class QuestCreateBody(BaseModel):
    key: str = Field(min_length=2, max_length=50)
    period: str = Field(min_length=3, max_length=16)
    action: str = Field(min_length=3, max_length=32)
    target: int = Field(default=1, ge=1, le=9999)
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    emoji: str = Field(default="📋", max_length=16)
    enabled: bool = True
    targetScope: str = Field(default="any", max_length=16)
    targetCropKey: str | None = Field(default=None, max_length=64)
    targetItemId: str | None = Field(default=None, max_length=128)
    rewards: list[QuestRewardBody] = Field(default_factory=list, max_length=10)
    # Scheduling
    activeFrom: str | None = Field(default=None, max_length=64)
    activeUntil: str | None = Field(default=None, max_length=64)
    recurrence: str | None = Field(default=None, max_length=16)
    recurrenceEnd: str | None = Field(default=None, max_length=64)
    model_config = {"extra": "forbid"}


class QuestUpdateBody(BaseModel):
    period: str | None = Field(default=None, max_length=16)
    action: str | None = Field(default=None, max_length=32)
    target: int | None = Field(default=None, ge=1, le=9999)
    title: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    emoji: str | None = Field(default=None, max_length=16)
    enabled: bool | None = None
    targetScope: str | None = Field(default=None, max_length=16)
    targetCropKey: str | None = Field(default=None, max_length=64)
    targetItemId: str | None = Field(default=None, max_length=128)
    rewards: list[QuestRewardBody] | None = Field(default=None, max_length=10)
    # Scheduling (use empty string "" to clear a field)
    activeFrom: str | None = Field(default=None, max_length=64)
    activeUntil: str | None = Field(default=None, max_length=64)
    recurrence: str | None = Field(default=None, max_length=16)
    recurrenceEnd: str | None = Field(default=None, max_length=64)
    clearSchedule: bool = False  # set to True to wipe all scheduling fields
    model_config = {"extra": "forbid"}


class GiveawayConditionBody(BaseModel):
    kind: str = Field(min_length=3, max_length=16)
    targetValue: int = Field(default=1, ge=1)
    itemId: str | None = Field(default=None, max_length=128)
    model_config = {"extra": "forbid"}


class GiveawayCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    emoji: str = Field(default="🎁", max_length=16)
    rarity: str = Field(min_length=3, max_length=16)
    prizeType: str = Field(min_length=3, max_length=16)
    prizeKutAmount: int | None = Field(default=None, ge=1)
    prizeTitle: str | None = Field(default=None, max_length=120)
    prizeEmoji: str | None = Field(default=None, max_length=16)
    prizeDescription: str | None = Field(default=None, max_length=500)
    prizeAnimationUrl: str | None = Field(default=None, max_length=500)
    prizeAnimationType: str | None = Field(default=None, max_length=16)
    drawType: str = Field(min_length=5, max_length=16)
    startsAt: str | None = Field(default=None, max_length=64)
    endsAt: str | None = Field(default=None, max_length=64)
    conditions: list[GiveawayConditionBody] = Field(default_factory=list, max_length=10)
    enabled: bool = True
    model_config = {"extra": "forbid"}


class GiveawayUpdateBody(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    emoji: str | None = Field(default=None, max_length=16)
    rarity: str | None = Field(default=None, max_length=16)
    prizeType: str | None = Field(default=None, max_length=16)
    prizeKutAmount: int | None = Field(default=None, ge=1)
    prizeTitle: str | None = Field(default=None, max_length=120)
    prizeEmoji: str | None = Field(default=None, max_length=16)
    prizeDescription: str | None = Field(default=None, max_length=500)
    prizeAnimationUrl: str | None = Field(default=None, max_length=500)
    prizeAnimationType: str | None = Field(default=None, max_length=16)
    drawType: str | None = Field(default=None, max_length=16)
    startsAt: str | None = Field(default=None, max_length=64)
    endsAt: str | None = Field(default=None, max_length=64)
    conditions: list[GiveawayConditionBody] | None = Field(default=None, max_length=10)
    enabled: bool | None = None
    model_config = {"extra": "forbid"}


class BotSubTaskBody(BaseModel):
    chatRef: str = Field(min_length=1, max_length=200)
    reward: float | str | int
    limitMode: str = Field(default="unlimited", max_length=16)
    totalCap: int | None = Field(default=None, ge=1)
    ttlValue: int | None = Field(default=None, ge=1)
    ttlUnit: str = Field(default="h", max_length=4)
    ttlExpiresAt: str | None = Field(default=None, max_length=64)
    startsAt: str | None = Field(default=None, max_length=64)
    active: bool = True
    model_config = {"extra": "forbid"}


class BotSubTaskBulkBody(BaseModel):
    items: list[BotSubTaskBody] = Field(min_length=1, max_length=100)
    model_config = {"extra": "forbid"}


class BotSubTaskPatchBody(BaseModel):
    chatRef: str | None = Field(default=None, max_length=200)
    reward: float | str | int | None = None
    limitMode: str | None = Field(default=None, max_length=16)
    totalCap: int | None = Field(default=None, ge=1)
    ttlValue: int | None = Field(default=None, ge=1)
    ttlUnit: str | None = Field(default=None, max_length=4)
    ttlExpiresAt: str | None = Field(default=None, max_length=64)
    startsAt: str | None = Field(default=None, max_length=64)
    active: bool | None = None
    activateNow: bool | None = None
    model_config = {"extra": "forbid"}


class BotChallengeBody(BaseModel):
    startAmount: int = Field(ge=1)
    targetAmount: int = Field(ge=1)
    rewardAmount: int = Field(ge=1)
    maxBet: int | None = Field(default=None, ge=0)
    chatRef: str | None = Field(default=None, max_length=200)
    maxUsers: int | None = Field(default=None, ge=0)
    free: str = Field(default="-", max_length=2)
    startsAt: str | None = Field(default=None, max_length=64)
    model_config = {"extra": "forbid"}


class BotChallengeBulkBody(BaseModel):
    items: list[BotChallengeBody] = Field(min_length=1, max_length=100)
    model_config = {"extra": "forbid"}


class BotChallengePatchBody(BaseModel):
    startAmount: int | None = Field(default=None, ge=1)
    targetAmount: int | None = Field(default=None, ge=1)
    rewardAmount: int | None = Field(default=None, ge=1)
    maxBet: int | None = Field(default=None, ge=0)
    chatRef: str | None = Field(default=None, max_length=200)
    maxUsers: int | None = Field(default=None, ge=0)
    free: str | None = Field(default=None, max_length=2)
    status: str | None = Field(default=None, max_length=16)
    startsAt: str | None = Field(default=None, max_length=64)
    activateNow: bool | None = None
    disable: bool | None = None
    model_config = {"extra": "forbid"}


class BroadcastFilterBody(BaseModel):
    excludeBanned: bool = True
    minBalance: int | None = Field(default=None, ge=0, le=1_000_000_000)
    maxBalance: int | None = Field(default=None, ge=0, le=1_000_000_000)
    hasPlots: bool | None = None
    username: str | None = Field(default=None, max_length=64)
    userIds: list[int] | None = Field(default=None, max_length=500)
    model_config = {"extra": "forbid"}


class BroadcastChannelsBody(BaseModel):
    webapp: bool = True
    telegram: bool = True
    model_config = {"extra": "forbid"}


class BroadcastPreviewBody(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(default="", max_length=500)
    detail: str = Field(default="", max_length=300)
    telegramText: str = Field(default="", max_length=2000)
    sampleUserId: int | None = Field(default=None, ge=1)
    model_config = {"extra": "forbid"}


class BroadcastCountBody(BaseModel):
    audience: str = Field(default="all", pattern=r"^(all|online|filtered)$")
    filter: BroadcastFilterBody | None = None
    model_config = {"extra": "forbid"}


class BroadcastSendBody(BaseModel):
    audience: str = Field(default="all", pattern=r"^(all|online|filtered)$")
    filter: BroadcastFilterBody | None = None
    channels: BroadcastChannelsBody = Field(default_factory=BroadcastChannelsBody)
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(default="", max_length=500)
    detail: str = Field(default="", max_length=300)
    telegramText: str = Field(default="", max_length=2000)
    templateKey: str | None = Field(default=None, max_length=64)
    scheduledAt: str | None = Field(default=None, max_length=64)
    label: str = Field(default="", max_length=120)
    model_config = {"extra": "forbid"}


class BroadcastTemplateBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(default="", max_length=500)
    detail: str = Field(default="", max_length=300)
    telegramText: str = Field(default="", max_length=2000)
    templateId: int | None = Field(default=None, ge=1)
    model_config = {"extra": "forbid"}


@router.get("/health")
async def admin_health():
    login_key = _fresh_login_key()
    return {
        "ok": True,
        "loginKeyConfigured": bool(login_key),
        "loginKeyLength": len(login_key),
    }


@router.get("/auth/status")
async def admin_auth_status(
    request: Request,
    user_id: int = Depends(get_any_telegram_user_id),
):
    account = await get_admin_account(user_id)
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else ""
    verified = verify_admin_token(token) if token else None

    application = await get_latest_application(user_id) if account else None

    return {
        "registered": account is not None,
        "authenticated": verified is not None and verified[0] == user_id,
        "userId": user_id,
        "role": account["role"] if account else None,
        "status": account["status"] if account else None,
        "applicationStatus": application["status"] if application else None,
        "isOwner": user_id in owner_user_ids(),
    }


@router.post("/auth/register/start")
async def admin_register_start(
    body: RegisterStartBody,
    request: Request,
    user_id: int = Depends(get_any_telegram_user_id),
):
    from admin_auth_rate_limit import enforce_admin_auth_rate_limit

    enforce_admin_auth_rate_limit(request)
    await cleanup_expired_pending()

    # Проверяем сначала env-ключи, потом DB-инвайты
    key_type = classify_admin_key(body.inviteKey)
    db_invite_token: str | None = None
    if key_type is None:
        invite_record = await find_valid_invite_token(body.inviteKey)
        if invite_record is None:
            raise HTTPException(status_code=403, detail="Неверный ключ доступа")
        key_type = "staff"
        db_invite_token = body.inviteKey

    if await get_admin_account(user_id):
        raise HTTPException(
            status_code=409,
            detail="Аккаунт уже зарегистрирован. Войдите во вкладке «Вход».",
        )

    tg_user = getattr(request.state, "telegram_user", {}) or {}
    account_name = tg_user.get("username") or tg_user.get("first_name") or str(user_id)

    secret = generate_totp_secret()
    setup_token = create_setup_token()
    # Метка в приложении-аутентификаторе: «CuteEpsilon [имя] [хвост ключа]».
    tail = secret[-4:]
    label_name = f"{account_name} [{tail}]"
    otpauth_uri = build_otpauth_uri(secret, account_name=label_name, issuer="CuteEpsilon")
    qr_data_url = totp_qr_data_url(otpauth_uri)

    await save_pending_registration(setup_token, user_id, secret, key_type, db_invite_token)

    return {
        "setupToken": setup_token,
        "qrDataUrl": qr_data_url,
        "totpSecret": secret,
        "accountName": account_name,
        "authenticatorLabel": f"CuteEpsilon {account_name} [{tail}]",
        "expiresIn": 900,
        "issuer": "CuteEpsilon",
        "keyType": key_type,
    }


@router.post("/auth/register/reveal-code")
async def admin_register_reveal_code(
    body: RegisterConfirmBody,
    request: Request,
    user_id: int = Depends(get_any_telegram_user_id),
):
    """Шаг «Получить подтверждающий код» при регистрации.

    Возвращает актуальный код сервера, вычисленный от секрета в БД (как
    «SERVER EXPECTED CODE NOW» в check-register-code.bat). Этот код гарантированно
    проходит финальную проверку. Поле synced показывает, совпал ли код из
    приложения (индикатор синхронизации, вход не блокирует).
    """
    from admin_auth_rate_limit import enforce_admin_auth_rate_limit

    enforce_admin_auth_rate_limit(request)

    pending = await get_pending_registration(body.setupToken, user_id)
    if not pending:
        raise HTTPException(status_code=400, detail="Сессия регистрации истекла. Начните заново.")

    pending_secret = normalize_totp_secret(pending["totp_secret"])
    if not pending_secret:
        raise HTTPException(status_code=400, detail="Сессия регистрации повреждена. Начните заново.")

    # Код считаем от секрета в БД — та же логика, что «SERVER EXPECTED CODE NOW»
    # в check-register-code.bat. Он гарантированно пройдёт финальную проверку,
    # т.к. сверяется с тем же секретом на том же сервере.
    code = totp_code_now(pending_secret)
    if not code:
        raise HTTPException(status_code=400, detail="Не удалось получить код. Начните регистрацию заново.")

    # Совпал ли код из приложения (широкое окно ±15 мин) — только индикатор синхронизации.
    synced = verify_totp(pending_secret, body.totp, valid_window=max(ADMIN_TOTP_VALID_WINDOW, 30))
    return {"ok": True, "code": code, "synced": synced}


@router.post("/auth/register/confirm")
async def admin_register_confirm(
    body: RegisterConfirmBody,
    request: Request,
    user_id: int = Depends(get_any_telegram_user_id),
):
    from admin_auth_rate_limit import enforce_admin_auth_rate_limit

    enforce_admin_auth_rate_limit(request)

    pending = await get_pending_registration(body.setupToken, user_id)
    if not pending:
        other = await get_pending_registration_by_token(body.setupToken)
        if other and int(other["user_id"]) != int(user_id):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Сессия регистрации открыта с другого Telegram-аккаунта. "
                    "Завершите её в том же аккаунте, с которого начали."
                ),
            )
        raise HTTPException(status_code=400, detail="Сессия регистрации истекла. Начните заново.")

    if await get_admin_account(user_id):
        raise HTTPException(
            status_code=409,
            detail="Аккаунт уже зарегистрирован. Войдите во вкладке «Вход».",
        )

    pending_secret = normalize_totp_secret(pending["totp_secret"])
    if not pending_secret or not verify_totp(pending_secret, body.totp, valid_window=max(ADMIN_TOTP_VALID_WINDOW, 30)):
        raise HTTPException(status_code=403, detail="Неверный код подтверждения. Начните заново.")

    key_type = pending.get("key_type") or "staff"
    if key_type == "owner":
        role, status = "owner", "active"
    else:
        role, status = "applicant", "pending"

    tg_user = getattr(request.state, "telegram_user", {}) or {}
    ok = await confirm_admin_registration(
        body.setupToken,
        user_id,
        pending_secret,
        username=tg_user.get("username"),
        first_name=tg_user.get("first_name"),
        role=role,
        status=status,
        invite_token=pending.get("invite_token"),
    )
    if not ok:
        raise HTTPException(
            status_code=409,
            detail="Инвайт уже использован другим пользователем",
        )

    return {
        "ok": True,
        "registered": True,
        "keyType": key_type,
        "requiresApplication": key_type == "staff",
    }


@router.get("/auth/application-questions")
async def admin_application_questions(_user_id: int = Depends(get_any_telegram_user_id)):
    """Вопросы анкеты для формы регистрации кандидата."""
    return {"items": await list_application_questions(enabled_only=True)}


@router.post("/auth/application")
async def admin_submit_application(
    body: ApplicationBody,
    request: Request,
    user_id: int = Depends(get_any_telegram_user_id),
):
    from admin_auth_rate_limit import enforce_admin_auth_rate_limit

    enforce_admin_auth_rate_limit(request)

    account = await get_admin_account(user_id)
    if not account:
        raise HTTPException(status_code=403, detail="Сначала пройдите регистрацию")
    if account["status"] != "pending" or account["role"] != "applicant":
        raise HTTPException(status_code=409, detail="Заявка недоступна для этого аккаунта")

    payout_type = body.payoutType.strip().lower()
    if payout_type not in PAYOUT_TYPES:
        raise HTTPException(status_code=400, detail="Неверный способ выплаты")

    # Чистим анкету: только непустые строковые ответы, до 2000 символов
    answers = {
        str(k)[:64]: str(v).strip()[:2000]
        for k, v in (body.answers or {}).items()
        if str(v).strip()
    }

    tg_user = getattr(request.state, "telegram_user", {}) or {}
    created = await create_application(
        user_id,
        username=tg_user.get("username") or account.get("username"),
        first_name=tg_user.get("first_name") or account.get("first_name"),
        answers=answers,
        payout_type=payout_type,
        payout_details=body.payoutDetails.strip() or None,
    )
    if not created:
        raise HTTPException(status_code=409, detail="Заявка уже отправлена и ожидает рассмотрения")

    who = tg_user.get("username") or tg_user.get("first_name") or str(user_id)
    notify_owners(f"<tg-emoji emoji-id='5400289821253990206'>📝</tg-emoji> <b>Новая заявка во вкладке Staff в админ панели Эпсилона, от {who} (ID {user_id}).</b>\n<blockquote><b>Виво-Эпсилон</b></blockquote>")

    return {"ok": True, "submitted": True}


async def _resolve_login_key_ok(user_id: int, account: dict, login_key: str) -> bool:
    """env-ключ владельца ИЛИ персональный login_key пользователя."""
    from db import db as _db
    personal_key = account.get("login_key") or ""
    if not personal_key:
        personal_key = await _db.pool.fetchval(
            "SELECT token FROM admin_invite_tokens WHERE used_by = $1 LIMIT 1",
            user_id,
        ) or ""
        if personal_key:
            await _db.pool.execute(
                "UPDATE admin_accounts SET login_key = $1 WHERE user_id = $2",
                personal_key, user_id,
            )
    return validate_login_key(login_key) or (
        bool(personal_key) and _key_matches(login_key, personal_key)
    )


def _login_status_guard(account: dict) -> None:
    status = account.get("status")
    if status != "active" or account.get("role") == "suspended":
        if status == "pending":
            raise HTTPException(
                status_code=403,
                detail="Аккаунт ещё не активирован. Ожидайте решения владельца",
            )
        if status == "rejected":
            raise HTTPException(status_code=403, detail="Заявка отклонена")
        raise HTTPException(status_code=403, detail="Доступ к панели закрыт")


@router.post("/auth/login/verify-key")
async def admin_login_verify_key(
    body: LoginKeyBody,
    request: Request,
    user_id: int = Depends(get_admin_user_id),
):
    """Проверка только ключа входа (без кода). Позволяет фронту показать поле
    для кода лишь при верном ключе — как автопроверка ключа при регистрации."""
    from admin_auth_rate_limit import enforce_admin_auth_rate_limit

    enforce_admin_auth_rate_limit(request)

    account = await get_admin_account(user_id)
    if not account:
        raise HTTPException(status_code=403, detail="Сначала пройдите регистрацию")

    if not await _resolve_login_key_ok(user_id, account, body.loginKey):
        raise HTTPException(status_code=403, detail="Неверный ключ входа")

    _login_status_guard(account)

    totp_secret = normalize_totp_secret(await get_admin_totp_secret(user_id) or "")
    if not totp_secret:
        raise HTTPException(status_code=403, detail="TOTP не настроен. Пройдите регистрацию заново.")

    return {"ok": True}


@router.post("/auth/login/reveal-code")
async def admin_login_reveal_code(
    body: LoginBody,
    request: Request,
    user_id: int = Depends(get_admin_user_id),
):
    """Шаг «Получить подтверждающий код» при входе. Проверяет ключ + код из
    Authenticator широким окном (чинит рассинхрон часов) и возвращает актуальный
    код сервера для завершения входа."""
    from admin_auth_rate_limit import enforce_admin_auth_rate_limit

    enforce_admin_auth_rate_limit(request)

    account = await get_admin_account(user_id)
    if not account:
        raise HTTPException(status_code=403, detail="Сначала пройдите регистрацию")

    if not await _resolve_login_key_ok(user_id, account, body.loginKey):
        raise HTTPException(status_code=403, detail="Неверный ключ входа")

    _login_status_guard(account)

    totp_secret = normalize_totp_secret(await get_admin_totp_secret(user_id) or "")
    if not totp_secret:
        raise HTTPException(status_code=403, detail="TOTP не настроен. Пройдите регистрацию заново.")

    # Код считаем от секрета в БД — как «SERVER EXPECTED CODE NOW» в батнике.
    code = totp_code_now(totp_secret)
    if not code:
        raise HTTPException(status_code=400, detail="Не удалось получить код. Попробуйте снова.")

    synced = verify_totp(totp_secret, body.totp, valid_window=max(ADMIN_TOTP_VALID_WINDOW, 30))
    return {"ok": True, "code": code, "synced": synced}


@router.post("/auth/login")
async def admin_login(
    body: LoginBody,
    request: Request,
    user_id: int = Depends(get_admin_user_id),
):
    from admin_auth_rate_limit import enforce_admin_auth_rate_limit

    enforce_admin_auth_rate_limit(request)

    account = await get_admin_account(user_id)
    if not account:
        raise HTTPException(status_code=403, detail="Сначала пройдите регистрацию")

    if not await _resolve_login_key_ok(user_id, account, body.loginKey):
        schedule_security_alert(
            "ERR_SEC_ADMIN_LOGIN_FAIL",
            request=request,
            user_id=user_id,
            message="Неверный ключ входа в админку",
            status=403,
        )
        raise HTTPException(status_code=403, detail="Неверный ключ входа")

    _login_status_guard(account)

    totp_secret = await get_admin_totp_secret(user_id)
    if not totp_secret or not verify_totp(totp_secret, body.totp, valid_window=max(ADMIN_TOTP_VALID_WINDOW, 30)):
        schedule_security_alert(
            "ERR_SEC_ADMIN_LOGIN_FAIL",
            request=request,
            user_id=user_id,
            message="Неверный код 2FA при входе в админку",
            status=403,
        )
        raise HTTPException(status_code=403, detail="Неверный код из Google Authenticator")

    token, exp = issue_admin_token(user_id)
    await store_session_fingerprint(user_id, request)
    await log_admin_action(
        user_id, "login",
        target_type="session",
        target_label="Вход в панель",
        ip=_get_client_ip(request),
    )
    return {
        "ok": True,
        "token": token,
        "expiresAt": exp,
        "sessionMinutes": get_admin_session_minutes_cached(),
        "authenticated": True,
    }


@router.post("/auth/refresh")
async def admin_refresh_session(admin_id: int = Depends(require_admin_session)):
    token, exp = issue_admin_token(admin_id)
    return {
        "ok": True,
        "token": token,
        "expiresAt": exp,
        "sessionMinutes": get_admin_session_minutes_cached(),
    }


@router.get("/auth/me")
async def admin_me(user_id: int = Depends(require_active_admin)):
    """Текущий админ: роль, статус, права — для фильтрации навигации фронта."""
    account = await get_admin_account_security(user_id)
    if not account:
        raise HTTPException(status_code=403, detail="Админ-аккаунт не найден")
    account["projectCreatorId"] = int(PROJECT_CREATOR_ID)
    account["isProjectCreator"] = sr_is_creator(user_id)
    return account


class PanelRoleDefaultBody(BaseModel):
    role: str
    sectionId: str
    enabled: bool


class PanelUserAccessBody(BaseModel):
    userId: int
    sectionId: str
    # None / omit via reset=true — сброс к дефолту роли
    allowed: bool | None = None
    reset: bool = False


class PanelUserAccessBatchItem(BaseModel):
    userId: int
    sectionId: str
    allowed: bool | None = None
    reset: bool = False


class PanelUserAccessBatchBody(BaseModel):
    items: list[PanelUserAccessBatchItem] = Field(default_factory=list)


async def _panel_target_role(target_user_id: int) -> str:
    """Лёгкая проверка цели без полного get_admin_account."""
    from db import db as _db

    row = await _db.pool.fetchrow(
        "SELECT role, status FROM admin_accounts WHERE user_id = $1",
        int(target_user_id),
    )
    if not row or row["status"] != "active":
        raise HTTPException(status_code=404, detail="Администратор не найден")
    if row["role"] == ROLE_OWNER:
        raise HTTPException(status_code=400, detail="Доступ владельца не ограничивается")
    return str(row["role"])


@router.get("/panel-access")
async def panel_access_overview(
    user_id: int = Depends(require_admin_permission("manage_panel_access")),
):
    from panel_access import list_panel_access_overview

    return await list_panel_access_overview()


@router.put("/panel-access/role-default")
async def panel_access_set_role_default(
    body: PanelRoleDefaultBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("manage_panel_access")),
):
    from panel_access import set_role_default

    try:
        await set_role_default(body.role, body.sectionId, body.enabled, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await log_admin_action(
        user_id,
        "panel_role_default",
        target_type="panel",
        target_id=f"{body.role}:{body.sectionId}",
        details={"enabled": body.enabled},
        ip=_get_client_ip(request),
    )
    return {"ok": True}


@router.put("/panel-access/user")
async def panel_access_set_user(
    body: PanelUserAccessBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("manage_panel_access")),
):
    from panel_access import set_user_override

    if int(body.userId) == int(user_id):
        raise HTTPException(status_code=400, detail="Нельзя менять доступ самому себе здесь")
    await _panel_target_role(body.userId)

    allowed = None if body.reset else body.allowed
    if not body.reset and body.allowed is None:
        raise HTTPException(status_code=400, detail="Укажите allowed или reset")
    try:
        await set_user_override(int(body.userId), body.sectionId, allowed, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Аудит не блокирует ответ UI — пишем в фоне.
    try:
        import asyncio

        asyncio.create_task(
            log_admin_action(
                user_id,
                "panel_user_access",
                target_type="staff",
                target_id=str(body.userId),
                details={"sectionId": body.sectionId, "allowed": allowed, "reset": body.reset},
                ip=_get_client_ip(request),
            )
        )
    except Exception:
        pass
    return {"ok": True}


@router.put("/panel-access/user-batch")
async def panel_access_set_user_batch(
    body: PanelUserAccessBatchBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("manage_panel_access")),
):
    """Пакетное изменение доступов (строка «всем ON/OFF», массовые клики)."""
    from panel_access import set_user_overrides_batch

    if not body.items:
        return {"ok": True, "count": 0}
    if len(body.items) > 200:
        raise HTTPException(status_code=400, detail="Слишком много изменений за раз")

    seen_targets: set[int] = set()
    payload = []
    for item in body.items:
        tid = int(item.userId)
        if tid == int(user_id):
            raise HTTPException(status_code=400, detail="Нельзя менять доступ самому себе здесь")
        if tid not in seen_targets:
            await _panel_target_role(tid)
            seen_targets.add(tid)
        payload.append(
            {
                "userId": tid,
                "sectionId": item.sectionId,
                "allowed": item.allowed,
                "reset": bool(item.reset),
            }
        )
    try:
        count = await set_user_overrides_batch(payload, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        import asyncio

        asyncio.create_task(
            log_admin_action(
                user_id,
                "panel_user_access_batch",
                target_type="panel",
                target_id="batch",
                details={"count": count, "sample": payload[:8]},
                ip=_get_client_ip(request),
            )
        )
    except Exception:
        pass
    return {"ok": True, "count": count}


@router.post("/staff/accept-rules")
async def staff_accept_rules(
    request: Request,
    user_id: int = Depends(require_active_admin),
):
    """Принятие правил при первом входе. Идемпотентно."""
    changed = await accept_rules(user_id)
    if changed:
        await log_admin_action(
            user_id, "rules_accept",
            target_type="session",
            target_label="Принял правила",
            ip=_get_client_ip(request),
        )
    account = await get_admin_account_security(user_id)
    return {
        "ok": True,
        "rulesAcceptedAt": account["rulesAcceptedAt"] if account else None,
    }


# ---------------------------------------------------------------------------
# Staff: заявки и сотрудники (owner / senior)
# ---------------------------------------------------------------------------


@router.get("/staff/applications")
async def staff_list_applications(
    status: str = Query("pending"),
    _user_id: int = Depends(require_admin_permission("review_applications")),
):
    if status not in {"pending", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Неверный статус")
    return {"items": await list_applications(status)}


@router.post("/staff/applications/{application_id}/approve")
async def staff_approve_application(
    application_id: int,
    body: ApproveApplicationBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("assign_roles")),
):
    role = body.role.strip()
    if role not in ASSIGNABLE_ROLES:
        raise HTTPException(status_code=400, detail="Недопустимая роль")

    result = await approve_application(application_id, role, user_id)
    if not result:
        raise HTTPException(status_code=409, detail="Заявка не найдена или уже рассмотрена")

    await log_admin_action(
        user_id, "staff_approve",
        target_type="staff",
        target_id=str(result["userId"]),
        target_label=ROLE_LABELS.get(role, role),
        details={"role": role, "applicationId": application_id},
        ip=_get_client_ip(request),
    )
    notify_staff(
        result["userId"],
        f"<tg-emoji emoji-id='5208540237524911208'>✅</tg-emoji> <b>Ваша заявка в состав сотрудников Эпсилона одобрена! Вы повышены до роли : {ROLE_LABELS.get(role, role)}. </b>\n<blockquote><b>Виво-Эпсилон</b></blockquote>"
    )
    return {"ok": True, **result}


@router.post("/staff/applications/{application_id}/reject")
async def staff_reject_application(
    application_id: int,
    body: RejectApplicationBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("review_applications")),
):
    result = await reject_application(application_id, body.reason.strip(), user_id)
    if not result:
        raise HTTPException(status_code=409, detail="Заявка не найдена или уже рассмотрена")

    await log_admin_action(
        user_id, "staff_reject",
        target_type="staff",
        target_id=str(result["userId"]),
        target_label="Заявка отклонена",
        details={"reason": body.reason.strip(), "applicationId": application_id},
        ip=_get_client_ip(request),
    )
    reason_txt = body.reason.strip()
    notify_staff(
        result["userId"],
        "❌ Ваша заявка отклонена."
        + (f" Причина: {reason_txt}" if reason_txt else "")
        + " Вы можете подать заявку заново.",
    )
    return {"ok": True, **result}


@router.get("/staff/members")
async def staff_list_members(
    _user_id: int = Depends(require_admin_permission("manage_staff")),
):
    members = await list_staff_members()
    for m in members:
        m["roleLabel"] = ROLE_LABELS.get(m["role"], m["role"])
    return {"items": members}


@router.post("/staff/members/{member_id}/suspend")
async def staff_suspend_member(
    member_id: int,
    request: Request,
    user_id: int = Depends(require_admin_permission("manage_staff")),
):
    if member_id == user_id:
        raise HTTPException(status_code=400, detail="Нельзя отстранить самого себя")

    ok = await suspend_member(member_id, user_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Сотрудник не найден или это владелец")

    await log_admin_action(
        user_id, "staff_suspend",
        target_type="staff",
        target_id=str(member_id),
        target_label="Отстранён",
        ip=_get_client_ip(request),
    )
    return {"ok": True}


@router.post("/staff/members/{member_id}/unsuspend")
async def staff_unsuspend_member(
    member_id: int,
    request: Request,
    user_id: int = Depends(require_admin_permission("manage_staff")),
):
    ok = await unsuspend_member(member_id, user_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Сотрудник не найден или не отстранён")

    await log_admin_action(
        user_id, "staff_unsuspend",
        target_type="staff",
        target_id=str(member_id),
        target_label="Возвращён к работе",
        ip=_get_client_ip(request),
    )
    return {"ok": True}


@router.delete("/staff/members/{member_id}")
async def staff_delete_member(
    member_id: int,
    request: Request,
    user_id: int = Depends(require_admin_permission("assign_roles")),
):
    if member_id == user_id:
        raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")
    ok = await delete_suspended_member(member_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Сотрудник не найден или не отстранён")
    await log_admin_action(
        user_id, "staff_delete",
        target_type="staff",
        target_id=str(member_id),
        target_label="Аккаунт удалён",
        ip=_get_client_ip(request),
    )
    return {"ok": True}


@router.post("/staff/members/{member_id}/role")
async def staff_change_role(
    member_id: int,
    body: ChangeRoleBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("assign_roles")),
):
    role = body.role.strip()
    if role not in ASSIGNABLE_STAFF_ROLES:
        raise HTTPException(status_code=400, detail="Недопустимая роль")
    if member_id == user_id:
        raise HTTPException(status_code=400, detail="Нельзя менять свою роль")

    result = await change_member_role(member_id, role, user_id, body.reason.strip())
    if not result:
        raise HTTPException(status_code=409, detail="Сотрудник не найден, это владелец или роль не изменилась")

    await log_admin_action(
        user_id, "staff_role_change",
        target_type="staff", target_id=str(member_id),
        target_label=f"{ROLE_LABELS.get(result['oldRole'], result['oldRole'])} → {ROLE_LABELS.get(role, role)}",
        details={"oldRole": result["oldRole"], "newRole": role, "reason": body.reason.strip()},
        ip=_get_client_ip(request),
    )
    notify_staff(
        member_id,
        f"<tg-emoji emoji-id='5454074580010295588'>🔄</tg-emoji> <b>Ваша должность изменена : {ROLE_LABELS.get(result['oldRole'], result['oldRole'])} → </b>"
        f"<b>{ROLE_LABELS.get(role, role)}.</b>"
        + (f" <b>Причина : {body.reason.strip()}</b>" if body.reason.strip() else "") + (f"<blockquote><b>Виво-Эпсилон</b></blockquote>"),

    )
    return {"ok": True, **result}


@router.get("/staff/members/{member_id}/history")
async def staff_role_history(
    member_id: int,
    _user_id: int = Depends(require_admin_permission("manage_staff")),
):
    return {"items": await list_role_history(member_id)}


@router.post("/staff/members/{member_id}/curator")
async def staff_set_curator(
    member_id: int,
    body: SetCuratorBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("manage_staff")),
):
    curator_id = body.curatorId
    if curator_id is not None:
        if curator_id == member_id:
            raise HTTPException(status_code=400, detail="Сотрудник не может быть своим куратором")
        curator = await get_admin_account(curator_id)
        if not curator or curator.get("role") not in ("senior_admin", "owner"):
            raise HTTPException(status_code=400, detail="Куратором может быть только старший или владелец")

    ok = await set_member_curator(member_id, curator_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    await log_admin_action(
        user_id, "staff_curator_set",
        target_type="staff", target_id=str(member_id),
        details={"curatorId": curator_id},
        ip=_get_client_ip(request),
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Staff: зарплаты и апелляции
# ---------------------------------------------------------------------------


@router.get("/staff/salaries")
async def staff_list_salaries(
    periodType: str = Query(default="week"),
    periodStart: str | None = Query(default=None),
    periodEnd: str | None = Query(default=None),
    _user_id: int = Depends(require_admin_permission("set_salary")),
):
    from staff_payroll import period_label, resolve_period

    raw_start = None
    raw_end = None
    if periodStart:
        try:
            raw_start = date.fromisoformat(periodStart[:10])
        except ValueError:
            raise HTTPException(status_code=400, detail="periodStart: YYYY-MM-DD")
    if periodEnd:
        try:
            raw_end = date.fromisoformat(periodEnd[:10])
        except ValueError:
            raise HTTPException(status_code=400, detail="periodEnd: YYYY-MM-DD")
    try:
        p_type, p_start, p_end = resolve_period(periodType or "week", raw_start, raw_end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "weekStart": p_start.isoformat() if p_type == "week" else current_week_start().isoformat(),
        "periodType": p_type,
        "periodStart": p_start.isoformat(),
        "periodEnd": p_end.isoformat(),
        "periodLabel": period_label(p_type, p_start, p_end),
        "items": await list_salaries_for_period(p_type, p_start, p_end),
    }


@router.post("/staff/salaries")
async def staff_set_salary(
    body: SetSalaryBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("set_salary")),
):
    from staff_payroll import period_label, resolve_period

    setter = await get_admin_account_security(user_id)
    setter_role = setter["role"] if setter else None

    target = await get_admin_account(body.userId)
    if not target or target.get("status") != "active":
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    target_role = target.get("role")
    if target_role == ROLE_OWNER:
        raise HTTPException(status_code=400, detail="Владельцу зарплата не начисляется")
    if int(body.userId) == int(user_id):
        raise HTTPException(status_code=403, detail="Нельзя назначать зарплату самому себе")

    # senior ставит только модераторам/младшим; owner — кому угодно из стаффа
    if setter_role == ROLE_OWNER:
        status = "approved"
    elif setter_role == ROLE_SENIOR:
        if target_role not in (ROLE_MODERATOR, ROLE_JUNIOR):
            raise HTTPException(status_code=403, detail="Старший не может ставить эту зарплату")
        status = "pending_approval"
    else:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    raw_start = None
    raw_end = None
    if body.periodStart:
        try:
            raw_start = date.fromisoformat(body.periodStart[:10])
        except ValueError:
            raise HTTPException(status_code=400, detail="periodStart: YYYY-MM-DD")
    if body.periodEnd:
        try:
            raw_end = date.fromisoformat(body.periodEnd[:10])
        except ValueError:
            raise HTTPException(status_code=400, detail="periodEnd: YYYY-MM-DD")
    try:
        p_type, p_start, p_end = resolve_period(body.periodType or "week", raw_start, raw_end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    week_start = current_week_start()
    payout_type = body.payoutType if body.payoutType in SALARY_PAYOUT_TYPES else "other"
    salary_id = await upsert_salary(
        body.userId, week_start,
        base=body.baseAmount,
        coefficient=body.coefficient,
        bonus=body.bonus,
        bonus_reason=body.bonusReason.strip(),
        penalty=body.penalty,
        penalty_reason=body.penaltyReason.strip(),
        note=body.note.strip(),
        setter_id=user_id,
        status=status,
        payout_type=payout_type,
        period_type=p_type,
        period_start=p_start,
        period_end=p_end,
    )
    if salary_id is None:
        raise HTTPException(status_code=409, detail="Зарплата за этот период уже выплачена")

    from admin_db import compute_salary_total
    total = compute_salary_total(body.baseAmount, body.coefficient, body.bonus, body.penalty)
    label = period_label(p_type, p_start, p_end)

    await log_admin_action(
        user_id, "salary_set",
        target_type="staff",
        target_id=str(body.userId),
        target_label=f"Зарплата {total}",
        details={
            "base": body.baseAmount, "coefficient": body.coefficient,
            "bonus": body.bonus, "penalty": body.penalty, "total": total,
            "status": status, "periodType": p_type,
            "periodStart": p_start.isoformat(), "periodEnd": p_end.isoformat(),
        },
        ip=_get_client_ip(request),
    )
    status_txt = "ожидает одобрения" if status == "pending_approval" else "одобрена"
    notify_staff(
        body.userId,
        (
            f"<tg-emoji emoji-id='4958926882994127612'>💰</tg-emoji> "
            f"<b>Вам выставлена зарплата</b>\n"
            f"<tg-emoji emoji-id='5449372007432985754'>🌴</tg-emoji> "
            f"<b>{total} кут · {label}</b>\n"
            f"<b>Статус: {status_txt}</b>\n"
            f"<blockquote>Если не согласны — апелляция в панели.\n"
            f"Виво-Эпсилон</blockquote>"
        ),
    )

    # Сохранение зарплаты НЕ ставит заявку в канал выводов.
    # В канал — только явная кнопка «В канал» / pay (PayrollPayModal).
    return {
        "ok": True, "salaryId": salary_id, "status": status, "total": total,
        "periodType": p_type, "periodStart": p_start.isoformat(),
        "periodEnd": p_end.isoformat(), "periodLabel": label,
        "starQueued": False,
        "starPayouts": [],
        "starPayout": None,
    }


async def _enqueue_salary_stars_channel(
    *,
    salary_id: int,
    staff_user_id: int,
    amount: int,
    requested_by: int,
    stars_username: str | None = None,
    gift_id: int = 0,
    gift_emoji: str = "⭐",
    has_upgrade: int = 0,
    gifts: list[dict] | None = None,
) -> list[dict] | None:
    """После назначения/одобрения/выплаты Stars — сразу заявки в канал выводов."""
    from staff_payroll import get_staff_payout_profile
    from staff_stars import enqueue_salary_channel_request

    profile = await get_staff_payout_profile(staff_user_id)
    stars_user = (stars_username or "").strip().lstrip("@")
    if not stars_user and profile:
        stars_user = (profile.get("starsUsername") or profile.get("username") or "").lstrip("@")
    if not stars_user or len(stars_user) < 5:
        notify_owners(
            (
                f"<tg-emoji emoji-id='5924701179157156993'>⭐️</tg-emoji> "
                f"<b>Зарплата #{salary_id} в Stars не ушла в канал</b>\n"
                f"<b>У сотрудника нет username для Stars.</b>\n"
                f"<blockquote>Виво-Эпсилон</blockquote>"
            ),
        )
        return None
    try:
        queued = await enqueue_salary_channel_request(
            salary_id=salary_id,
            user_id=staff_user_id,
            amount=amount,
            requested_by=requested_by,
            stars_username=stars_user,
            gift_id=gift_id,
            gift_emoji=gift_emoji or "⭐",
            has_upgrade=has_upgrade,
            gifts=gifts,
            first_name=(profile or {}).get("firstName") or "",
        )
    except ValueError as e:
        notify_owners(
            (
                f"<tg-emoji emoji-id='5420315771991497307'>🔥</tg-emoji> "
                f"<b>Не удалось создать заявку зарплаты в канал</b>\n"
                f"<code>{e}</code>\n"
                f"<blockquote>Виво-Эпсилон</blockquote>"
            ),
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        notify_owners(
            (
                f"<tg-emoji emoji-id='5420315771991497307'>🔥</tg-emoji> "
                f"<b>Ошибка отправки зарплаты в канал</b>\n"
                f"<code>{e}</code>\n"
                f"<blockquote>Виво-Эпсилон</blockquote>"
            ),
        )
        return None

    n = len(queued or [])
    posted_n = sum(1 for q in (queued or []) if q.get("status") == "channel_pending")
    notify_staff(
        staff_user_id,
        (
            f"<tg-emoji emoji-id='5924701179157156993'>⭐️</tg-emoji> "
            f"<b>Заявка на зарплату {amount}⭐ создана</b>\n"
            f"<tg-emoji emoji-id='5294026527850132517'>🍬</tg-emoji> "
            f"<b>Получатель: @{stars_user}</b>\n"
            f"<blockquote>{n} сообщ. в канале выводов · в канале уже {posted_n}\n"
            f"Ожидайте подтверждения 👍\n"
            f"Виво-Эпсилон</blockquote>"
        ),
    )
    notify_owners(
        (
            f"<tg-emoji emoji-id='5422818196031840237'>🌿</tg-emoji> "
            f"<b>Заявка на выплату зарплаты администратору</b>\n"
            f"<tg-emoji emoji-id='5449372007432985754'>🌴</tg-emoji> "
            f"<b>{amount} кут в stars · {n} сообщ.</b>\n"
            f"<tg-emoji emoji-id='5294026527850132517'>🍬</tg-emoji> "
            f"<b>Для @{stars_user}</b>\n"
            f"<blockquote>Откройте канал выводов (@CurrencyCute) и нажмите 👍\n"
            f"Виво-Эпсилон</blockquote>"
        ),
        exclude=requested_by,
    )
    return queued


@router.post("/staff/salaries/{salary_id}/approve")
async def staff_approve_salary(
    salary_id: int,
    request: Request,
    user_id: int = Depends(require_admin_permission("approve_salary")),
):
    from admin_db import get_salary_full

    ok = await approve_salary(salary_id, user_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Начисление не найдено или уже одобрено")
    await log_admin_action(
        user_id, "salary_approve",
        target_type="salary",
        target_id=str(salary_id),
        ip=_get_client_ip(request),
    )

    # Одобрение тоже только сохраняет статус — в канал идём через «В канал».
    return {
        "ok": True,
        "starQueued": False,
        "starPayouts": [],
        "starPayout": None,
    }


async def _needs_cosign(amount: int, method: str | None) -> bool:
    """Двойное подтверждение по порогам из «Настройки выплат»."""
    from staff_payroll import needs_cosign
    return await needs_cosign(amount, method)


@router.post("/staff/salaries/{salary_id}/pay")
async def staff_pay_salary(
    salary_id: int,
    body: PaySalaryBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("pay_salary")),
):
    from admin_db import get_salary_full

    ctx = await get_salary_full(salary_id)
    if not ctx or ctx["status"] not in ("approved", "partially_paid"):
        raise HTTPException(status_code=409, detail="Начисление не одобрено или уже выплачено")
    if int(ctx["userId"]) == int(user_id):
        raise HTTPException(status_code=403, detail="Нельзя выплачивать зарплату самому себе")
    remaining = max(0, ctx["amount"] - ctx["paidAmount"])
    method = (body.method.strip() if body.method else None) or ctx["payoutType"]
    pay_amount = min(body.amount if body.amount is not None else remaining, remaining)
    if pay_amount <= 0:
        raise HTTPException(status_code=409, detail="Нечего выплачивать")

    # Stars: подтверждение — это 👍 в канале, cosign не нужен
    # (иначе крупные суммы «оплачивались» без заявки в канал)
    if method != "stars" and await _needs_cosign(pay_amount, method):
        payout_id = await create_pending_payout(
            salary_id, ctx["userId"], pay_amount, method, body.kind,
            body.txid.strip(), body.proof.strip(), user_id,
        )
        notify_owners(
            f"<tg-emoji emoji-id='5870972873450984431'>🔐</tg-emoji> <b>Требуется со-подтверждение выплаты : {pay_amount} ({method or '—'}). </b>"
            f"<b>Откройте «Реестр → На подтверждении».</b>\n<blockquote><b>Виво-Эпсилон</b></blockquote>",
            exclude=user_id,
        )
        await log_admin_action(
            user_id, "salary_pay_request",
            target_type="salary", target_id=str(salary_id),
            details={"amount": pay_amount}, ip=_get_client_ip(request),
        )
        return {"ok": True, "pending": True, "payoutId": payout_id}

    # --- Stars: строгий флоу — N заявок в канал → 👍 → userbot ---
    if method == "stars":
        gifts_payload = [g.model_dump() for g in body.gifts] if body.gifts else None
        try:
            queued_list = await _enqueue_salary_stars_channel(
                salary_id=salary_id,
                staff_user_id=ctx["userId"],
                amount=pay_amount,
                requested_by=user_id,
                stars_username=body.starsUsername,
                gift_id=int(body.giftId or 0),
                gift_emoji=(body.giftEmoji or "⭐").strip() or "⭐",
                has_upgrade=int(body.hasUpgrade or 0),
                gifts=gifts_payload,
            )
        except HTTPException:
            raise
        if not queued_list:
            raise HTTPException(
                status_code=400,
                detail="Не удалось создать заявку Stars — проверьте username сотрудника",
            )
        await log_admin_action(
            user_id, "salary_stars_enqueue",
            target_type="salary", target_id=str(salary_id),
            details={
                "amount": pay_amount,
                "method": "userbot",
                "count": len(queued_list),
                "payoutIds": [q.get("id") for q in queued_list],
            },
            ip=_get_client_ip(request),
        )
        return {
            "ok": True,
            "queued": True,
            "starPayouts": queued_list,
            "starPayout": queued_list[0],
            "status": "queued",
            "amount": pay_amount,
            "userId": ctx["userId"],
            "posted": sum(1 for q in queued_list if q.get("status") == "channel_pending"),
        }

    result = await add_salary_payment(
        salary_id, user_id, pay_amount,
        method=method,
        kind=body.kind,
        txid=body.txid.strip(),
        proof=body.proof.strip(),
    )
    if not result:
        raise HTTPException(status_code=409, detail="Начисление не одобрено или уже выплачено")
    await log_admin_action(
        user_id, "salary_pay",
        target_type="salary",
        target_id=str(salary_id),
        details={"amount": result["amount"], "kind": body.kind, "txid": body.txid.strip()},
        ip=_get_client_ip(request),
    )
    txid_txt = f" TXID: {body.txid.strip()}" if body.txid.strip() else ""
    if result["status"] == "paid":
        notify_staff(int(result["userId"]), f"<tg-emoji emoji-id='5208540237524911208'>✅</tg-emoji> <b>Ваша зарплата полностью выплачена. {txid_txt}</b>")
    else:
        notify_staff(
            int(result["userId"]),
            f"<tg-emoji emoji-id='5472030678633684592'>💸</tg-emoji> <b>Вам {'выдан аванс' if body.kind == 'advance' else 'частично выплачена зарплата'} : </b>"
            f"<b>{result['amount']}. Остаток : {result['remaining']}.{txid_txt}</b>\n<blockquote><b>Виво-Эпсилон</b></blockquote>",
        )
    return {"ok": True, **result}


@router.post("/staff/salaries/{salary_id}/cancel")
async def staff_cancel_salary(
    salary_id: int,
    request: Request,
    user_id: int = Depends(require_admin_permission("set_salary")),
):
    ok = await cancel_salary(salary_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Начисление не найдено или уже выплачено")
    await log_admin_action(
        user_id, "salary_cancel",
        target_type="salary",
        target_id=str(salary_id),
        ip=_get_client_ip(request),
    )
    return {"ok": True}


@router.get("/staff/my-salary")
async def staff_my_salary(user_id: int = Depends(require_active_admin)):
    from staff_payroll import list_my_bonuses
    return {
        "items": await list_my_salaries(user_id),
        "bonuses": await list_my_bonuses(user_id),
    }


@router.post("/staff/my-salary/claim-kut")
async def staff_claim_kut_salary(user_id: int = Depends(require_active_admin)):
    """Сотрудник забирает одобренную ЗП в kut на свой игровой баланс."""
    result = await claim_kut_salary(user_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Нет одобренной зарплаты в kut для получения",
        )
    return {"ok": True, "amount": result["amount"], "salaryId": result["salaryId"]}


@router.post("/staff/my-salary/claim-kut-bonus")
async def staff_claim_kut_bonus(user_id: int = Depends(require_active_admin)):
    from staff_payroll import claim_kut_bonus
    result = await claim_kut_bonus(user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Нет одобренной премии в kut")
    return {"ok": True, **result}


@router.get("/staff/my-payout-profile")
async def staff_get_my_payout_profile(user_id: int = Depends(require_active_admin)):
    from staff_payroll import get_staff_payout_profile
    profile = await get_staff_payout_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")
    return profile


@router.put("/staff/my-payout-profile")
async def staff_update_my_payout_profile(
    body: StaffPayoutProfileBody,
    request: Request,
    user_id: int = Depends(require_active_admin),
):
    from staff_payroll import update_staff_payout_profile
    try:
        profile = await update_staff_payout_profile(
            user_id,
            payout_type=body.payoutType,
            payout_details=body.payoutDetails,
            stars_username=body.starsUsername,
            crypto_network=body.cryptoNetwork,
            crypto_address=body.cryptoAddress,
            card_bank=body.cardBank,
            card_number=body.cardNumber,
            card_holder=body.cardHolder,
            card_sbp_phone=body.cardSbpPhone,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")
    await log_admin_action(
        user_id, "payout_profile_update",
        target_type="staff", target_id=str(user_id),
        ip=_get_client_ip(request),
    )
    return profile


@router.put("/staff/members/{member_id}/payout-profile")
async def staff_update_member_payout_profile(
    member_id: int,
    body: StaffPayoutProfileBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("pay_salary")),
):
    """Владелец/плательщик может сам прописать реквизиты сотруднику."""
    from staff_payroll import update_staff_payout_profile
    try:
        profile = await update_staff_payout_profile(
            member_id,
            payout_type=body.payoutType,
            payout_details=body.payoutDetails,
            stars_username=body.starsUsername,
            crypto_network=body.cryptoNetwork,
            crypto_address=body.cryptoAddress,
            card_bank=body.cardBank,
            card_number=body.cardNumber,
            card_holder=body.cardHolder,
            card_sbp_phone=body.cardSbpPhone,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not profile:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    await log_admin_action(
        user_id, "payout_profile_update",
        target_type="staff", target_id=str(member_id),
        ip=_get_client_ip(request),
    )
    return profile


# ---------------------------------------------------------------------------
# Настройки выплат / премии / договоры
# ---------------------------------------------------------------------------

@router.get("/staff/payout-settings")
async def staff_get_payout_settings(
    _user_id: int = Depends(require_admin_permission("pay_salary")),
):
    from staff_payroll import get_payout_settings
    from staff_stars import get_fragment_health
    settings = await get_payout_settings()
    settings["fragment"] = await get_fragment_health()
    return settings


@router.get("/staff/fragment-health")
async def staff_fragment_health(
    _user_id: int = Depends(require_admin_permission("pay_salary")),
):
    from staff_stars import get_fragment_health
    return await get_fragment_health()


@router.get("/staff/star-gifts")
async def staff_star_gifts(
    amount: int | None = Query(default=None, ge=1, le=100_000_000),
    exact: bool = Query(default=True),
    _user_id: int = Depends(require_admin_permission("pay_salary")),
):
    """Каталог подарков для зарплатных Stars (live Telegram + ручные)."""
    from staff_stars import list_star_gifts
    items = await list_star_gifts(amount=amount, exact=exact)
    live_n = sum(1 for g in items if g.get("source") == "live")
    manual_n = sum(1 for g in items if g.get("source") == "manual")
    return {
        "items": items,
        "amount": amount,
        "exact": exact,
        "liveCount": live_n,
        "manualCount": manual_n,
    }


@router.get("/staff/star-payouts")
async def staff_list_star_payouts(
    status: str | None = Query(default=None),
    _user_id: int = Depends(require_admin_permission("pay_salary")),
):
    from staff_stars import list_star_payouts
    return {"items": await list_star_payouts(status=status)}


@router.put("/staff/payout-settings")
async def staff_put_payout_settings(
    body: PayoutSettingsBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("approve_salary")),
):
    from staff_payroll import update_payout_settings
    try:
        settings = await update_payout_settings(
            updated_by=user_id,
            cosign_kut=body.cosignKut,
            cosign_stars=body.cosignStars,
            cosign_crypto=body.cosignCrypto,
            cosign_card=body.cosignCard,
            cosign_other=body.cosignOther,
            default_stars_method=body.defaultStarsMethod,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await log_admin_action(
        user_id, "payout_settings_update",
        target_type="settings", target_id="payout",
        details=settings, ip=_get_client_ip(request),
    )
    return settings


@router.get("/staff/bonuses")
async def staff_list_bonuses(
    status: str | None = Query(default=None),
    _user_id: int = Depends(require_admin_permission("set_salary")),
):
    from staff_payroll import list_bonuses
    return {"items": await list_bonuses(status=status)}


@router.post("/staff/bonuses")
async def staff_create_bonus(
    body: SetBonusBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("set_salary")),
):
    from staff_payroll import create_bonus

    setter = await get_admin_account_security(user_id)
    setter_role = setter["role"] if setter else None
    target = await get_admin_account(body.userId)
    if not target or target.get("status") != "active":
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    target_role = target.get("role")
    if target_role == ROLE_OWNER:
        raise HTTPException(status_code=400, detail="Владельцу премия не начисляется")

    if setter_role == ROLE_OWNER:
        status = "approved"
    elif setter_role == ROLE_SENIOR:
        if target_role not in (ROLE_MODERATOR, ROLE_JUNIOR):
            raise HTTPException(status_code=403, detail="Старший не может ставить эту премию")
        status = "pending_approval"
    else:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    payout_type = body.payoutType if body.payoutType in SALARY_PAYOUT_TYPES else "other"
    bonus_id = await create_bonus(
        body.userId,
        amount=body.amount,
        reason=body.reason.strip(),
        note=body.note.strip() or None,
        payout_type=payout_type,
        setter_id=user_id,
        status=status,
    )
    await log_admin_action(
        user_id, "bonus_set",
        target_type="staff", target_id=str(body.userId),
        details={"amount": body.amount, "status": status, "bonusId": bonus_id},
        ip=_get_client_ip(request),
    )
    status_txt = "ожидает одобрения" if status == "pending_approval" else "одобрена"
    notify_staff(
        body.userId,
        f"<tg-emoji emoji-id='4958926882994127612'>🎁</tg-emoji> <b>Вам выставлена премия: {body.amount} ({status_txt}).</b>"
        + (f" <b>Причина: {body.reason.strip()}</b>" if body.reason.strip() else "")
        + "\n<blockquote><b>Виво-Эпсилон</b></blockquote>",
    )
    return {"ok": True, "bonusId": bonus_id, "status": status}


@router.post("/staff/bonuses/{bonus_id}/approve")
async def staff_approve_bonus(
    bonus_id: int,
    request: Request,
    user_id: int = Depends(require_admin_permission("approve_salary")),
):
    from staff_payroll import approve_bonus
    ok = await approve_bonus(bonus_id, user_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Премия не найдена или уже одобрена")
    await log_admin_action(
        user_id, "bonus_approve", target_type="bonus", target_id=str(bonus_id),
        ip=_get_client_ip(request),
    )
    return {"ok": True}


@router.post("/staff/bonuses/{bonus_id}/pay")
async def staff_pay_bonus(
    bonus_id: int,
    body: PayBonusBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("pay_salary")),
):
    from staff_payroll import add_bonus_payment, get_bonus

    ctx = await get_bonus(bonus_id)
    if not ctx or ctx["status"] not in ("approved", "partially_paid"):
        raise HTTPException(status_code=409, detail="Премия не одобрена или уже выплачена")
    remaining = max(0, ctx["amount"] - ctx["paidAmount"])
    method = (body.method.strip() if body.method else None) or ctx["payoutType"]
    pay_amount = min(body.amount if body.amount is not None else remaining, remaining)

    if await _needs_cosign(pay_amount, method):
        # Переиспользуем pending_payouts с bonus_id (salary_id NULL)
        from db import db as _db
        row = await _db.pool.fetchrow(
            """
            INSERT INTO pending_payouts
                (salary_id, bonus_id, source, user_id, amount, method, kind, txid, proof, requested_by)
            VALUES (NULL, $1, 'bonus', $2, $3, $4, $5, $6, $7, $8) RETURNING id
            """,
            bonus_id, ctx["userId"], pay_amount, method, body.kind,
            body.txid.strip() or None, body.proof.strip() or None, user_id,
        )
        notify_owners(
            f"<tg-emoji emoji-id='5870972873450984431'>🔐</tg-emoji> <b>Со-подтверждение премии: {pay_amount} ({method or '—'}).</b>"
            f"<b>Откройте «Реестр → На подтверждении».</b>\n<blockquote><b>Виво-Эпсилон</b></blockquote>",
            exclude=user_id,
        )
        await log_admin_action(
            user_id, "bonus_pay_request",
            target_type="bonus", target_id=str(bonus_id),
            details={"amount": pay_amount}, ip=_get_client_ip(request),
        )
        return {"ok": True, "pending": True, "payoutId": int(row["id"])}

    result = await add_bonus_payment(
        bonus_id, user_id, pay_amount,
        method=method, kind=body.kind,
        txid=body.txid.strip(), proof=body.proof.strip(),
    )
    if not result:
        raise HTTPException(status_code=409, detail="Премия не одобрена или уже выплачена")
    await log_admin_action(
        user_id, "bonus_pay",
        target_type="bonus", target_id=str(bonus_id),
        details={"amount": result["amount"]}, ip=_get_client_ip(request),
    )
    notify_staff(
        int(result["userId"]),
        f"<tg-emoji emoji-id='5208540237524911208'>✅</tg-emoji> <b>Премия: выплачено {result['amount']}.</b>"
        + (f" <b>Остаток: {result['remaining']}.</b>" if result["remaining"] else ""),
    )
    return {"ok": True, **result}


@router.post("/staff/bonuses/{bonus_id}/cancel")
async def staff_cancel_bonus(
    bonus_id: int,
    request: Request,
    user_id: int = Depends(require_admin_permission("set_salary")),
):
    from staff_payroll import cancel_bonus
    ok = await cancel_bonus(bonus_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Премия не найдена или уже выплачена")
    await log_admin_action(
        user_id, "bonus_cancel", target_type="bonus", target_id=str(bonus_id),
        ip=_get_client_ip(request),
    )
    return {"ok": True}


@router.get("/staff/contract-templates")
async def staff_list_contract_templates(
    _user_id: int = Depends(require_admin_permission("pay_salary")),
):
    from staff_payroll import list_contract_templates
    return {"items": await list_contract_templates()}


@router.post("/staff/contract-templates")
async def staff_save_contract_template(
    body: ContractTemplateBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("approve_salary")),
):
    from staff_payroll import upsert_contract_template
    if body.payoutType and body.payoutType not in ("crypto", "card", "other", "stars", "kut"):
        raise HTTPException(status_code=400, detail="Неверный payoutType шаблона")
    tid = await upsert_contract_template(
        template_id=body.id,
        name=body.name.strip(),
        body=body.body,
        payout_type=body.payoutType,
        enabled=body.enabled,
        sort_order=body.sortOrder,
        updated_by=user_id,
    )
    await log_admin_action(
        user_id, "contract_template_save",
        target_type="contract", target_id=str(tid),
        ip=_get_client_ip(request),
    )
    return {"ok": True, "id": tid}


@router.delete("/staff/contract-templates/{template_id}")
async def staff_delete_contract_template(
    template_id: int,
    request: Request,
    user_id: int = Depends(require_admin_permission("approve_salary")),
):
    from staff_payroll import delete_contract_template
    ok = await delete_contract_template(template_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    await log_admin_action(
        user_id, "contract_template_delete",
        target_type="contract", target_id=str(template_id),
        ip=_get_client_ip(request),
    )
    return {"ok": True}


@router.post("/staff/contract-templates/render")
async def staff_render_contract(
    body: RenderContractBody,
    user_id: int = Depends(require_admin_permission("pay_salary")),
):
    from staff_payroll import get_staff_payout_profile, list_contract_templates, render_contract
    templates = await list_contract_templates()
    tpl = next((t for t in templates if t["id"] == body.templateId), None)
    if not tpl:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    profile = await get_staff_payout_profile(body.userId)
    if not profile:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    text = render_contract(
        tpl["body"],
        amount=body.amount,
        staff_name=profile.get("firstName") or "",
        staff_username=profile.get("username") or "",
        payout_type=body.payoutType,
        details={
            "cryptoNetwork": profile.get("cryptoNetwork") or "",
            "cryptoAddress": profile.get("cryptoAddress") or "",
            "cardBank": profile.get("cardBank") or "",
            "cardNumber": profile.get("cardNumber") or "",
            "cardHolder": profile.get("cardHolder") or "",
            "cardSbpPhone": profile.get("cardSbpPhone") or "",
            "starsUsername": profile.get("starsUsername") or "",
        },
        period_label_text=body.periodLabel,
    )
    return {"text": text, "templateName": tpl["name"]}


@router.post("/staff/contract-templates/send")
async def staff_send_contract(
    body: RenderContractBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("pay_salary")),
):
    """Рендерит договор и отправляет сотруднику в Telegram."""
    from staff_payroll import get_staff_payout_profile, list_contract_templates, render_contract

    templates = await list_contract_templates()
    tpl = next((t for t in templates if t["id"] == body.templateId), None)
    if not tpl:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    profile = await get_staff_payout_profile(body.userId)
    if not profile:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    text = render_contract(
        tpl["body"],
        amount=body.amount,
        staff_name=profile.get("firstName") or "",
        staff_username=profile.get("username") or "",
        payout_type=body.payoutType,
        details={
            "cryptoNetwork": profile.get("cryptoNetwork") or "",
            "cryptoAddress": profile.get("cryptoAddress") or "",
            "cardBank": profile.get("cardBank") or "",
            "cardNumber": profile.get("cardNumber") or "",
            "cardHolder": profile.get("cardHolder") or "",
            "cardSbpPhone": profile.get("cardSbpPhone") or "",
            "starsUsername": profile.get("starsUsername") or "",
        },
        period_label_text=body.periodLabel,
    )
    chunk = text if len(text) <= 3500 else text[:3500] + "\n…"
    safe = chunk.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    notify_staff(
        body.userId,
        f"<tg-emoji emoji-id='5870521446382696672'>📄</tg-emoji> <b>Договор / инструкция по выплате</b>\n\n"
        f"<pre>{safe}</pre>"
        f"\n<blockquote><b>Виво-Эпсилон</b></blockquote>",
    )
    await log_admin_action(
        user_id, "contract_send",
        target_type="staff", target_id=str(body.userId),
        details={"templateId": body.templateId, "amount": body.amount},
        ip=_get_client_ip(request),
    )
    return {"ok": True, "text": text}


@router.post("/staff/my-salary/{salary_id}/appeal")
async def staff_appeal_salary(
    salary_id: int,
    body: AppealBody,
    request: Request,
    user_id: int = Depends(require_active_admin),
):
    ok = await create_salary_appeal(salary_id, user_id, body.reason.strip())
    if not ok:
        raise HTTPException(status_code=409, detail="Апелляция недоступна или уже подана")
    await log_admin_action(
        user_id, "salary_appeal",
        target_type="salary",
        target_id=str(salary_id),
        details={"reason": body.reason.strip()},
        ip=_get_client_ip(request),
    )
    return {"ok": True}


@router.get("/staff/appeals")
async def staff_list_appeals(
    _user_id: int = Depends(require_admin_permission("set_salary")),
):
    return {"items": await list_open_appeals()}


@router.post("/staff/appeals/{appeal_id}/resolve")
async def staff_resolve_appeal(
    appeal_id: int,
    body: ResolveAppealBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("set_salary")),
):
    appellant_id = await resolve_salary_appeal(appeal_id, body.resolution.strip(), user_id)
    if appellant_id is None:
        raise HTTPException(status_code=409, detail="Апелляция не найдена или уже рассмотрена")
    await log_admin_action(
        user_id, "salary_appeal_resolve",
        target_type="salary",
        target_id=str(appeal_id),
        details={"resolution": body.resolution.strip()},
        ip=_get_client_ip(request),
    )
    res_txt = body.resolution.strip()
    notify_staff(
        appellant_id,
        "<tg-emoji emoji-id='5400250414929041085'>⚖️</tg-emoji> <b>Ваша апелляция по зарплате рассмотрена.</b>"
        + (f" <b>Решение : {res_txt}</b>" if res_txt else ""),
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Staff: реестр выплат, долги, KPI, отчёты
# ---------------------------------------------------------------------------


def _period_range(period: str):
    from datetime import datetime, timedelta, timezone
    now_dt = datetime.now(timezone.utc)
    if period == "week":
        start = now_dt - timedelta(days=7)
    elif period == "all":
        start = datetime(2000, 1, 1, tzinfo=timezone.utc)
    else:  # month
        start = now_dt - timedelta(days=30)
    return start, now_dt + timedelta(days=1)


@router.get("/staff/ledger")
async def staff_ledger(
    period: str = Query("month", pattern=r"^(week|month|all)$"),
    userId: int | None = Query(None, ge=1),
    _user_id: int = Depends(require_admin_permission("pay_salary")),
):
    date_from, date_to = _period_range(period)
    data = await list_payments(date_from, date_to, userId)
    return {"period": period, **data}


@router.get("/staff/ledger/export")
async def staff_ledger_export(
    period: str = Query("month", pattern=r"^(week|month|all)$"),
    _user_id: int = Depends(require_admin_permission("pay_salary")),
):
    import csv
    import io
    from fastapi.responses import StreamingResponse

    date_from, date_to = _period_range(period)
    data = await list_payments(date_from, date_to, None)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Дата", "Сотрудник", "Роль", "Сумма", "Способ", "Тип", "TXID", "Выплатил"])
    for it in data["items"]:
        name = it["firstName"] or (f"@{it['username']}" if it["username"] else str(it["userId"]))
        writer.writerow([
            it["paidAt"] or "", name, it["role"] or "", it["amount"],
            it["method"] or "", it["kind"], it["txid"] or "", it["paidBy"] or "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=payments_{period}.csv"},
    )


@router.get("/staff/unpaid")
async def staff_unpaid(
    _user_id: int = Depends(require_admin_permission("set_salary")),
):
    return {"items": await list_unpaid(current_week_start())}


@router.get("/staff/members/{member_id}/stats")
async def staff_member_stats(
    member_id: int,
    period: str = Query("week", pattern=r"^(week|month|all)$"),
    _user_id: int = Depends(require_admin_permission("manage_staff")),
):
    date_from, _ = _period_range(period)
    return {"period": period, **await get_member_stats(member_id, date_from)}


@router.get("/staff/leaderboard")
async def staff_leaderboard(
    period: str = Query("week", pattern=r"^(week|month|all)$"),
    _user_id: int = Depends(require_admin_permission("manage_staff")),
):
    date_from, _ = _period_range(period)
    return {"period": period, "items": await get_leaderboard(date_from)}


@router.post("/staff/reminders/send")
async def staff_send_reminder(
    user_id: int = Depends(require_admin_permission("pay_salary")),
):
    from staff_notify import build_salary_reminder, notify_owners
    text = await build_salary_reminder()
    if not text:
        return {"ok": True, "sent": False, "detail": "Нет ожидающих/невыплаченных начислений"}
    notify_owners(text)
    return {"ok": True, "sent": True}


@router.get("/staff/payouts/pending")
async def staff_pending_payouts(
    _user_id: int = Depends(require_admin_permission("pay_salary")),
):
    return {"items": await list_pending_payouts()}


@router.post("/staff/payouts/pending/{payout_id}/confirm")
async def staff_confirm_payout(
    payout_id: int,
    request: Request,
    user_id: int = Depends(require_admin_permission("pay_salary")),
):
    p = await get_pending_payout(payout_id)
    if not p:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    if int(p["requested_by"]) == user_id:
        raise HTTPException(status_code=403, detail="Нужно подтверждение другого владельца")

    source = p.get("source") or "salary"
    if source == "bonus" or p.get("bonus_id"):
        from staff_payroll import add_bonus_payment
        result = await add_bonus_payment(
            int(p["bonus_id"]), user_id, int(p["amount"]),
            method=p["method"], kind=p["kind"], txid=p["txid"], proof=p["proof"],
        )
        target_type, target_id = "bonus", str(p["bonus_id"])
    else:
        if not p.get("salary_id"):
            await delete_pending_payout(payout_id)
            raise HTTPException(status_code=409, detail="Битый запрос выплаты")
        result = await add_salary_payment(
            int(p["salary_id"]), user_id, int(p["amount"]),
            method=p["method"], kind=p["kind"], txid=p["txid"], proof=p["proof"],
        )
        target_type, target_id = "salary", str(p["salary_id"])

    if not result:
        await delete_pending_payout(payout_id)
        raise HTTPException(status_code=409, detail="Начисление уже выплачено/недоступно")
    await delete_pending_payout(payout_id)
    await log_admin_action(
        user_id, "salary_pay_cosign",
        target_type=target_type, target_id=target_id,
        details={"amount": result["amount"]}, ip=_get_client_ip(request),
    )
    notify_staff(int(result["userId"]), f"<tg-emoji emoji-id='4958926882994127612'>💰</tg-emoji> <b>Для вас была проведена выплата : {result['amount']}. Остаток : {result['remaining']}.</b>")
    return {"ok": True, **result}


@router.delete("/staff/payouts/pending/{payout_id}")
async def staff_cancel_payout(
    payout_id: int,
    _user_id: int = Depends(require_admin_permission("pay_salary")),
):
    await delete_pending_payout(payout_id)
    return {"ok": True}


# --- Заметки о сотруднике ---

@router.get("/staff/members/{member_id}/notes")
async def staff_member_notes(member_id: int, _u: int = Depends(require_admin_permission("manage_staff"))):
    return {"items": await list_staff_notes(member_id)}


@router.post("/staff/members/{member_id}/notes")
async def staff_member_note_add(
    member_id: int, body: StaffNoteBody, request: Request,
    user_id: int = Depends(require_admin_permission("manage_staff")),
):
    note_id = await add_staff_note(member_id, user_id, body.text.strip())
    return {"ok": True, "id": note_id}


@router.delete("/staff/members/{member_id}/notes/{note_id}")
async def staff_member_note_delete(
    member_id: int, note_id: int,
    _u: int = Depends(require_admin_permission("manage_staff")),
):
    await delete_staff_note(note_id)
    return {"ok": True}


# --- Страйки ---

@router.get("/staff/members/{member_id}/strikes")
async def staff_member_strikes(member_id: int, _u: int = Depends(require_admin_permission("manage_staff"))):
    return {"items": await list_strikes(member_id)}


@router.delete("/staff/members/{member_id}/strikes/{strike_id}")
async def staff_member_strike_remove(
    member_id: int, strike_id: int,
    _u: int = Depends(require_admin_permission("manage_staff")),
):
    ok = await remove_strike(strike_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Страйк не найден или уже истёк")
    return {"ok": True}


@router.post("/staff/members/{member_id}/strikes")
async def staff_member_strike_add(
    member_id: int, body: StrikeBody, request: Request,
    user_id: int = Depends(require_admin_permission("manage_staff")),
):
    sid = await add_strike(member_id, body.reason.strip(), user_id)
    await log_admin_action(
        user_id, "staff_strike", target_type="staff", target_id=str(member_id),
        details={"reason": body.reason.strip()}, ip=_get_client_ip(request),
    )
    notify_staff(member_id, f"<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>Вам выдан страйк : {body.reason.strip()} (действует 30 дней).</b>")
    return {"ok": True, "id": sid}


# --- Доступность (отпуск/афк) ---

@router.post("/staff/members/{member_id}/availability")
async def staff_member_availability(
    member_id: int, body: AvailabilityBody, request: Request,
    user_id: int = Depends(require_admin_permission("manage_staff")),
):
    until = _parse_dt(body.until) if body.until else None
    ok = await set_availability(member_id, body.availability, until)
    if not ok:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    await log_admin_action(
        user_id, "staff_availability", target_type="staff", target_id=str(member_id),
        details={"availability": body.availability}, ip=_get_client_ip(request),
    )
    return {"ok": True}


# --- Смены ---

@router.get("/staff/shifts")
async def staff_shifts_list(
    userId: int | None = Query(None, ge=1),
    _u: int = Depends(require_admin_permission("manage_staff")),
):
    from datetime import datetime, timedelta, timezone
    since = datetime.now(timezone.utc) - timedelta(days=7)
    return {"items": await list_shifts(since, userId)}


@router.post("/staff/shifts")
async def staff_shift_add(
    body: ShiftBody, request: Request,
    user_id: int = Depends(require_admin_permission("manage_staff")),
):
    starts = _parse_dt(body.startsAt)
    ends = _parse_dt(body.endsAt)
    if not starts or not ends or ends <= starts:
        raise HTTPException(status_code=400, detail="Неверный интервал смены")
    sid = await add_shift(body.userId, starts, ends, body.note.strip(), user_id)
    return {"ok": True, "id": sid}


@router.delete("/staff/shifts/{shift_id}")
async def staff_shift_delete(
    shift_id: int, _u: int = Depends(require_admin_permission("manage_staff")),
):
    await delete_shift(shift_id)
    return {"ok": True}


# --- Дашборд / аудит сотрудника ---

@router.get("/staff/members/{member_id}/card")
async def staff_member_card(
    member_id: int,
    period: str = Query("week", pattern=r"^(week|month|all)$"),
    _u: int = Depends(require_admin_permission("manage_staff")),
):
    date_from, _ = _period_range(period)
    return {"period": period, **await get_member_card(member_id, date_from)}


@router.get("/staff/members/{member_id}/audit")
async def staff_member_audit(
    member_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _u: int = Depends(require_admin_permission("manage_staff")),
):
    return await list_admin_audit(admin_user_id=member_id, limit=limit, offset=offset)


# --- Шаблоны вопросов анкеты ---

@router.get("/staff/questions")
async def staff_questions_list(_u: int = Depends(require_admin_permission("manage_staff"))):
    return {"items": await list_application_questions(enabled_only=False)}


@router.post("/staff/questions")
async def staff_question_upsert(
    body: QuestionBody, _u: int = Depends(require_admin_permission("assign_roles")),
):
    qid = await upsert_application_question(
        body.key, body.label.strip(), body.type, body.required, body.sortOrder, body.enabled, body.id,
    )
    return {"ok": True, "id": qid}


@router.delete("/staff/questions/{question_id}")
async def staff_question_delete(
    question_id: int, _u: int = Depends(require_admin_permission("assign_roles")),
):
    await delete_application_question(question_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Staff: доказательная отчётность и жалобы
# ---------------------------------------------------------------------------


@router.get("/staff/members/{member_id}/actions")
async def staff_member_actions(
    member_id: int,
    _user_id: int = Depends(require_admin_permission("manage_staff")),
):
    return {"items": await list_staff_actions(member_id)}


@router.get("/staff/complaints")
async def staff_get_complaints(
    status: str | None = Query(None),
    _user_id: int = Depends(require_admin_permission("manage_staff")),
):
    if status and status not in {"open", "in_progress", "resolved"}:
        raise HTTPException(status_code=400, detail="Неверный статус")
    return {"items": await list_complaints(status)}


@router.post("/staff/complaints")
async def staff_create_complaint(
    body: ComplaintBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("manage_staff")),
):
    target = await get_admin_account(body.targetAdminId)
    if not target:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    if target.get("role") == ROLE_OWNER:
        raise HTTPException(status_code=400, detail="Нельзя подать жалобу на владельца")

    complaint_id = await create_complaint(
        body.targetAdminId, body.subject.strip(), body.reason.strip(), user_id,
    )
    await log_admin_action(
        user_id, "complaint_create",
        target_type="staff", target_id=str(body.targetAdminId),
        details={"complaintId": complaint_id},
        ip=_get_client_ip(request),
    )
    return {"ok": True, "complaintId": complaint_id}


@router.post("/staff/complaints/{complaint_id}/take")
async def staff_take_complaint(
    complaint_id: int,
    request: Request,
    user_id: int = Depends(require_admin_permission("manage_staff")),
):
    ok, target_id = await take_complaint(complaint_id, user_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Жалоба не найдена или уже в работе")
    await log_admin_action(
        user_id, "complaint_take",
        target_type="complaint", target_id=str(complaint_id),
        ip=_get_client_ip(request),
    )
    if target_id:
        notify_staff(
            target_id,
            "<tg-emoji emoji-id='5213205860498549992'>⚠️</tg-emoji> <b>На вас поступила жалоба которая уже ушла на рассмотрение старшим составом Эпсилона</b>"
            "<b>Зайдите в панель → «Жалобы на меня» и приложите доказательства.</b>\n<blockquote><b>Виво-Эпсилон</b></blockquote>",
        )
    return {"ok": True}


@router.post("/staff/complaints/{complaint_id}/resolve")
async def staff_resolve_complaint(
    complaint_id: int,
    body: ComplaintResolveBody,
    request: Request,
    user_id: int = Depends(require_admin_permission("manage_staff")),
):
    ok, target_id = await resolve_complaint(complaint_id, body.resolution.strip(), user_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Жалоба не найдена или уже закрыта")

    res_txt = body.resolution.strip()
    extras = []
    # Авто-штраф к зарплате + страйк, если жалоба подтверждена
    if target_id and body.penalty > 0:
        applied = await add_penalty_to_current_salary(
            target_id, body.penalty, f"жалоба #{complaint_id}: {res_txt}"[:300], user_id,
        )
        if applied:
            extras.append(f"штраф {body.penalty}")
    if target_id and body.strike:
        await add_strike(target_id, f"жалоба #{complaint_id}: {res_txt}"[:500], user_id, complaint_id)
        extras.append("страйк")

    await log_admin_action(
        user_id, "complaint_resolve",
        target_type="complaint", target_id=str(complaint_id),
        details={"resolution": res_txt, "penalty": body.penalty, "strike": body.strike},
        ip=_get_client_ip(request),
    )
    if target_id:
        suffix = f" <b>Применено : {', '.join(extras)}.</b>" if extras else ""
        notify_staff(
            target_id,
            "<tg-emoji emoji-id='5400250414929041085'>⚖️</tg-emoji> <b>Жалоба на вас рассмотрена и закрыта.</b>"
            + (f" <b>Решение : {res_txt}</b>" if res_txt else "") + suffix + (f"<blockquote><b>Виво-Эпсилон</b></blockquote>"),
        )
    return {"ok": True, "applied": extras}


@router.get("/staff/my-complaints")
async def staff_my_complaints(user_id: int = Depends(require_active_admin)):
    """Открытые жалобы на текущего сотрудника — чтобы приложить доказательства."""
    return {"items": await list_complaints_for_target(user_id)}


@router.post("/staff/my-complaints/{complaint_id}/evidence")
async def staff_submit_complaint_evidence(
    complaint_id: int,
    body: ComplaintEvidenceBody,
    request: Request,
    user_id: int = Depends(require_active_admin),
):
    if not await submit_complaint_evidence(complaint_id, user_id, body.evidence.strip()):
        raise HTTPException(
            status_code=409,
            detail="Жалоба не найдена, не в работе или адресована не вам",
        )
    await log_admin_action(
        user_id, "complaint_evidence",
        target_type="complaint", target_id=str(complaint_id),
        ip=_get_client_ip(request),
    )
    return {"ok": True}


@router.get("/dashboard/stats")
async def admin_dashboard_stats(_user_id: int = Depends(require_admin_session)):
    stats = await get_dashboard_stats()
    stats.update(await get_online_summary())
    return stats


@router.get("/dashboard/online")
async def admin_dashboard_online(_user_id: int = Depends(require_admin_session)):
    return await get_online_summary()


@router.get("/dashboard/online/day")
async def admin_dashboard_online_day(
    day: date = Query(..., description="Дата YYYY-MM-DD (UTC)"),
    _user_id: int = Depends(require_admin_session),
):
    return await get_day_analytics(day)


@router.get("/dashboard/online/range")
async def admin_dashboard_online_range(
    from_: date = Query(..., alias="from", description="Начало периода YYYY-MM-DD"),
    to: date = Query(..., description="Конец периода YYYY-MM-DD"),
    _user_id: int = Depends(require_admin_session),
):
    try:
        return await get_range_analytics(from_, to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/dashboard/server")
async def admin_dashboard_server(_user_id: int = Depends(require_admin_session)):
    maintenance = await get_maintenance_enabled()
    return {
        "ok": True,
        "maintenance": maintenance,
        "adminEnabled": ADMIN_ENABLED,
        "adminBotConfigured": bool(ADMIN_BOT_TOKEN),
        "jwtConfigured": bool(ADMIN_JWT_SECRET),
    }


@router.get("/system/maintenance")
async def admin_get_maintenance(_user_id: int = Depends(require_admin_permission("manage_settings"))):
    enabled = await get_maintenance_enabled()
    return {"maintenance": enabled}


@router.post("/system/maintenance")
async def admin_set_maintenance(
    body: MaintenanceBody,
    user_id: int = Depends(require_admin_permission("manage_settings")),
):
    enabled = await set_maintenance_enabled(body.enabled, admin_user_id=user_id)
    return {"maintenance": enabled, "ok": True}


class SystemSettingsBody(BaseModel):
    # economy/farm settings live only in EconomySettingsBody/FarmSettingsBody now -
    # editing the same field from two screens caused drift (see settings_history gap).
    # seed economy
    harvestSeedDropPercent: int | None = Field(default=None, ge=0, le=100)
    dailySeedAmount: int | None = Field(default=None, ge=1, le=50)
    starterTreeSeeds: int | None = Field(default=None, ge=0, le=100)
    starterTobaccoSeeds: int | None = Field(default=None, ge=0, le=100)
    starterWater: int | None = Field(default=None, ge=0, le=100)
    starterAxe: int | None = Field(default=None, ge=0, le=100)
    # system
    adminSessionMinutes: int | None = Field(default=None, ge=5, le=1_440)
    maintenance: bool | None = None
    model_config = {"extra": "forbid"}


@router.get("/system/settings")
async def admin_system_settings_get(
    _admin_id: int = Depends(require_admin_permission("manage_settings")),
):
    return await get_all_settings()


@router.post("/system/settings")
async def admin_system_settings_set(
    body: SystemSettingsBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_settings")),
):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        result = await update_settings(fields, admin_user_id=admin_id)
        await log_admin_action(
            admin_id, "settings_change",
            target_type="setting",
            target_label=f"Изменено настроек: {len(fields)}",
            details={"keys": list(fields.keys())},
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/system/settings/history")
async def admin_system_settings_history(
    category: str | None = Query(None, max_length=32),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("manage_settings")),
):
    return await get_settings_history(category=category, limit=limit, offset=offset)


def _strip_player_sensitive(request: Request, profile: dict) -> dict:
    """Прячет IP/устройство/гео/историю входов, если нет права view_player_sensitive."""
    account = getattr(request.state, "admin_account", None) or {}
    if "view_player_sensitive" in set(account.get("permissions") or []):
        return profile
    profile.pop("device", None)
    profile.pop("network", None)
    profile.pop("loginHistory", None)
    return profile


@router.get("/users/search")
async def admin_users_search(
    q: str = Query(..., min_length=1, max_length=128),
    _admin_id: int = Depends(require_admin_permission("view_players")),
):
    return {"results": await search_users(q)}


@router.get("/users/{target_user_id}/inventory")
async def admin_user_inventory(
    target_user_id: int,
    _admin_id: int = Depends(require_admin_permission("view_players")),
):
    try:
        items = await get_player_inventory(target_user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"items": items}


@router.get("/users/{target_user_id}")
async def admin_user_profile(
    target_user_id: int,
    request: Request,
    _admin_id: int = Depends(require_admin_permission("view_players")),
):
    profile = await get_user_admin_profile(target_user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Игрок не найден")
    return _strip_player_sensitive(request, profile)


@router.get("/accounts/recent")
async def admin_accounts_recent(
    limit: int = Query(30, ge=1, le=50),
    _admin_id: int = Depends(require_admin_permission("view_accounts")),
):
    return {"results": await list_recent_accounts(limit=limit)}


@router.get("/accounts/search")
async def admin_accounts_search(
    q: str = Query(..., min_length=1, max_length=128),
    _admin_id: int = Depends(require_admin_permission("view_accounts")),
):
    return {"results": await search_accounts(q)}


@router.get("/accounts/{target_user_id}")
async def admin_account_profile(
    target_user_id: int,
    _admin_id: int = Depends(require_admin_permission("view_accounts")),
):
    profile = await get_account_profile(target_user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return profile


@router.get("/users/{target_user_id}/audit")
async def admin_user_audit(
    target_user_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("view_players")),
):
    return await get_user_audit_history(target_user_id, limit=limit, offset=offset)


@router.get("/users/{target_user_id}/cute-history")
async def admin_user_cute_history(
    target_user_id: int,
    dateFrom: str | None = Query(None, max_length=32),
    dateTo: str | None = Query(None, max_length=32),
    direction: str | None = Query(None, pattern="^(in|out)$"),
    q: str | None = Query(None, max_length=200),
    onlyTransfers: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    # История кут — только для владельцев (не для сотрудников с view_players)
    _admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    return await get_user_cute_history(
        target_user_id,
        date_from=dateFrom,
        date_to=dateTo,
        direction=direction,
        q=q,
        only_transfers=onlyTransfers,
        limit=limit,
        offset=offset,
    )


@router.post("/users/{target_user_id}/balance")
async def admin_user_balance(
    target_user_id: int,
    body: UserBalanceBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("adjust_balance")),
):
    try:
        result = await admin_adjust_balance(
            target_user_id,
            body.delta,
            admin_user_id=admin_id,
            note=body.note,
        )
        await log_admin_action(
            admin_id, "balance_change",
            target_type="user", target_id=str(target_user_id),
            target_label=f"Игрок {target_user_id}",
            details={"delta": body.delta, "note": body.note or "", "balanceAfter": result.get("balance")},
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users/{target_user_id}/items")
async def admin_user_items(
    target_user_id: int,
    body: UserItemBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("give_items")),
):
    try:
        result = await admin_adjust_item(
            target_user_id,
            body.itemId,
            body.delta,
            admin_user_id=admin_id,
            note=body.note,
        )
        await log_admin_action(
            admin_id, "item_grant",
            target_type="user", target_id=str(target_user_id),
            target_label=f"Игрок {target_user_id}",
            details={
                "itemId": body.itemId, "delta": body.delta, "note": body.note or "",
                "countAfter": result.get("countAfter"),
            },
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users/{target_user_id}/ban")
async def admin_user_ban(
    target_user_id: int,
    body: UserBanBody,
    request: Request,
    admin_id: int = Depends(require_active_admin),
):
    # Бан — право moderate_ban; разбан (отмена чужого решения) — moderate_unban.
    account = getattr(request.state, "admin_account", None) or {}
    perms = set(account.get("permissions") or [])
    needed = "moderate_ban" if body.banned else "moderate_unban"
    if needed not in perms:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    # И бан, и разбан требуют причину и доказательства.
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="Укажите причину")
    if not body.evidence.strip():
        raise HTTPException(status_code=400, detail="Приложите доказательства (скриншоты/логи)")

    try:
        has_photo = bool(body.proofMediaId.strip()) and body.banned
        result = await admin_set_banned(
            target_user_id,
            body.banned,
            admin_user_id=admin_id,
            reason=body.reason,
            notify=not has_photo,  # если есть фото — уведомление придёт с ним
        )
        action = "ban_user" if body.banned else "unban_user"
        await log_admin_action(
            admin_id, action,
            target_type="user", target_id=str(target_user_id),
            target_label=f"Игрок {target_user_id}",
            details={"reason": body.reason or ""},
            ip=_get_client_ip(request),
        )
        # Токен-владелец пруфа: панель грузит фото через BOT_TOKEN/ADMIN_BOT_TOKEN
        # (см. /users/upload-evidence), тем же и скачаем из архива.
        _proof_id = body.proofMediaId.strip() or None
        _proof_token = None
        if _proof_id:
            from config import BOT_TOKEN as _BT, ADMIN_BOT_TOKEN as _ABT
            _proof_token = _BT or _ABT or None
        await log_staff_action(
            admin_id, "ban" if body.banned else "unban", target_user_id,
            body.reason.strip(), body.evidence.strip(),
            proof_media_id=_proof_id,
            # Блокировка из веб-панели действует на весь проект (users.banned) -
            # это охват «во всём проекте», как «банфулл» у бота.
            scope="full", chat_id=0,
            proof_bot_token=_proof_token,
        )
        # Если есть фото-доказательство — отправляем игроку вместе с уведомлением о бане
        proof_id = body.proofMediaId.strip()
        if proof_id and body.banned:
            import asyncio as _asyncio
            _asyncio.create_task(_send_ban_photo_to_player(target_user_id, proof_id, body.reason.strip()))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users/{target_user_id}/onboarding/reset")
async def admin_user_onboarding_reset(
    target_user_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_settings")),
):
    try:
        result = await admin_reset_onboarding(target_user_id, admin_user_id=admin_id)
        await log_admin_action(
            admin_id, "onboarding_reset",
            target_type="user", target_id=str(target_user_id),
            target_label=f"Игрок {target_user_id}",
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/economy/overview")
async def admin_economy_overview(_admin_id: int = Depends(require_admin_permission("manage_economy"))):
    return await get_economy_overview()


@router.get("/economy/stats")
async def admin_economy_stats(_admin_id: int = Depends(require_admin_permission("manage_economy"))):
    return await get_economy_stats()


@router.get("/economy/settings")
async def admin_economy_settings_get(_admin_id: int = Depends(require_admin_permission("manage_economy"))):
    return await get_economy_settings_payload()


@router.post("/economy/settings")
async def admin_economy_settings_set(
    body: EconomySettingsBody,
    admin_id: int = Depends(require_admin_permission("manage_economy")),
):
    try:
        return await update_economy_settings(
            default_balance=body.defaultBalance,
            clear_cost=body.clearCost,
            admin_user_id=admin_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/economy/dex")
async def admin_economy_dex_list(
    q: str = Query("", max_length=128),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("manage_economy")),
):
    return await list_dex_items(search=q, limit=limit, offset=offset)


@router.patch("/economy/dex/{item_id}")
async def admin_economy_dex_patch(
    item_id: str,
    body: DexItemPatchBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_economy")),
):
    try:
        result = await update_dex_item(
            item_id,
            price=body.price,
            dis=body.dis,
            remains=body.remains,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "economy_dex_update",
            target_type="dex_item", target_id=item_id, target_label=result.get("name") or item_id,
            details={"price": body.price, "dis": body.dis, "remains": body.remains},
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/economy/grants")
async def admin_economy_grants(
    body: BulkGrantBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_economy")),
):
    if body.delta == 0:
        raise HTTPException(status_code=400, detail="Сумма не может быть 0")
    try:
        result = await bulk_grant_kut(
            body.delta,
            target=body.target,
            note=body.note,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "bulk_grant",
            target_type="players", target_label=f"Массовая выдача ({body.target})",
            details={
                "delta": body.delta, "target": body.target, "note": body.note or "",
                "success": result.get("success"), "skipped": result.get("skipped"),
                "totalKut": result.get("totalKut"),
            },
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/market/overview")
async def admin_market_overview(_admin_id: int = Depends(require_admin_permission("view_market"))):
    return await get_market_overview()


@router.get("/market/listings")
async def admin_market_listings(
    q: str = Query("", max_length=128),
    itemId: str = Query("", max_length=128),
    sellerId: int | None = Query(None, ge=1),
    suspicious: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("view_market")),
):
    return await list_active_listings(
        q=q,
        item_id=itemId,
        seller_id=sellerId,
        suspicious_only=suspicious,
        limit=limit,
        offset=offset,
    )


@router.post("/market/listings/{listing_id}/cancel")
async def admin_market_cancel(
    listing_id: int,
    body: MarketCancelBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("market_cancel")),
):
    try:
        result = await admin_cancel_listing(
            listing_id,
            admin_user_id=admin_id,
            reason=body.reason,
        )
        await log_admin_action(
            admin_id, "market_cancel",
            target_type="listing", target_id=str(listing_id),
            target_label=result.get("itemName") or f"Лот #{listing_id}",
            details={
                "reason": body.reason or "", "itemId": result.get("itemId"),
                "quantity": result.get("returnedQuantity"), "price": result.get("price"),
            },
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/farm/overview")
async def admin_farm_overview(_admin_id: int = Depends(require_admin_permission("manage_farm"))):
    return await get_farm_overview()


@router.get("/farm/settings")
async def admin_farm_settings_get(_admin_id: int = Depends(require_admin_permission("manage_farm"))):
    return await get_farm_settings_payload()


@router.post("/farm/settings")
async def admin_farm_settings_set(
    body: FarmSettingsBody,
    admin_id: int = Depends(require_admin_permission("manage_farm")),
):
    import logging as _log
    try:
        return await update_farm_settings(
            tree_grow_seconds=body.treeGrowSeconds,
            tobacco_grow_seconds=body.tobaccoGrowSeconds,
            max_plots=body.maxPlots,
            plot_price_step=body.plotPriceStep,
            water_interval_seconds=body.waterIntervalSeconds,
            wilt_grace_seconds=body.wiltGraceSeconds,
            water_cost_per_use=body.waterCostPerUse,
            admin_user_id=admin_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        _log.getLogger("admin.farm_settings").exception("FARM SETTINGS ERROR: %s", e)
        raise


@router.get("/farm/users/search")
async def admin_farm_users_search(
    q: str = Query(..., min_length=1, max_length=128),
    _admin_id: int = Depends(require_admin_permission("manage_farm")),
):
    return {"results": await search_users(q)}


@router.get("/farm/users/{target_user_id}")
async def admin_farm_user(
    target_user_id: int,
    _admin_id: int = Depends(require_admin_permission("manage_farm")),
):
    farm = await get_user_farm_admin(target_user_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Игрок не найден")
    return farm


@router.post("/farm/users/{target_user_id}/reset")
async def admin_farm_user_reset(
    target_user_id: int,
    request: Request,
    plotId: int | None = Query(None, ge=1, le=100),
    admin_id: int = Depends(require_admin_permission("manage_farm")),
):
    try:
        result = await reset_user_plots(
            target_user_id,
            plot_id=plotId,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "farm_reset",
            target_type="user", target_id=str(target_user_id),
            target_label=f"Игрок {target_user_id}",
            details={"plotId": plotId, "plotsReset": result.get("plotsReset")},
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/farm/global-reset")
async def admin_farm_global_reset(
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_farm")),
):
    try:
        result = await global_farm_restart(admin_user_id=admin_id)
        await log_admin_action(
            admin_id, "farm_global_reset",
            target_type="system", target_label="Глобальный сброс фермы",
            details={"plotsReset": result.get("plotsReset")},
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/content/overview")
async def admin_content_overview(_admin_id: int = Depends(require_admin_permission("manage_content"))):
    return await get_content_overview()


@router.get("/content/dex")
async def admin_content_dex_list(
    q: str = Query("", max_length=128),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    scope: str = Query("all", max_length=16),
    _admin_id: int = Depends(require_admin_permission("manage_content")),
):
    return await list_dex_items_admin(search=q, limit=limit, offset=offset, scope=scope)


@router.post("/content/dex")
async def admin_content_dex_create(
    body: DexItemCreateBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await create_dex_item(
            name=body.name,
            emoji=body.emoji,
            name1=body.name1,
            price=body.price,
            dis=body.dis,
            remains=body.remains,
            sorting=body.sorting,
            bio=body.bio,
            use=body.use,
            bonus=body.bonus,
            craft=body.craft,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "dex_create",
            target_type="dex_item", target_label=body.name,
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/content/dex/{item_id}")
async def admin_content_dex_patch(
    item_id: str,
    body: DexItemMetaBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await update_dex_item_meta(
            item_id,
            name=body.name,
            emoji=body.emoji,
            name1=body.name1,
            price=body.price,
            dis=body.dis,
            remains=body.remains,
            sorting=body.sorting,
            bio=body.bio,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "dex_update",
            target_type="dex_item", target_id=item_id, target_label=item_id,
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/content/crops")
async def admin_content_crop_create(
    body: CropCreateBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await create_crop(
            key=body.key,
            display_name=body.displayName,
            seed_item_id=body.seedItemId,
            grow_seconds=body.growSeconds,
            harvest_tool_item_id=body.harvestToolItemId,
            harvest_tool_cost=body.harvestToolCost,
            water_item_id=body.waterItemId,
            water_cost_per_use=body.waterCostPerUse,
            sprite_key=body.spriteKey,
            enabled=body.enabled,
            harvest_drops=[drop.model_dump() for drop in body.harvestDrops],
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "crop_create",
            target_type="crop", target_id=body.key, target_label=body.displayName,
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/content/crops/{crop_id}")
async def admin_content_crop_patch(
    crop_id: int,
    body: CropUpdateBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await update_crop(
            crop_id,
            display_name=body.displayName,
            seed_item_id=body.seedItemId,
            grow_seconds=body.growSeconds,
            harvest_tool_item_id=body.harvestToolItemId,
            harvest_tool_cost=body.harvestToolCost,
            water_item_id=body.waterItemId,
            water_cost_per_use=body.waterCostPerUse,
            sprite_key=body.spriteKey,
            enabled=body.enabled,
            harvest_drops=(
                [drop.model_dump() for drop in body.harvestDrops]
                if body.harvestDrops is not None
                else None
            ),
            clear_harvest_tool=body.clearHarvestTool,
            clear_water_item=body.clearWaterItem,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "crop_update",
            target_type="crop", target_id=str(crop_id),
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/content/crops/{crop_id}")
async def admin_content_crop_delete(
    crop_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await delete_crop(crop_id, admin_user_id=admin_id)
        await log_admin_action(
            admin_id, "crop_delete",
            target_type="crop", target_id=str(crop_id),
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/content/craft")
async def admin_content_craft_create(
    body: CraftRecipeCreateBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await create_craft_recipe(
            key=body.key,
            display_name=body.displayName,
            result_item_id=body.resultItemId,
            ingredient_a_id=body.ingredientAId,
            ingredient_b_id=body.ingredientBId,
            success_percent=body.successPercent,
            enabled=body.enabled,
            remains=body.remains,
            result_qty=body.resultQty,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "craft_create",
            target_type="craft_recipe", target_id=body.key, target_label=body.displayName,
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/content/craft/{recipe_id}")
async def admin_content_craft_patch(
    recipe_id: int,
    body: CraftRecipeUpdateBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await update_craft_recipe(
            recipe_id,
            display_name=body.displayName,
            result_item_id=body.resultItemId,
            ingredient_a_id=body.ingredientAId,
            ingredient_b_id=body.ingredientBId,
            success_percent=body.successPercent,
            enabled=body.enabled,
            remains=body.remains,
            result_qty=body.resultQty,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "craft_update",
            target_type="craft_recipe", target_id=str(recipe_id),
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/content/craft/{recipe_id}")
async def admin_content_craft_delete(
    recipe_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await delete_craft_recipe(recipe_id, admin_user_id=admin_id)
        await log_admin_action(
            admin_id, "craft_delete",
            target_type="craft_recipe", target_id=str(recipe_id),
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/content/craft-map")
async def admin_content_craft_map(
    _admin_id: int = Depends(require_admin_permission("manage_content")),
):
    return await get_craft_map()


@router.post("/content/craft-map/positions")
async def admin_content_craft_map_positions(
    body: CraftMapPositionsBody,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    positions = [p.model_dump() for p in body.positions]
    return await save_craft_map_positions(positions, admin_user_id=admin_id)


@router.post("/content/quests")
async def admin_content_quest_create(
    body: QuestCreateBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await create_quest(
            key=body.key,
            period=body.period,
            action=body.action,
            target=body.target,
            title=body.title,
            description=body.description,
            emoji=body.emoji,
            enabled=body.enabled,
            target_scope=body.targetScope,
            target_crop_key=body.targetCropKey,
            target_item_id=body.targetItemId,
            rewards=[reward.model_dump() for reward in body.rewards],
            active_from=_parse_dt(body.activeFrom),
            active_until=_parse_dt(body.activeUntil),
            recurrence=body.recurrence,
            recurrence_end=_parse_dt(body.recurrenceEnd),
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "quest_create",
            target_type="quest", target_id=body.key,
            target_label=body.title or body.key,
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/content/quests/{quest_id}")
async def admin_content_quest_patch(
    quest_id: int,
    body: QuestUpdateBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    from admin_quests import _UNSET as _QU
    try:
        # When clearSchedule=True, explicitly set all scheduling fields to None.
        # Otherwise, only pass fields that were explicitly provided (others stay as _UNSET = don't touch).
        if body.clearSchedule:
            af = None
            au = None
            rec = None
            re_end = None
        else:
            af = _parse_dt(body.activeFrom) if body.activeFrom is not None else _QU
            au = _parse_dt(body.activeUntil) if body.activeUntil is not None else _QU
            rec = body.recurrence if body.recurrence is not None else _QU
            re_end = _parse_dt(body.recurrenceEnd) if body.recurrenceEnd is not None else _QU

        result = await update_quest(
            quest_id,
            period=body.period,
            action=body.action,
            target=body.target,
            title=body.title,
            description=body.description,
            emoji=body.emoji,
            enabled=body.enabled,
            target_scope=body.targetScope,
            target_crop_key=body.targetCropKey,
            target_item_id=body.targetItemId,
            rewards=(
                [reward.model_dump() for reward in body.rewards]
                if body.rewards is not None
                else None
            ),
            active_from=af,
            active_until=au,
            recurrence=rec,
            recurrence_end=re_end,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "quest_update",
            target_type="quest", target_id=str(quest_id),
            target_label=body.title or f"Квест #{quest_id}",
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/content/quests/{quest_id}")
async def admin_content_quest_delete(
    quest_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await delete_quest(quest_id, admin_user_id=admin_id)
        await log_admin_action(
            admin_id, "quest_delete",
            target_type="quest", target_id=str(quest_id),
            target_label=f"Квест #{quest_id}",
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/content/giveaways")
async def admin_content_giveaways_list(
    _admin_id: int = Depends(require_admin_permission("manage_content")),
):
    return await list_giveaways_admin()


@router.post("/content/giveaways")
async def admin_content_giveaway_create(
    body: GiveawayCreateBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await create_giveaway(
            title=body.title,
            description=body.description,
            emoji=body.emoji,
            rarity=body.rarity,
            prize_type=body.prizeType,
            prize_kut_amount=body.prizeKutAmount,
            prize_title=body.prizeTitle,
            prize_emoji=body.prizeEmoji,
            prize_description=body.prizeDescription,
            prize_animation_url=body.prizeAnimationUrl,
            prize_animation_type=body.prizeAnimationType,
            draw_type=body.drawType,
            ends_at=_parse_dt(body.endsAt),
            starts_at=_parse_dt(body.startsAt),
            conditions=[c.model_dump() for c in body.conditions],
            enabled=body.enabled,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "giveaway_create",
            target_type="giveaway", target_label=body.title,
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/content/giveaways/{giveaway_id}")
async def admin_content_giveaway_patch(
    giveaway_id: int,
    body: GiveawayUpdateBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    from admin_giveaways import _UNSET

    try:
        result = await update_giveaway(
            giveaway_id,
            title=body.title,
            description=body.description,
            emoji=body.emoji,
            rarity=body.rarity,
            prize_type=body.prizeType,
            prize_kut_amount=body.prizeKutAmount if body.prizeKutAmount is not None else _UNSET,
            prize_title=body.prizeTitle if body.prizeTitle is not None else _UNSET,
            prize_emoji=body.prizeEmoji if body.prizeEmoji is not None else _UNSET,
            prize_description=body.prizeDescription if body.prizeDescription is not None else _UNSET,
            prize_animation_url=body.prizeAnimationUrl if body.prizeAnimationUrl is not None else _UNSET,
            prize_animation_type=body.prizeAnimationType if body.prizeAnimationType is not None else _UNSET,
            draw_type=body.drawType,
            ends_at=_parse_dt(body.endsAt) if body.endsAt is not None else _UNSET,
            starts_at=_parse_dt(body.startsAt) if "startsAt" in body.model_fields_set else _UNSET,
            conditions=[c.model_dump() for c in body.conditions] if body.conditions is not None else None,
            enabled=body.enabled,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "giveaway_update",
            target_type="giveaway", target_id=str(giveaway_id),
            target_label=body.title or f"Розыгрыш #{giveaway_id}",
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/content/giveaways/{giveaway_id}")
async def admin_content_giveaway_cancel(
    giveaway_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await cancel_giveaway(giveaway_id, admin_user_id=admin_id)
        await log_admin_action(
            admin_id, "giveaway_cancel",
            target_type="giveaway", target_id=str(giveaway_id),
            target_label=f"Розыгрыш #{giveaway_id}",
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/content/giveaways/{giveaway_id}/complete")
async def admin_content_giveaway_complete(
    giveaway_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await complete_giveaway(giveaway_id, admin_user_id=admin_id)
        await log_admin_action(
            admin_id, "giveaway_complete",
            target_type="giveaway", target_id=str(giveaway_id),
            target_label=f"Розыгрыш #{giveaway_id}",
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── TG Bot quests (owner-only): +задание / +заданиеч ─────────────────────────


@router.get("/group-balance-level/overview")
async def admin_gbl_overview(
    _admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    return gbl_overview()


# ─── Soft Restart (только создатель проекта) ─────────────────────────────────


def _require_project_creator(admin_id: int) -> None:
    if not sr_is_creator(admin_id):
        raise HTTPException(status_code=403, detail="Только создатель проекта")


@router.get("/soft-restart/overview")
async def admin_sr_overview(
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    _require_project_creator(admin_id)
    return await sr_overview()


class SoftRestartSettingsBody(BaseModel):
    enabled: bool | None = None
    test: bool | None = None
    interval_sec: float | None = Field(default=None, ge=60, le=86400 * 7)
    initial_delay_sec: float | None = Field(default=None, ge=30, le=86400 * 7)
    grace_sec: float | None = Field(default=None, ge=0.5, le=120)
    model_config = {"extra": "forbid"}


@router.post("/soft-restart/settings")
async def admin_sr_save_settings(
    body: SoftRestartSettingsBody,
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    _require_project_creator(admin_id)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    cfg = await sr_save_settings(patch)
    try:
        await log_admin_action(
            admin_id, "soft_restart_settings",
            target_type="soft_restart",
            details={"keys": list(patch.keys())},
        )
    except Exception:
        pass
    return {"ok": True, "config": cfg, "status": (await sr_overview())["status"]}


class SoftRestartPresetBody(BaseModel):
    name: str = Field(min_length=2, max_length=32)
    model_config = {"extra": "forbid"}


@router.post("/soft-restart/preset")
async def admin_sr_preset(
    body: SoftRestartPresetBody,
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    _require_project_creator(admin_id)
    try:
        cfg = await sr_apply_preset(body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await log_admin_action(
            admin_id, "soft_restart_preset",
            target_type="soft_restart",
            details={"name": body.name},
        )
    except Exception:
        pass
    return {"ok": True, "config": cfg, "status": (await sr_overview())["status"]}


class SoftRestartNowBody(BaseModel):
    reason: str | None = Field(default="panel", max_length=64)
    model_config = {"extra": "forbid"}


@router.post("/soft-restart/restart")
async def admin_sr_restart(
    body: SoftRestartNowBody,
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    _require_project_creator(admin_id)
    result = await sr_queue_restart(body.reason or "panel")
    try:
        await log_admin_action(
            admin_id, "soft_restart_now",
            target_type="soft_restart",
            details={"reason": body.reason or "panel"},
        )
    except Exception:
        pass
    return result


class GroupBalanceLevelSettingsBody(BaseModel):
    enabled: bool | None = None
    level_0_cap: int | None = Field(default=None, ge=0, le=1_000_000)
    recommend_pct: float | None = Field(default=None, ge=0, le=100)
    health_success_min: float | None = Field(default=None, ge=0, le=10)
    health_primary_min: float | None = Field(default=None, ge=0, le=10)
    atmosphere_enabled: bool | None = None
    atmosphere_max_bonus_pct: float | None = Field(default=None, ge=0, le=200)
    society_snapshot_ttl_sec: float | None = Field(default=None, ge=60, le=86400)
    society_price_max_mult: float | None = Field(default=None, ge=1, le=10)
    donor_life_weight: float | None = Field(default=None, ge=0, le=1)
    donor_month_weight: float | None = Field(default=None, ge=0, le=1)
    society_activity_share: float | None = Field(default=None, ge=0, le=1)
    society_donor_share: float | None = Field(default=None, ge=0, le=1)
    society_synergy_share: float | None = Field(default=None, ge=0, le=1)
    society_activity_curve: float | None = Field(default=None, ge=0.5, le=3)
    raise_button_text: str | None = Field(default=None, max_length=64)
    system_title: str | None = Field(default=None, max_length=128)
    prices: dict[str, int] | None = None
    stake_caps: dict[str, int | None] | None = None
    badge_titles: dict[str, str] | None = None
    model_config = {"extra": "forbid"}


@router.post("/group-balance-level/settings")
async def admin_gbl_save_settings(
    body: GroupBalanceLevelSettingsBody,
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    result = gbl_save_settings(patch)
    try:
        await log_admin_action(
            admin_id, "gbl_save_settings",
            target_type="group_balance_level",
            details={"keys": list(patch.keys())},
        )
    except Exception:
        pass
    return {"ok": True, "settings": result}


@router.post("/group-balance-level/settings/reset")
async def admin_gbl_reset_settings(
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    result = gbl_reset_settings()
    try:
        await log_admin_action(
            admin_id, "gbl_reset_settings",
            target_type="group_balance_level",
        )
    except Exception:
        pass
    return {"ok": True, "settings": result}


class GroupBalanceLevelSetBody(BaseModel):
    chat_id: int
    level: int = Field(ge=0, le=5)
    model_config = {"extra": "forbid"}


@router.get("/group-balance-level/chat/{chat_id}")
async def admin_gbl_get_chat(
    chat_id: int,
    _admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    return gbl_get_chat_level(chat_id)


@router.post("/group-balance-level/chat")
async def admin_gbl_set_chat(
    body: GroupBalanceLevelSetBody,
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    result = gbl_set_chat_level(body.chat_id, body.level)
    try:
        await log_admin_action(
            admin_id, "gbl_set_chat_level",
            target_type="chat",
            target_id=str(body.chat_id),
            details={"level": body.level},
        )
    except Exception:
        pass
    return {"ok": True, **result}


@router.get("/achievements/overview")
async def admin_achievements_overview(
    _admin_id: int = Depends(require_admin_permission("manage_achievements")),
):
    return await ach_overview()


@router.get("/achievements/list")
async def admin_achievements_list(
    q: str = Query("", max_length=128),
    enabled_only: bool = Query(False),
    _admin_id: int = Depends(require_admin_permission("manage_achievements")),
):
    items = await ach_list_catalog(enabled_only=enabled_only, q=q or None)
    return {"items": items}


class AchievementBody(BaseModel):
    id: int | None = None
    code: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=80)
    title_html: str | None = Field(default=None, max_length=500)
    icon_emoji_id: str | None = Field(default=None, max_length=64)
    icon_fallback: str | None = Field(default=None, max_length=8)
    description: str | None = Field(default=None, max_length=400)
    rarity: int = Field(default=1, ge=1, le=5)
    sort: int = Field(default=0, ge=-10000, le=10000)
    enabled: bool = True
    model_config = {"extra": "forbid"}


@router.post("/achievements/save")
async def admin_achievements_save(
    body: AchievementBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_achievements")),
):
    try:
        item = await ach_save_item(body.model_dump(), actor_id=admin_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await log_admin_action(
            admin_id, "achievement_save",
            target_type="achievement",
            target_id=str(item.get("id")),
            details={"code": item.get("code")},
        )
    except Exception:
        pass
    return {"ok": True, "item": item}


@router.post("/achievements/delete")
async def admin_achievements_delete(
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_achievements")),
):
    data = await request.json()
    oid = int((data or {}).get("id") or 0)
    if oid <= 0:
        raise HTTPException(status_code=400, detail="id required")
    ok = await ach_remove_item(oid)
    try:
        await log_admin_action(
            admin_id, "achievement_delete",
            target_type="achievement",
            target_id=str(oid),
        )
    except Exception:
        pass
    return {"ok": ok}


class AchievementGrantOfficialBody(BaseModel):
    user_id: int = Field(gt=0)
    official_id: int | None = None
    code: str | None = Field(default=None, max_length=64)
    model_config = {"extra": "forbid"}


@router.post("/achievements/grant-official")
async def admin_achievements_grant_official(
    body: AchievementGrantOfficialBody,
    admin_id: int = Depends(require_admin_permission("grant_official_achievements")),
):
    if not body.official_id and not (body.code or "").strip():
        raise HTTPException(status_code=400, detail="official_id or code required")
    try:
        result = await ach_grant_official(
            user_id=int(body.user_id),
            official_id=int(body.official_id) if body.official_id else None,
            code=(body.code or "").strip() or None,
            actor_id=int(admin_id),
            actor_name="Админ-панель",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await log_admin_action(
            admin_id, "achievement_grant_official",
            target_type="user",
            target_id=str(body.user_id),
            details={"code": result.get("code"), "already": result.get("already")},
        )
    except Exception:
        pass
    return result


class AchievementGrantFreeBody(BaseModel):
    user_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    icon_emoji_id: str | None = Field(default=None, max_length=64)
    icon_fallback: str | None = Field(default="⭐", max_length=8)
    model_config = {"extra": "forbid"}


@router.post("/achievements/grant-free")
async def admin_achievements_grant_free(
    body: AchievementGrantFreeBody,
    admin_id: int = Depends(require_admin_permission("grant_free_achievements")),
):
    try:
        result = await ach_grant_free(
            user_id=int(body.user_id),
            title=body.title,
            icon_emoji_id=body.icon_emoji_id,
            icon_fallback=body.icon_fallback or "⭐",
            actor_id=int(admin_id),
            actor_name="Админ-панель",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await log_admin_action(
            admin_id, "achievement_grant_free",
            target_type="user",
            target_id=str(body.user_id),
            details={"title": result.get("title")},
        )
    except Exception:
        pass
    return result


@router.get("/achievements/user/{user_id}")
async def admin_achievements_user_list(
    user_id: int,
    _admin_id: int = Depends(require_any_admin_permission(
        "grant_official_achievements",
        "grant_free_achievements",
    )),
):
    try:
        return await ach_list_user(int(user_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class AchievementRevokeBody(BaseModel):
    user_id: int = Field(gt=0)
    instance_id: str = Field(min_length=1, max_length=64)
    model_config = {"extra": "forbid"}


@router.post("/achievements/revoke")
async def admin_achievements_revoke(
    request: Request,
    body: AchievementRevokeBody,
    admin_id: int = Depends(require_any_admin_permission(
        "grant_official_achievements",
        "grant_free_achievements",
    )),
):
    # Сначала смотрим kind — право зависит от типа награды
    try:
        preview = await ach_list_user(int(body.user_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    target = next(
        (x for x in preview.get("items") or [] if x.get("instance_id") == body.instance_id),
        None,
    )
    if not target:
        raise HTTPException(status_code=404, detail="not_found")
    account = getattr(request.state, "admin_account", None)
    if not account:
        account = await get_admin_account_security(admin_id)
        request.state.admin_account = account
    perms = set(account.get("permissions") or [])
    kind = str(target.get("kind") or "free")
    need = (
        "grant_official_achievements"
        if kind == "official"
        else "grant_free_achievements"
    )
    if need not in perms:
        raise HTTPException(status_code=403, detail="Недостаточно прав для этого типа")
    try:
        result = await ach_revoke(
            user_id=int(body.user_id),
            instance_id=str(body.instance_id),
            actor_id=int(admin_id),
            actor_name="Админ-панель",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        await log_admin_action(
            admin_id, "achievement_revoke",
            target_type="user",
            target_id=str(body.user_id),
            details={
                "kind": result.get("kind"),
                "title": result.get("title"),
                "code": result.get("unique_code"),
                "instance_id": result.get("instance_id"),
            },
        )
    except Exception:
        pass
    return result


@router.get("/bot-quests/overview")
async def admin_bot_quests_overview(
    _admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    return await bot_quests_overview()


@router.get("/bot-quests/payouts")
async def admin_bot_quests_payouts(
    kind: str = Query("all", pattern=r"^(all|sub|gc)$"),
    q: str = Query("", max_length=128),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    return await list_quest_payouts(kind=kind, query=q, limit=limit, offset=offset)


@router.get("/bot-quests/sub-tasks")
async def admin_bot_sub_tasks_list(
    _admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    return {"items": await list_sub_tasks()}


@router.post("/bot-quests/sub-tasks")
async def admin_bot_sub_tasks_create(
    body: BotSubTaskBody,
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    try:
        result = await upsert_sub_task(
            chat_ref=body.chatRef,
            reward=body.reward,
            limit_mode=body.limitMode,
            total_cap=body.totalCap,
            ttl_value=body.ttlValue,
            ttl_unit=body.ttlUnit,
            ttl_expires_at=_parse_dt(body.ttlExpiresAt),
            starts_at=_parse_dt(body.startsAt),
            active=body.active,
        )
        await log_admin_action(
            admin_id, "bot_sub_task_upsert",
            target_type="quest_task", target_id=str(result.get("id")),
            target_label=body.chatRef,
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bot-quests/sub-tasks/bulk")
async def admin_bot_sub_tasks_bulk(
    body: BotSubTaskBulkBody,
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    items = []
    for it in body.items:
        items.append({
            "chatRef": it.chatRef,
            "reward": it.reward,
            "limitMode": it.limitMode,
            "totalCap": it.totalCap,
            "ttlValue": it.ttlValue,
            "ttlUnit": it.ttlUnit,
            "ttlExpiresAt": _parse_dt(it.ttlExpiresAt),
            "startsAt": _parse_dt(it.startsAt),
            "active": it.active,
        })
    result = await bulk_upsert_sub_tasks(items)
    await log_admin_action(
        admin_id, "bot_sub_task_bulk",
        target_type="quest_task",
        target_label=f"ok={result['ok']} fail={result['failed']}",
        ip=_get_client_ip(request),
    )
    return result


@router.patch("/bot-quests/sub-tasks/{task_id}")
async def admin_bot_sub_tasks_patch(
    task_id: int,
    body: BotSubTaskPatchBody,
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    patch = body.model_dump(exclude_unset=True)
    if "ttlExpiresAt" in patch:
        patch["ttlExpiresAt"] = _parse_dt(patch.get("ttlExpiresAt"))
    if "startsAt" in patch:
        patch["startsAt"] = _parse_dt(patch.get("startsAt"))
    try:
        result = await patch_sub_task(task_id, patch)
        await log_admin_action(
            admin_id, "bot_sub_task_patch",
            target_type="quest_task", target_id=str(task_id),
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/bot-quests/sub-tasks/{task_id}")
async def admin_bot_sub_tasks_delete(
    task_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    try:
        result = await delete_sub_task(task_id)
        await log_admin_action(
            admin_id, "bot_sub_task_delete",
            target_type="quest_task", target_id=str(task_id),
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bot-quests/challenges")
async def admin_bot_challenges_list(
    _admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    return {"items": await list_challenges(include_disabled=True)}


@router.post("/bot-quests/challenges")
async def admin_bot_challenges_create(
    body: BotChallengeBody,
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    try:
        result = await create_challenge(
            start_amount=body.startAmount,
            target_amount=body.targetAmount,
            reward_amount=body.rewardAmount,
            max_bet=body.maxBet,
            chat_ref=body.chatRef,
            max_users=body.maxUsers,
            free=body.free,
            starts_at=_parse_dt(body.startsAt),
        )
        await log_admin_action(
            admin_id, "bot_challenge_create",
            target_type="gc_template", target_id=str(result.get("id")),
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bot-quests/challenges/bulk")
async def admin_bot_challenges_bulk(
    body: BotChallengeBulkBody,
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    items = []
    for it in body.items:
        items.append({
            "startAmount": it.startAmount,
            "targetAmount": it.targetAmount,
            "rewardAmount": it.rewardAmount,
            "maxBet": it.maxBet,
            "chatRef": it.chatRef,
            "maxUsers": it.maxUsers,
            "free": it.free,
            "startsAt": _parse_dt(it.startsAt),
        })
    result = await bulk_create_challenges(items)
    await log_admin_action(
        admin_id, "bot_challenge_bulk",
        target_type="gc_template",
        target_label=f"ok={result['ok']} fail={result['failed']}",
        ip=_get_client_ip(request),
    )
    return result


@router.patch("/bot-quests/challenges/{template_id}")
async def admin_bot_challenges_patch(
    template_id: int,
    body: BotChallengePatchBody,
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    patch = body.model_dump(exclude_unset=True)
    if "startsAt" in patch:
        patch["startsAt"] = _parse_dt(patch.get("startsAt"))
    try:
        result = await patch_challenge(template_id, patch)
        await log_admin_action(
            admin_id, "bot_challenge_patch",
            target_type="gc_template", target_id=str(template_id),
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/bot-quests/challenges/{template_id}")
async def admin_bot_challenges_delete(
    template_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    try:
        result = await delete_challenge(template_id)
        await log_admin_action(
            admin_id, "bot_challenge_delete",
            target_type="gc_template", target_id=str(template_id),
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bot-quests/seed-pack")
async def admin_bot_quests_seed_pack(
    request: Request,
    admin_id: int = Depends(require_admin_role(ROLE_OWNER)),
):
    """Создаёт рекомендованный пакет заданий для @CuteGamingChat (идемпотентно)."""
    result = await seed_recommended_pack()
    await log_admin_action(
        admin_id, "bot_quests_seed_pack",
        target_type="bot_quests",
        target_label=f"ok={result.get('ok')} skip={result.get('skippedCount')}",
        ip=_get_client_ip(request),
    )
    return result


@router.get("/broadcast/overview")
async def admin_broadcast_overview(_admin_id: int = Depends(require_admin_permission("manage_broadcast"))):
    return await get_broadcast_overview()


@router.get("/broadcast/history")
async def admin_broadcast_history(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None, pattern=r"^(pending|running|scheduled|done|failed|cancelled)$"),
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    return await list_broadcast_history(limit=limit, offset=offset, status=status)


@router.get("/broadcast/runs/{run_id}")
async def admin_broadcast_run(
    run_id: int,
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    run = await get_broadcast_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")
    return run


@router.get("/broadcast/runs/{run_id}/recipients")
async def admin_broadcast_run_recipients(
    run_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None, max_length=16),
    channel: str | None = Query(None, max_length=16),
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    run = await get_broadcast_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")
    return await list_broadcast_recipients(
        run_id, limit=limit, offset=offset, status=status, channel=channel,
    )


@router.post("/broadcast/runs/{run_id}/cancel")
async def admin_broadcast_cancel(
    run_id: int,
    admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        return await cancel_broadcast(run_id, admin_user_id=admin_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/broadcast/preview")
async def admin_broadcast_preview(
    body: BroadcastPreviewBody,
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    return await preview_broadcast(
        title=body.title,
        body=body.body,
        detail=body.detail,
        telegram_text=body.telegramText,
        sample_user_id=body.sampleUserId,
    )


@router.post("/broadcast/count")
async def admin_broadcast_count(
    body: BroadcastCountBody,
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    filt = body.filter.model_dump() if body.filter else {}
    count = await count_recipients(body.audience, filt)
    return {"count": count}


@router.post("/broadcast/send")
async def admin_broadcast_send(
    body: BroadcastSendBody,
    admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        filt = body.filter.model_dump() if body.filter else {}
        return await start_broadcast(
            audience=body.audience,
            filter_data=filt,
            channels=body.channels.model_dump(),
            title=body.title,
            body=body.body,
            detail=body.detail,
            telegram_text=body.telegramText,
            template_key=body.templateKey,
            scheduled_at=_parse_dt(body.scheduledAt),
            label=body.label,
            admin_user_id=admin_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/broadcast/templates")
async def admin_broadcast_template_save(
    body: BroadcastTemplateBody,
    admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        return await save_template(
            name=body.name,
            title=body.title,
            body=body.body,
            detail=body.detail,
            telegram_text=body.telegramText,
            admin_user_id=admin_id,
            template_id=body.templateId,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/broadcast/templates/{template_id}")
async def admin_broadcast_template_delete(
    template_id: int,
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        await delete_template(template_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class DailyRotationBody(BaseModel):
    enabled: bool | None = None
    hour: int | None = Field(None, ge=0, le=23)
    minute: int | None = Field(None, ge=0, le=59)
    cooldownDays: int | None = Field(None, ge=1, le=30)
    sampleRate: float | None = Field(None, gt=0, lt=1)


@router.get("/broadcast/daily-rotation")
async def admin_daily_rotation_get(
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    from db import db

    row = await db.pool.fetchrow(
        """
        SELECT daily_broadcast_enabled, daily_broadcast_hour, daily_broadcast_minute,
               daily_broadcast_next_fire_at, daily_broadcast_cooldown_days,
               daily_broadcast_sample_rate
        FROM system_settings WHERE id = 1
        """
    )
    if not row:
        raise HTTPException(status_code=500, detail="system_settings не инициализирован")
    return {
        "enabled": bool(row["daily_broadcast_enabled"]),
        "hourUtc": int(row["daily_broadcast_hour"]),
        "minuteUtc": int(row["daily_broadcast_minute"]),
        "cooldownDays": int(row["daily_broadcast_cooldown_days"]),
        "sampleRate": float(row["daily_broadcast_sample_rate"]),
        "nextFireAt": row["daily_broadcast_next_fire_at"].isoformat() if row["daily_broadcast_next_fire_at"] else None,
        "templateCount": len(DAILY_ROTATION_TEMPLATES),
    }


@router.post("/broadcast/daily-rotation")
async def admin_daily_rotation_set(
    body: DailyRotationBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    from db import db

    updates: list[str] = []
    params: list = []
    idx = 1
    if body.enabled is not None:
        updates.append(f"daily_broadcast_enabled = ${idx}")
        params.append(body.enabled)
        idx += 1
    reschedule = body.hour is not None or body.minute is not None
    if body.hour is not None:
        updates.append(f"daily_broadcast_hour = ${idx}")
        params.append(body.hour)
        idx += 1
    if body.minute is not None:
        updates.append(f"daily_broadcast_minute = ${idx}")
        params.append(body.minute)
        idx += 1
    if body.cooldownDays is not None:
        updates.append(f"daily_broadcast_cooldown_days = ${idx}")
        params.append(body.cooldownDays)
        idx += 1
    if body.sampleRate is not None:
        updates.append(f"daily_broadcast_sample_rate = ${idx}")
        params.append(body.sampleRate)
        idx += 1
    if reschedule:
        # Время поменялось - сбрасываем next_fire_at, планировщик пересчитает его на следующем тике.
        updates.append("daily_broadcast_next_fire_at = NULL")
    if not updates:
        raise HTTPException(status_code=400, detail="Нечего менять")

    await db.pool.execute(
        f"UPDATE system_settings SET {', '.join(updates)} WHERE id = 1",
        *params,
    )
    await log_admin_action(
        admin_id, "settings_change",
        target_type="setting",
        target_label="Ежедневная рассылка: расписание",
        details=body.model_dump(exclude_none=True),
        ip=_get_client_ip(request),
    )
    return await admin_daily_rotation_get(_admin_id=admin_id)


@router.post("/broadcast/daily-rotation/run-now")
async def admin_daily_rotation_run_now(
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        result = await run_daily_rotation_now(admin_user_id=admin_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await log_admin_action(
        admin_id, "broadcast_run_now",
        target_type="broadcast",
        target_label=f"Ежедневная ротация: ручной запуск (run_id={result.get('runId')})",
        details={"runId": result.get("runId"), "recipientCount": result.get("recipientCount")},
        ip=_get_client_ip(request),
    )
    return result


@router.get("/group-posts")
async def admin_group_posts_list(
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    return {"items": await list_campaigns()}


@router.get("/group-posts/known-chats")
async def admin_group_posts_known_chats(
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    return {"items": await list_known_chats()}


@router.post("/group-posts")
async def admin_group_posts_create(
    label: str = Form(default=""),
    chat_ids: str = Form(...),
    telegram_text: str = Form(default=""),
    buttons: str = Form(default="[]"),
    interval_minutes: int = Form(...),
    photo: UploadFile | None = File(default=None),
    delete_previous: bool = Form(default=False),
    pin_message: bool = Form(default=False),
    pin_notify: bool = Form(default=False),
    chat_overrides: str = Form(default="{}"),
    admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        buttons_data = json.loads(buttons) if buttons else []
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Некорректный формат кнопок")

    try:
        overrides_data = json.loads(chat_overrides) if chat_overrides else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Некорректный формат настроек по группам")

    photo_bytes = None
    photo_mime = None
    if photo is not None and photo.filename:
        photo_bytes = await photo.read()
        photo_mime = photo.content_type or "image/jpeg"
        if len(photo_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Фото больше 10МБ")

    try:
        return await create_campaign(
            admin_user_id=admin_id,
            label=label,
            chat_ids=chat_ids,
            telegram_text=telegram_text,
            buttons=buttons_data,
            interval_minutes=interval_minutes,
            photo_bytes=photo_bytes,
            photo_mime=photo_mime,
            delete_previous=delete_previous,
            pin_message=pin_message,
            pin_notify=pin_notify,
            chat_overrides=overrides_data,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/group-posts/{campaign_id}")
async def admin_group_posts_update(
    campaign_id: int,
    label: str | None = Form(default=None),
    chat_ids: str | None = Form(default=None),
    telegram_text: str | None = Form(default=None),
    buttons: str | None = Form(default=None),
    interval_minutes: int | None = Form(default=None),
    photo: UploadFile | None = File(default=None),
    clear_photo: bool = Form(default=False),
    delete_previous: bool | None = Form(default=None),
    pin_message: bool | None = Form(default=None),
    pin_notify: bool | None = Form(default=None),
    chat_overrides: str | None = Form(default=None),
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    buttons_data = None
    if buttons is not None:
        try:
            buttons_data = json.loads(buttons)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Некорректный формат кнопок")

    overrides_data = None
    if chat_overrides is not None:
        try:
            overrides_data = json.loads(chat_overrides)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Некорректный формат настроек по группам")

    photo_bytes = None
    photo_mime = None
    if photo is not None and photo.filename:
        photo_bytes = await photo.read()
        photo_mime = photo.content_type or "image/jpeg"
        if len(photo_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Фото больше 10МБ")

    try:
        return await update_campaign(
            campaign_id,
            label=label,
            chat_ids=chat_ids,
            telegram_text=telegram_text,
            buttons=buttons_data,
            interval_minutes=interval_minutes,
            photo_bytes=photo_bytes,
            photo_mime=photo_mime,
            clear_photo=clear_photo,
            delete_previous=delete_previous,
            pin_message=pin_message,
            pin_notify=pin_notify,
            chat_overrides=overrides_data,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/group-posts/{campaign_id}/pause")
async def admin_group_posts_pause(
    campaign_id: int,
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        return await set_campaign_status(campaign_id, "paused")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/group-posts/{campaign_id}/resume")
async def admin_group_posts_resume(
    campaign_id: int,
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        return await set_campaign_status(campaign_id, "active")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/group-posts/{campaign_id}/run-now")
async def admin_group_posts_run_now(
    campaign_id: int,
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        return await run_campaign_now(campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/group-posts/{campaign_id}")
async def admin_group_posts_delete(
    campaign_id: int,
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        await delete_campaign(campaign_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/group-posts/{campaign_id}/log")
async def admin_group_posts_log(
    campaign_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    campaign = await get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    return await list_campaign_log(campaign_id, limit=limit, offset=offset)


@router.get("/group-posts/{campaign_id}/photo")
async def admin_group_posts_photo(
    campaign_id: int,
    _admin_id: int = Depends(require_admin_permission("manage_broadcast")),
):
    try:
        photo_bytes, photo_mime = await get_campaign_photo(campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Response(content=photo_bytes, media_type=photo_mime)


@router.get("/logs/overview")
async def admin_logs_overview(_admin_id: int = Depends(require_admin_permission("view_logs"))):
    return await get_logs_overview()


@router.get("/logs/audit")
async def admin_logs_audit(
    userId: int | None = Query(None, ge=1),
    eventType: str | None = Query(None, max_length=64),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("view_logs")),
):
    return await list_audit_logs(
        user_id=userId,
        event_type=eventType,
        limit=limit,
        offset=offset,
    )


@router.get("/logs/transfers")
async def admin_logs_transfers(
    userId: int | None = Query(None, ge=1),
    senderId: int | None = Query(None, ge=1),
    receiverId: int | None = Query(None, ge=1),
    dateFrom: str | None = Query(None, max_length=32),
    dateTo: str | None = Query(None, max_length=32),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("view_logs")),
):
    return await list_p2p_transfers(
        user_id=userId,
        sender_id=senderId,
        receiver_id=receiverId,
        date_from=dateFrom,
        date_to=dateTo,
        limit=limit,
        offset=offset,
    )


@router.get("/logs/system")
async def admin_logs_system(
    category: str = Query("security", pattern=r"^(security|errors|error|api)$"),
    userId: int | None = Query(None, ge=1),
    code: str | None = Query(None, max_length=64),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("view_logs")),
):
    return await list_system_logs(
        category=category,
        user_id=userId,
        code=code,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Events & Scheduling
# ---------------------------------------------------------------------------

@router.get("/events/upcoming")
async def admin_events_upcoming(_admin_id: int = Depends(require_admin_permission("manage_events"))):
    """Все запланированные события: квесты с расписанием + отложенные рассылки."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    # Timed quests
    quest_events = []
    for q in all_quests():
        if not q.active_from and not q.active_until and not q.recurrence:
            continue
        from quest_registry import PERIOD_LABELS
        if q.active_from and q.active_from >= now:
            quest_events.append({
                "type": "quest_activate",
                "at": q.active_from.isoformat(),
                "questId": q.db_id,
                "questKey": q.key,
                "questTitle": q.title,
                "questEmoji": q.emoji,
                "period": q.period,
                "periodLabel": PERIOD_LABELS.get(q.period, q.period),
                "recurrence": q.recurrence,
            })
        if q.active_until:
            if q.active_until >= now:
                quest_events.append({
                    "type": "quest_deactivate",
                    "at": q.active_until.isoformat(),
                    "questId": q.db_id,
                    "questKey": q.key,
                    "questTitle": q.title,
                    "questEmoji": q.emoji,
                    "period": q.period,
                    "periodLabel": PERIOD_LABELS.get(q.period, q.period),
                    "recurrence": q.recurrence,
                })

    # Scheduled broadcasts
    sched = await list_scheduled_broadcasts(limit=50)
    broadcast_events = [
        {
            "type": "broadcast",
            "at": item["scheduledAt"],
            "broadcastId": item["id"],
            "title": item["title"],
            "label": item["label"],
            "audience": item["audience"],
            "recipientCount": item["recipientCount"],
        }
        for item in sched["items"]
        if item["scheduledAt"]
    ]

    all_events = sorted(
        quest_events + broadcast_events,
        key=lambda e: e["at"],
    )
    return {"events": all_events, "count": len(all_events)}


@router.get("/events/timed-quests")
async def admin_events_timed_quests(_admin_id: int = Depends(require_admin_permission("manage_events"))):
    """Список квестов с расписанием."""
    from quest_registry import quest_to_admin_dict
    timed = [
        quest_to_admin_dict(q)
        for q in all_quests()
        if q.active_from or q.active_until or q.recurrence
    ]
    return {"quests": timed, "total": len(timed)}


@router.get("/events/scheduled-broadcasts")
async def admin_events_scheduled_broadcasts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("manage_events")),
):
    # Только чтение - отмена теперь только через /broadcast/runs/{id}/cancel
    # (manage_broadcast), чтобы не было двух путей отмены с разными правами.
    return await list_scheduled_broadcasts(limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@router.get("/analytics/quests")
async def admin_analytics_quests(
    days: int = Query(30, ge=1, le=365),
    _admin_id: int = Depends(require_admin_permission("view_analytics")),
):
    return await get_quest_analytics(days=days)


@router.get("/analytics/farm")
async def admin_analytics_farm(
    days: int = Query(30, ge=1, le=365),
    _admin_id: int = Depends(require_admin_permission("view_analytics")),
):
    return await get_farm_analytics(days=days)


@router.get("/analytics/market")
async def admin_analytics_market(
    days: int = Query(30, ge=1, le=365),
    itemId: str | None = Query(None, max_length=64),
    _admin_id: int = Depends(require_admin_permission("view_analytics")),
):
    return await get_market_analytics(days=days, item_id=itemId)


@router.get("/analytics/craft")
async def admin_analytics_craft(
    days: int = Query(30, ge=1, le=365),
    _admin_id: int = Depends(require_admin_permission("view_analytics")),
):
    return await get_craft_analytics(days=days)


@router.get("/analytics/retention")
async def admin_analytics_retention(
    days: int = Query(30, ge=1, le=365),
    _admin_id: int = Depends(require_admin_permission("view_analytics")),
):
    return await get_retention_analytics(days=days)


# ---------------------------------------------------------------------------
# Extended player profile
# ---------------------------------------------------------------------------

@router.get("/users/{user_id}/quests")
async def admin_user_quests(
    user_id: int,
    _admin_id: int = Depends(require_admin_permission("view_players")),
):
    info = await get_player_quest_info(user_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Игрок не найден")
    return info


@router.get("/users/{user_id}/bans")
async def admin_user_bans(
    user_id: int,
    _admin_id: int = Depends(require_admin_permission("view_players")),
):
    return {"bans": await get_player_ban_history(user_id)}


@router.get("/users/{user_id}/notes")
async def admin_user_notes_list(
    user_id: int,
    _admin_id: int = Depends(require_admin_permission("view_players")),
):
    return {"notes": await list_player_notes(user_id)}


class PlayerNoteBody(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    noteId: int | None = None
    model_config = {"extra": "forbid"}


@router.post("/users/{user_id}/notes")
async def admin_user_notes_upsert(
    user_id: int,
    body: PlayerNoteBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("view_players")),
):
    try:
        note = await upsert_player_note(
            user_id,
            body.text,
            admin_user_id=admin_id,
            note_id=body.noteId,
        )
        await log_admin_action(
            admin_id, "note_upsert",
            target_type="user", target_id=str(user_id),
            target_label=f"Игрок {user_id}",
            ip=_get_client_ip(request),
        )
        return note
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/users/{user_id}/notes/{note_id}")
async def admin_user_notes_delete(
    user_id: int,
    note_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_permission("view_players")),
):
    try:
        await delete_player_note(user_id, note_id, admin_user_id=admin_id)
        await log_admin_action(
            admin_id, "note_delete",
            target_type="user", target_id=str(user_id),
            target_label=f"Игрок {user_id}",
            ip=_get_client_ip(request),
        )
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/users/{user_id}/export")
async def admin_user_export(
    user_id: int,
    _admin_id: int = Depends(require_admin_permission("view_player_sensitive")),
):
    try:
        import datetime as _dt
        data = await export_player_profile(user_id)
        data["exportedAt"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
        return data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Dex full CRUD
# ---------------------------------------------------------------------------

@router.get("/content/dex/{item_id}")
async def admin_dex_item_get(
    item_id: str,
    _admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        return await get_dex_item_full(item_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class DexItemFullBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    emoji: str = Field(default="📦", max_length=8)
    name1: str = Field(default="", max_length=120)
    price: int = Field(default=0, ge=0)
    dis: int = Field(default=0, ge=0)
    remains: int = Field(default=0, ge=0)
    sorting: str | None = Field(default=None, max_length=64)
    bio: str = Field(default="", max_length=1000)
    use: str = Field(default="", max_length=500)
    bonus: str = Field(default="", max_length=500)
    craft: str = Field(default="", max_length=500)
    model_config = {"extra": "forbid"}


@router.put("/content/dex/{item_id}")
async def admin_dex_item_update(
    item_id: str,
    body: DexItemFullBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await update_dex_item_meta(
            item_id,
            name=body.name,
            emoji=body.emoji,
            name1=body.name1,
            price=body.price,
            dis=body.dis,
            remains=body.remains,
            sorting=body.sorting,
            bio=body.bio,
            use=body.use,
            bonus=body.bonus,
            craft=body.craft,
            admin_user_id=admin_id,
        )
        await log_admin_action(
            admin_id, "dex_update",
            target_type="dex_item", target_id=item_id, target_label=item_id,
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/content/dex/{item_id}")
async def admin_dex_item_delete(
    item_id: str,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    try:
        result = await delete_dex_item(item_id, admin_user_id=admin_id)
        await log_admin_action(
            admin_id, "dex_item_delete",
            target_type="dex_item", target_id=item_id,
            target_label=f"DEX-предмет {item_id}",
            ip=_get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Security: admin audit log
# ---------------------------------------------------------------------------


@router.get("/security/audit")
async def admin_security_audit(
    admin_user_id: int | None = Query(None),
    action: str | None = Query(None, max_length=50),
    target_type: str | None = Query(None, max_length=32),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("manage_security")),
):
    return await list_admin_audit(
        admin_user_id=admin_user_id,
        action=action,
        target_type=target_type,
        limit=limit,
        offset=offset,
    )


@router.get("/security/audit/actions")
async def admin_security_audit_actions(_admin_id: int = Depends(require_admin_permission("manage_security"))):
    return {"actions": await list_admin_action_types()}


# ---------------------------------------------------------------------------
# Security: IP bans
# ---------------------------------------------------------------------------


class IpBanBody(BaseModel):
    ipOrCidr: str = Field(..., min_length=3, max_length=50)
    reason: str = Field("", max_length=200)
    expiresAt: str | None = None


@router.get("/security/ip-bans")
async def admin_security_ip_bans_list(_admin_id: int = Depends(require_admin_permission("manage_security"))):
    return {"bans": await list_ip_bans()}


@router.post("/security/ip-bans")
async def admin_security_ip_bans_add(
    body: IpBanBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_security")),
):
    try:
        ban = await add_ip_ban(
            body.ipOrCidr,
            reason=body.reason,
            banned_by=admin_id,
            expires_at=_parse_dt(body.expiresAt),
        )
        await log_admin_action(
            admin_id, "ip_ban_add",
            target_type="ip", target_id=body.ipOrCidr,
            target_label=body.ipOrCidr,
            details={"reason": body.reason},
            ip=_get_client_ip(request),
        )
        return {"ok": True, "ban": ban}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/security/ip-bans/{ban_id}")
async def admin_security_ip_bans_remove(
    ban_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_security")),
):
    removed = await remove_ip_ban(ban_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Бан не найден или уже снят")
    await log_admin_action(
        admin_id, "ip_ban_remove",
        target_type="ip", target_id=str(ban_id),
        target_label=f"IP-бан #{ban_id}",
        ip=_get_client_ip(request),
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Security: sessions & 2FA management
# ---------------------------------------------------------------------------


@router.get("/security/sessions")
async def admin_security_sessions(_admin_id: int = Depends(require_admin_permission("manage_security"))):
    from db import db
    rows = await db.pool.fetch(
        """
        SELECT user_id, username, first_name, registered_at,
               last_ip, last_seen_at, session_fingerprint, force_reauth_at
        FROM admin_accounts
        ORDER BY last_seen_at DESC NULLS LAST
        """
    )
    return {
        "sessions": [
            {
                "userId": int(r["user_id"]),
                "username": r["username"],
                "firstName": r["first_name"],
                "registeredAt": r["registered_at"].isoformat() if r["registered_at"] else None,
                "lastIp": r["last_ip"],
                "lastSeenAt": r["last_seen_at"].isoformat() if r["last_seen_at"] else None,
                "hasFingerprint": bool(r["session_fingerprint"]),
                "forceReauthAt": r["force_reauth_at"].isoformat() if r["force_reauth_at"] else None,
            }
            for r in rows
        ]
    }


class ForceReauthBody(BaseModel):
    userId: int | None = None  # None = all admins


@router.post("/security/sessions/force-reauth")
async def admin_security_force_reauth(
    body: ForceReauthBody,
    request: Request,
    admin_id: int = Depends(require_admin_permission("manage_security")),
):
    count = await force_reauth(body.userId)
    target = f"Администратор {body.userId}" if body.userId else "Все администраторы"
    await log_admin_action(
        admin_id, "force_reauth",
        target_type="session",
        target_id=str(body.userId) if body.userId else "all",
        target_label=target,
        ip=_get_client_ip(request),
    )
    return {"ok": True, "affected": count}


@router.post("/moderation/notify")
async def moderation_notify(request: Request):
    """Внутренний эндпоинт — бот вызывает после записи в staff_actions."""
    from db import db

    key = request.headers.get("X-Internal-Key", "")
    if not INTERNAL_API_KEY or key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Неверный ключ")

    body = await request.json()
    log_id = body.get("logId")
    if not log_id:
        raise HTTPException(status_code=422, detail="logId обязателен")

    row = await db.pool.fetchrow(
        """
        SELECT id, created_at, admin_user_id, admin_name, action_type,
               target_player_id, target_name, reason, evidence,
               proof_media_id, duration_minutes
        FROM staff_actions WHERE id = $1
        """,
        int(log_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    from admin_ws import broadcast_to_admins
    await broadcast_to_admins({
        "event": "new_moderation_log",
        "data": {
            "id": int(row["id"]),
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
            "actionType": row["action_type"],
            "adminId": int(row["admin_user_id"]),
            "adminName": row["admin_name"] or "",
            "targetId": int(row["target_player_id"]) if row["target_player_id"] else None,
            "targetName": row["target_name"] or "",
            "reason": row["reason"] or "",
            "hasProof": bool(row["proof_media_id"]),
            "durationMinutes": row["duration_minutes"],
        },
    })
    return {"ok": True}


@router.get("/photo-proxy")
async def photo_proxy(
    file_id: str = Query(...),
    _admin_id: int = Depends(require_admin_session),
):
    """Проксирует файл из Telegram через наш сервер — обходит CORS.

    file_id валиден только для бота, который его выдал. Сначала берём сохранённый
    в БД токен-владелец пруфа (его пишут все системы наказаний рядом с file_id),
    затем — настроенные токены как запасной вариант. Токен остаётся на сервере:
    клиенту уходят только байты картинки.
    """
    import aiohttp
    from admin_moderation import candidate_tokens_for_file
    tokens = await candidate_tokens_for_file(file_id)
    if not tokens:
        raise HTTPException(502, "Токен бота не настроен")
    async with aiohttp.ClientSession() as session:
        for token in tokens:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getFile",
                params={"file_id": file_id},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
            if not data.get("ok"):
                continue
            file_path = data["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
            async with session.get(file_url, timeout=aiohttp.ClientTimeout(total=30)) as img_resp:
                content_type = img_resp.headers.get("Content-Type", "image/jpeg")
                content = await img_resp.read()
            return Response(content=content, media_type=content_type)
    raise HTTPException(404, "Файл недоступен")


@router.get("/appeals")
async def admin_list_appeals(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("manage_appeals")),
):
    return await list_appeals(status=status, limit=limit, offset=offset)


@router.post("/appeals/{appeal_id}/take")
async def admin_take_appeal(
    appeal_id: int,
    admin_id: int = Depends(require_admin_permission("manage_appeals")),
):
    try:
        return await take_appeal(appeal_id, admin_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class ResolveAppealBody(BaseModel):
    approve: bool
    resolution: str = ""


async def _send_ban_photo_to_player(user_id: int, file_id: str, reason: str) -> None:
    """Отправляет фото-доказательство игроку через Telegram file_id."""
    import aiohttp
    from config import BOT_TOKEN

    if not BOT_TOKEN or not file_id:
        return

    caption_text = "<tg-emoji emoji-id='5260483378729208732'>⛔️</tg-emoji> Аккаунт заблокирован"
    if reason:
        caption_text += f"\n<tg-emoji emoji-id='5303138782004924588'>💬</tg-emoji> {reason}"

    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                json={
                    "chat_id": user_id,
                    "photo": file_id,
                    "caption": caption_text,
                    "parse_mode": "HTML",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            )
    except Exception:
        pass  # Не критично если фото не дошло


async def _upload_photo_to_telegram(file: UploadFile, token: str, chat_id: str, caption: str = "") -> str:
    """Загружает фото в Telegram и возвращает file_id."""
    import aiohttp
    data = aiohttp.FormData()
    data.add_field("chat_id", chat_id)
    if caption:
        data.add_field("caption", caption)
        data.add_field("parse_mode", "HTML")
    data.add_field("photo", await file.read(), filename=file.filename or "photo.jpg", content_type=file.content_type or "image/jpeg")
    async with aiohttp.ClientSession() as session:
        async with session.post(f"https://api.telegram.org/bot{token}/sendPhoto", data=data) as resp:
            result = await resp.json()
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=f"Telegram: {result.get('description', 'ошибка')}")
    sizes = result["result"]["photo"]
    return sizes[-1]["file_id"]


@router.post("/appeals/{appeal_id}/upload")
async def admin_appeal_upload(
    appeal_id: int,
    file: UploadFile = File(...),
    text: str = Form(default=""),
    admin_id: int = Depends(require_admin_permission("manage_appeals")),
):
    from config import SUPPORT_BOT_TOKEN
    from admin_db import get_admin_account

    from db import db
    row = await db.pool.fetchrow("SELECT user_id, status FROM ban_appeals WHERE id = $1", appeal_id)
    if not row:
        raise HTTPException(404, "Апелляция не найдена")
    if row["status"] in ("approved", "rejected"):
        raise HTTPException(400, "Апелляция закрыта")

    acc = await get_admin_account(admin_id)
    admin_name = (acc.get("firstName") or acc.get("username") or f"#{admin_id}") if acc else f"#{admin_id}"

    # Загружаем фото — оно уже уходит игроку внутри этой функции
    file_id = await _upload_photo_to_telegram(file, SUPPORT_BOT_TOKEN, str(row["user_id"]), text.strip())

    # Сохраняем в БД напрямую — без повторной отправки игроку
    msg_id = await db.pool.fetchval(
        """
        INSERT INTO ban_appeal_messages
            (appeal_id, from_user, admin_id, admin_name, text, photo_file_id)
        VALUES ($1, FALSE, $2, $3, $4, $5)
        RETURNING id
        """,
        appeal_id, admin_id, admin_name, text.strip(), file_id,
    )
    await db.pool.execute(
        "UPDATE ban_appeals SET taken_by = COALESCE(taken_by, $2), status = CASE WHEN status = 'pending' THEN 'taken' ELSE status END WHERE id = $1",
        appeal_id, admin_id,
    )
    return {"id": int(msg_id)}


@router.post("/users/upload-evidence")
async def admin_upload_ban_evidence(
    file: UploadFile = File(...),
    admin_id: int = Depends(require_admin_permission("moderate_ban")),
):
    """Загружает фото-доказательство в Telegram, возвращает Telegram file_id."""
    from config import BOT_TOKEN, ADMIN_BOT_TOKEN
    import aiohttp

    token = BOT_TOKEN or ADMIN_BOT_TOKEN
    if not token:
        raise HTTPException(status_code=503, detail="Токен бота не настроен — загрузка фото недоступна")

    content = await file.read()
    data = aiohttp.FormData()
    data.add_field("chat_id", str(admin_id))
    data.add_field("photo", content, filename=file.filename or "evidence.jpg", content_type=file.content_type or "image/jpeg")

    async with aiohttp.ClientSession() as session:
        async with session.post(f"https://api.telegram.org/bot{token}/sendPhoto", data=data) as resp:
            result = await resp.json()

    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=f"Telegram: {result.get('description', 'ошибка загрузки')}")

    sizes = result["result"]["photo"]
    telegram_file_id = sizes[-1]["file_id"]
    return {"fileId": telegram_file_id}


@router.get("/users/evidence/{file_id:path}")
async def admin_get_evidence(
    file_id: str,
    _admin_id: int = Depends(require_admin_session),
):
    """Возвращает временную ссылку на фото-доказательство через Telegram."""
    from admin_moderation import get_proof_url
    from fastapi.responses import RedirectResponse

    try:
        url = await get_proof_url_by_file_id(file_id)
        return RedirectResponse(url)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


async def get_proof_url_by_file_id(file_id: str) -> str:
    """Получает временный URL файла из Telegram по file_id."""
    import aiohttp
    from admin_moderation import candidate_tokens_for_file
    # Приоритет — сохранённому в БД токену-владельцу пруфа, затем настроенные.
    tokens = await candidate_tokens_for_file(file_id)
    if not tokens:
        raise RuntimeError("Токен бота не настроен")
    last_error = ""
    async with aiohttp.ClientSession() as session:
        for token in tokens:
            async with session.get(
                f"https://api.telegram.org/bot{token}/getFile",
                params={"file_id": file_id},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
            if data.get("ok"):
                return f"https://api.telegram.org/file/bot{token}/{data['result']['file_path']}"
            last_error = data.get("description", "ошибка")
    raise RuntimeError(f"Telegram getFile error: {last_error}")


@router.post("/support/tickets-upload/{ticket_id}")
async def admin_ticket_upload(
    ticket_id: int,
    file: UploadFile = File(...),
    text: str = Form(default=""),
    admin_id: int = Depends(require_admin_session),
):
    from config import SUPPORT_BOT_TOKEN
    import support_db

    ticket = await support_db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "Тикет не найден")
    if ticket["status"] == "closed":
        raise HTTPException(400, "Тикет закрыт")

    acc = await get_admin_account(admin_id)
    admin_name = (
        (acc.get("firstName") or acc.get("username") or f"#{admin_id}")
        if acc else f"#{admin_id}"
    )

    file_id = await _upload_photo_to_telegram(file, SUPPORT_BOT_TOKEN, str(ticket["user_id"]), text.strip())
    await support_db.add_admin_message(ticket_id, admin_id, admin_name, text.strip(), file_id)
    return {"ok": True, "fileId": file_id}


@router.get("/appeals/{appeal_id}/messages")
async def admin_appeal_messages(
    appeal_id: int,
    _admin_id: int = Depends(require_admin_permission("manage_appeals")),
):
    return {"items": await get_appeal_messages(appeal_id)}


class AppealMessageBody(BaseModel):
    text: str = ""
    photoFileId: str = ""


@router.post("/appeals/{appeal_id}/message")
async def admin_send_appeal_message(
    appeal_id: int,
    body: AppealMessageBody,
    admin_id: int = Depends(require_admin_permission("manage_appeals")),
):
    from admin_db import get_admin_account
    acc = await get_admin_account(admin_id)
    admin_name = (acc.get("firstName") or acc.get("username") or f"#{admin_id}") if acc else f"#{admin_id}"
    try:
        return await send_appeal_message(
            appeal_id, admin_id, admin_name,
            body.text, body.photoFileId or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/appeals/{appeal_id}/resolve")
async def admin_resolve_appeal(
    appeal_id: int,
    body: ResolveAppealBody,
    admin_id: int = Depends(require_admin_permission("manage_appeals")),
):
    try:
        return await resolve_appeal(
            appeal_id, admin_id,
            approve=body.approve,
            resolution=body.resolution,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/moderation/logs")
async def admin_moderation_logs(
    action_type: str | None = Query(None),
    player_id: int | None = Query(None),
    sort_by: str = Query("date"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _admin_id: int = Depends(require_admin_permission("moderate_ban")),
):
    return await list_moderation_logs(
        action_type=action_type,
        player_id=player_id,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )


@router.delete("/moderation/logs/{log_id}")
async def admin_moderation_delete_log(
    log_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_session),
):
    from admin_db import get_admin_account
    acc = await get_admin_account(admin_id)
    if not acc or acc.get("role") not in ("owner",):
        raise HTTPException(status_code=403, detail="Только владелец может удалять записи архива")
    try:
        await delete_log(log_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await log_admin_action(
        admin_id, "moderation_log_delete",
        target_type="moderation_log", target_id=str(log_id),
        ip=_get_client_ip(request),
    )
    return {"ok": True}


@router.get("/moderation/proof/{log_id}")
async def admin_moderation_proof(
    log_id: int,
    _admin_id: int = Depends(require_admin_permission("moderate_ban")),
):
    try:
        url = await get_proof_url(log_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"url": url}


@router.get("/moderation/player-history/{player_id}")
async def admin_player_history(
    player_id: int,
    _admin_id: int = Depends(require_admin_permission("moderate_ban")),
):
    return {"items": await get_player_history(player_id)}


@router.get("/moderation/moderator-stats")
async def admin_moderator_stats(
    period: str = Query("week"),
    _admin_id: int = Depends(require_admin_permission("moderate_ban")),
):
    return {"items": await get_moderator_stats(period)}


@router.get("/moderation/recent")
async def admin_moderation_recent(
    limit: int = Query(5, ge=1, le=20),
    _admin_id: int = Depends(require_admin_permission("moderate_ban")),
):
    return {"items": await get_recent_logs(limit)}


@router.post("/moderation/unban/{user_id}")
async def admin_moderation_unban(
    user_id: int,
    request: Request,
    admin_id: int = Depends(require_admin_permission("moderate_unban")),
):
    from admin_db import get_admin_account

    acc = await get_admin_account(admin_id)
    admin_name = (acc.get("firstName") or acc.get("username") or "") if acc else ""

    try:
        await unban_player(user_id, admin_user_id=admin_id, admin_name=admin_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    await log_admin_action(
        admin_id, "unban_user",
        target_type="player",
        target_id=str(user_id),
        ip=_get_client_ip(request),
    )
    return {"ok": True}


@router.websocket("/ws/moderation")
async def ws_moderation(websocket: WebSocket, token: str = Query("")):
    from admin_auth import verify_admin_token
    from admin_ws import ws_connect, ws_disconnect

    if not verify_admin_token(token):
        await websocket.close(code=4001)
        return

    await ws_connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        ws_disconnect(websocket)


# ---------------------------------------------------------------------------
# Invite tokens
# ---------------------------------------------------------------------------


class CreateInviteTokenBody(BaseModel):
    label: str = Field(default="", max_length=200)
    model_config = {"extra": "forbid"}


@router.get("/staff/invites")
async def get_invite_tokens(
    user_id: int = Depends(require_admin_permission("assign_roles")),
):
    items = await list_invite_tokens()
    return {"items": items}


@router.post("/staff/invites")
async def post_invite_token(
    body: CreateInviteTokenBody,
    user_id: int = Depends(require_admin_permission("assign_roles")),
):
    token = await create_invite_token(body.label, user_id)
    return token


@router.post("/staff/invites/{token_id}/revoke")
async def revoke_invite_token_route(
    token_id: int,
    user_id: int = Depends(require_admin_permission("assign_roles")),
):
    ok = await revoke_invite_token(token_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Токен не найден или уже отозван/использован")
    return {"ok": True}


@router.delete("/staff/invites/{token_id}")
async def hard_delete_invite_token_route(
    token_id: int,
    user_id: int = Depends(require_admin_permission("assign_roles")),
):
    ok = await hard_delete_invite_token(token_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Токен не найден")
    return {"ok": True}
