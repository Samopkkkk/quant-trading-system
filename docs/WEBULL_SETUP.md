# Webull setup — sandbox first, then live

The recommended path is **paper → UAT sandbox (dry-run) → UAT sandbox (live) →
production with tiny size**. Never skip straight to production.

## 0. Prerequisites

```bash
pip install -r requirements.txt
pip install webull-python-sdk-core webull-python-sdk-trade   # only needed for live
```

You also need network egress to the Webull host. In a restricted environment
(e.g. the web sandbox this repo was built in), add the host to your egress
allowlist — `us-openapi-alb.uat.webullbroker.com` for UAT, `api.webull.com` for
production. See https://code.claude.com/docs/en/claude-code-on-the-web.

## 1. Get credentials

- **UAT sandbox**: Webull publishes shared test app keys in its developer docs
  (https://developer.webull.com/apis/docs/sdk). These hit the UAT endpoint and
  touch no real money.
- **Production**: apply at https://developer.webull.com/ for your own
  `app_key` / `app_secret`, and find your `account_id` in the Webull app.

## 2. Set environment variables (never hard-code secrets)

```bash
export WEBULL_APP_KEY="..."
export WEBULL_APP_SECRET="..."
export WEBULL_ACCOUNT_ID="..."
# Optional but recommended: map symbols to Webull instrument IDs so the agent
# does not need a live lookup for each order.
export WEBULL_INSTRUMENT_IDS="AAPL:913256135,MSFT:913354090"
```

## 3. Preflight

```bash
python -m agent.cli preflight                 # checks UAT sandbox
python -m agent.cli preflight --production     # checks production endpoint
```

Every line should read `[OK]` before you continue:

```
Webull preflight (us-openapi-alb.uat.webullbroker.com):
  [OK] Webull SDK installed: webullsdkcore + webullsdktrade
  [OK] Credentials present: all set
  [OK] Instrument IDs mapped: 2 mapped
  [OK] Webull endpoint reachable: us-openapi-alb.uat.webullbroker.com
```

## 4. Dry run (connects, sends NO orders)

This connects to Webull, reads your real account/positions, and **logs the
orders it would place** without sending them. It is the safe way to confirm the
strategy, sizing, and instrument resolution are all correct.

```bash
python -m agent.cli live --symbols AAPL,MSFT --strategy ma_cross --dry-run --cycles 1
# -> [DRY RUN] would BUY 57 AAPL (MARKET)
#    Dry run complete: 1 order(s) would have been sent.
```

## 5. Live on the UAT sandbox

Once the dry run looks right, drop `--dry-run`. On the UAT endpoint this places
orders against the sandbox account (no real money). You must pass
`--i-understand-the-risk` and type `TRADE` to confirm.

```bash
python -m agent.cli live --symbols AAPL --strategy ma_cross --i-understand-the-risk --cycles 1
```

## 6. Production (real money) — only when you are sure

Add `--production`. Start with a tiny position cap and a tight kill switch, and
keep `--cycles` small while you watch it.

```bash
python -m agent.cli live --symbols AAPL --strategy ma_cross \
    --production --i-understand-the-risk \
    --max-position 0.05 --max-drawdown 0.05 --cycles 1
```

## Safety mechanisms that are always on

- **Paper by default.** Live requires `live=True` + credentials + explicit flags.
- **Kill switch.** Trading stops and positions flatten once drawdown from peak
  hits `--max-drawdown`.
- **Daily-loss halt.** No new exposure after `--daily-loss-limit` for the day.
- **Position + leverage caps.** `--max-position`, `--max-leverage`.

### Persist state across restarts (important for live)

A live bot restarts (crashes, redeploys). Pass `--state` so the drawdown peak,
kill-switch flag, and trade log survive restarts — otherwise a restart resets the
peak and the kill switch silently won't fire on an in-progress drawdown.

```bash
python -m agent.cli live --symbols AAPL --strategy ma_cross \
    --i-understand-the-risk --state ~/.webull-agent/state.json
```

The trade log is appended to the same JSON file. To clear a tripped kill switch,
stop the bot and delete (or edit) `risk_state.kill_switch_active` in that file —
a deliberate manual action, by design.

## Honest caveat

The live adapter targets the official SDK call surface (`ApiClient` / `Account`
/ `OrderOperation`) but was developed where the Webull endpoints were not
reachable, so it could not be exercised against the live API. Validate every
step on the UAT sandbox, in dry-run first, before risking real funds. And see
[RETURNS_AND_RISK.md](RETURNS_AND_RISK.md): nothing here guarantees a profit.
