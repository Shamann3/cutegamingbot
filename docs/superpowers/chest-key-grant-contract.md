# Chest key grant contract (MVP, donate-bot path)

## Purchase flow
1. Game opens the donate bot (`CuteGamingBot`) with a start payload meaning
   "grant N chest keys to this user", where N is the quantity chosen in-game
   (price = 25★ × N).
2. After the Stars payment succeeds, the donate bot grants N keys by calling
   `chest_db.grant_keys(user_id, N)` (shares this DB) OR by an authenticated
   internal HTTP call (see below).
3. The player opens chests in-game via `POST /api/chests/open`.

## Proposed start payload
`chest_{N}` where N is 1..10 (validate range on the bot side).
Keep it in the Telegram-allowed charset `[A-Za-z0-9_-]`.
The game builds this payload where it currently builds `insert_{amount}_`
(see `src/constants/donate.js`) — that change is part of the frontend plan,
not this backend plan.

## Grant entry point
- In-process (donate bot shares this codebase): `await chest_db.grant_keys(uid, n)`.
- Out-of-process: add a future internal endpoint `POST /internal/chests/grant`
  guarded by a shared secret. NOT built in MVP — documented here only.

## Future native-Stars swap
When moving to native Stars, replace step 2: on `successful_payment`, parse the
invoice payload for N and call the same `grant_keys(uid, N)`. All in-game opening
logic is unchanged.
