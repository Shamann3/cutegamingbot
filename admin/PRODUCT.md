# Product

<!-- impeccable:product-schema 1 -->

> Inferred from the repository and the owner's brief (the owner delegated every open decision: «я даю весь контроль тебе»). Facts marked *inferred* were not confirmed in an interview.

## Platform

web

## Users

- **Staff of CuteGamingBot (Epsilon)** — owner, admins, moderators, support. They moderate players, run the economy, farm, content, broadcasts and support tickets. *Inferred:* most sessions happen inside the Telegram Mini App on a phone, often a weak Android device; the rest in Telegram Desktop.
- **Administrators of official Telegram groups** — enter through the group door with a personal key, watch their chat's activity, punish with a mandatory reason, edit positions and rights. The group creator also owns the guard switches.

## Product Purpose

Epsilon is the operating panel of the CuteGamingBot project: one place to see live project numbers (bot calls, messages in all groups, the game "кут" turnover, players in the database) and to act on players, groups and staff. Success: a staff member or group admin finds the number or the action they need within a few seconds on a phone, without mistakes.

## Positioning

The only panel wired straight into the bot's own data: realtime counters refresh every second, every punishment lands in the group's archive with its reason, and rights follow the group's position ladder.

## Operating Context

- Opened from the admin bot as a Telegram Mini App; the door screen chooses the staff panel or the group panel.
- Phone viewport means Telegram iOS/Android; everything else renders the desktop layout.
- Sessions are token-based; a security boot screen prefetches the dashboard numbers.
- A performance mode exists for weak devices; users pick a personal interface color in the palette.

## Capabilities and Constraints

- Russian interface copy, the project's own terms: «кут» (in-game currency), «БЧ», «Ника» (balance keeper), «Архив», «Варн/Мут/Бан/Кик».
- Staff sections are permission-gated (29 sections); group tabs follow the position's rights.
- Numbers must never be invented: when a counter fails the UI says so instead of showing zeros.
- Must stay smooth on the weakest phones: effects degrade or switch off with reduced motion and the optimization toggle.

## Brand Commitments

- Name: Epsilon panel for CuteGamingBot. True-black interface with one user-chosen accent color.
- The owner's six phone references (dark bento tiles, pill bottom navigation, card → bottom sheet) are binding for the phone composition.
- The user's palette color must be visible on the panel backgrounds as a gradient, on phone and PC.

## Evidence on Hand

Real data comes from the API at runtime only. No testimonials, benchmarks or public claims exist; none may be invented.

## Product Principles

1. The number first: every tab leads with the live figure its user came for.
2. Touch to understand: any metric tile opens its detail and next action.
3. One thumb: primary navigation and actions sit within reach at the bottom.
4. Honest states: loading, empty and failed counters are named, never faked.
5. Light on the device: motion is decoration only when the device can afford it.

## Accessibility & Inclusion

*Inferred:* respect `prefers-reduced-motion`; keep text contrast ≥ 4.5:1 on graphite; tap targets ≥ 44px.
