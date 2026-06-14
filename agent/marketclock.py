"""US equity market-hours clock.

A poll-loop auto-trader must not act when the market is closed: quotes are stale,
orders are rejected or queued unpredictably, and a "signal" computed off-hours can
fire at the next open on information that has already moved the price.

`is_market_open` checks weekday, the NYSE/Nasdaq full-closure holiday calendar, and
the regular-trading-hours window (09:30–16:00 America/New_York, DST-aware via
zoneinfo). Half-day early closes (1:00pm) are NOT modelled — treat the holiday set
as needing periodic maintenance; extend HOLIDAYS each year.
"""
from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)

# NYSE/Nasdaq full-day closures. Maintain yearly (observed dates, not nominal).
HOLIDAYS: set[date] = {
    # 2026
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
    date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
    date(2026, 11, 26), date(2026, 12, 25),
    # 2027
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26),
    date(2027, 5, 31), date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6),
    date(2027, 11, 25), date(2027, 12, 24),
}


def _to_et(now: datetime) -> datetime:
    """Normalize to Eastern Time. Naive datetimes are assumed already ET."""
    if now.tzinfo is None:
        return now.replace(tzinfo=ET)
    return now.astimezone(ET)


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in HOLIDAYS


def is_market_open(now: datetime | None = None) -> bool:
    et = _to_et(now or datetime.now(ET))
    if not is_trading_day(et.date()):
        return False
    return RTH_OPEN <= et.timetz().replace(tzinfo=None) < RTH_CLOSE


def next_close_reason(now: datetime | None = None) -> str:
    """Human-readable reason the market is closed (for logging)."""
    et = _to_et(now or datetime.now(ET))
    if et.weekday() >= 5:
        return "weekend"
    if et.date() in HOLIDAYS:
        return "market holiday"
    if et.timetz().replace(tzinfo=None) < RTH_OPEN:
        return "pre-market"
    return "after-hours"
