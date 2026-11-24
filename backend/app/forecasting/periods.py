"""Fixed 30-day forecast periods.

Periods lie on a permanent grid anchored at FORECAST_ANCHOR, so a period's
start date is the same no matter which day the forecast is generated. This
is what keeps manual overrides attached to the right period.

* Forecast period 1 is the grid period containing today.
* History is the three complete grid periods immediately before it.
"""
from datetime import date, timedelta

FORECAST_ANCHOR = date(2026, 1, 1)
PERIOD_DAYS = 30
HISTORY_PERIODS = 3


def period_start_for(day: date) -> date:
    offset = (day - FORECAST_ANCHOR).days
    return FORECAST_ANCHOR + timedelta(days=(offset // PERIOD_DAYS) * PERIOD_DAYS)


def period_end_for(start: date) -> date:
    return start + timedelta(days=PERIOD_DAYS - 1)


def forecast_period_starts(today: date, count: int = 3) -> list[date]:
    first = period_start_for(today)
    return [first + timedelta(days=i * PERIOD_DAYS) for i in range(count)]


def history_period_starts(today: date, count: int = HISTORY_PERIODS) -> list[date]:
    current = period_start_for(today)
    return [current - timedelta(days=PERIOD_DAYS * (count - i)) for i in range(count)]
