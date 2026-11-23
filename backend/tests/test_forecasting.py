from datetime import date, timedelta
from decimal import Decimal as D

from app.database.session import SessionLocal
from app.forecasting.demand_forecast import generate_three_month_forecast
from app.forecasting.periods import (
    FORECAST_ANCHOR,
    forecast_period_starts,
    history_period_starts,
    period_end_for,
    period_start_for,
)
from app.forecasting.planning_demand import get_planning_demand
from tests.helpers import backdate_item, history_window, make_item, seed_daily, seed_history


def _forecast(item_id, today=None):
    db = SessionLocal()
    try:
        return generate_three_month_forecast(db, item_id, today=today)
    finally:
        db.close()


def _planning(item_id, today=None):
    db = SessionLocal()
    try:
        return get_planning_demand(db, item_id, today=today)
    finally:
        db.close()


# ---- period grid ---------------------------------------------------------

def test_period_grid_is_stable_for_every_day_in_a_period():
    start = period_start_for(FORECAST_ANCHOR + timedelta(days=95))
    for offset in range(30):
        assert period_start_for(start + timedelta(days=offset)) == start


def test_history_periods_are_three_complete_periods_before_today():
    today = date(2026, 6, 15)
    starts = history_period_starts(today)
    assert len(starts) == 3
    assert starts[1] - starts[0] == timedelta(days=30)
    assert period_end_for(starts[-1]) < period_start_for(today)


def test_forecast_periods_start_with_period_containing_today():
    today = date(2026, 6, 15)
    assert forecast_period_starts(today)[0] == period_start_for(today)


# ---- forecast statuses ---------------------------------------------------

def test_new_item_without_history_returns_insufficient_data_not_an_error(client):
    item = make_item(client)
    result = _forecast(item["id"])
    assert result["status"] == "insufficient_data"
    assert result["forecasts"] == []
    assert result["average_monthly_demand"] is None


def test_item_with_no_consumption_returns_zero_forecast(client):
    item = make_item(client)
    backdate_item(item["id"])
    result = _forecast(item["id"])
    assert result["status"] == "no_demand"
    assert all(f["predicted_demand"] == D("0.000") for f in result["forecasts"])


def test_steady_demand_produces_expected_forecast(client):
    item = make_item(client)
    backdate_item(item["id"])
    seed_history(item["id"], 9)  # 270 units per 30-day period
    result = _forecast(item["id"])
    assert result["status"] == "ok"
    assert result["average_monthly_demand"] == D("270.000")
    assert [f["predicted_demand"] for f in result["forecasts"]] == [D("270.000")] * 3


def test_untracked_history_is_not_averaged_in_as_zero(client):
    # Consumption tracking starts inside the history window, so the first period
    # is unknown. Treating those days as zero would understate demand.
    item = make_item(client)
    backdate_item(item["id"])
    start, end = history_window()
    seed_daily(item["id"], 30, period_end_for(start) + timedelta(days=1), end)
    result = _forecast(item["id"])
    assert result["status"] == "insufficient_data"
    assert result["forecasts"] == []
    assert "consumption has only been tracked since" in result["status_message"]


def test_genuine_zero_period_is_included_as_zero_and_explained(client):
    # Tracking began before the window, so an empty period is real zero demand.
    item = make_item(client)
    backdate_item(item["id"])
    start, end = history_window()
    seed_daily(item["id"], 5, start - timedelta(days=1), start - timedelta(days=1))
    seed_daily(item["id"], 30, period_end_for(start) + timedelta(days=1), end)
    result = _forecast(item["id"])
    assert result["status"] == "ok"
    assert result["historical_demand"][0] == D("0")
    assert result["average_monthly_demand"] == D("600.000")
    assert "no consumption" in result["status_message"]


def test_missing_item_returns_none(client):
    assert _forecast(999999) is None


def test_inactive_item_returns_none(client):
    item = make_item(client)
    client.patch(f"/inventory/{item['id']}", json={"is_active": False})
    assert _forecast(item["id"]) is None


# ---- API behaviour -------------------------------------------------------

def test_forecast_endpoint_returns_200_for_zero_demand(client):
    item = make_item(client)
    backdate_item(item["id"])
    response = client.get(f"/forecasting/{item['id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "no_demand"


def test_planning_endpoint_returns_200_for_new_item(client):
    item = make_item(client)
    response = client.get(f"/forecasting/{item['id']}/planning")
    assert response.status_code == 200
    body = response.json()
    assert body["forecast_status"] == "insufficient_data"
    assert body["planning_periods"] == []


# ---- overrides -----------------------------------------------------------

def _override_payload(forecast, adjusted, **overrides):
    period = forecast["forecasts"][0]
    payload = {
        "forecast_start_date": period["start_date"].isoformat(),
        "forecast_end_date": period["end_date"].isoformat(),
        "original_predicted_demand": str(period["predicted_demand"]),
        "adjusted_demand": str(adjusted),
        "adjusted_by": "Planner A",
        "reason": "Promotion expected",
    }
    payload.update(overrides)
    return payload


def test_override_replaces_planning_value_but_not_ai_forecast(client):
    item = make_item(client)
    backdate_item(item["id"])
    seed_history(item["id"], 9)
    forecast = _forecast(item["id"])
    response = client.post(f"/forecasting/{item['id']}/overrides", json=_override_payload(forecast, 300))
    assert response.status_code == 201, response.text

    planning = _planning(item["id"])
    first = planning["planning_periods"][0]
    assert first["final_planning_demand"] == D("300.000")
    assert first["original_ai_demand"] == D("270.000")
    assert first["adjustment_status"] == "manually_adjusted"
    assert _forecast(item["id"])["forecasts"][0]["predicted_demand"] == D("270.000")


def test_override_remains_attached_to_its_period_for_every_day_in_that_period(client):
    item = make_item(client)
    backdate_item(item["id"])
    seed_history(item["id"], 9)
    forecast = _forecast(item["id"])
    client.post(f"/forecasting/{item['id']}/overrides", json=_override_payload(forecast, 300))

    period_start = forecast["forecasts"][0]["start_date"]
    for offset in (0, 10, 29):
        day = period_start + timedelta(days=offset)
        if period_start_for(day) != period_start:
            continue
        planning = _planning(item["id"], today=day)
        assert planning["planning_periods"][0]["adjustment_status"] == "manually_adjusted"


def test_duplicate_override_for_same_period_is_rejected(client):
    item = make_item(client)
    backdate_item(item["id"])
    seed_history(item["id"], 9)
    forecast = _forecast(item["id"])
    assert client.post(f"/forecasting/{item['id']}/overrides", json=_override_payload(forecast, 300)).status_code == 201
    assert client.post(f"/forecasting/{item['id']}/overrides", json=_override_payload(forecast, 310)).status_code == 409


def test_override_with_stale_original_demand_is_rejected(client):
    item = make_item(client)
    backdate_item(item["id"])
    seed_history(item["id"], 9)
    forecast = _forecast(item["id"])
    response = client.post(
        f"/forecasting/{item['id']}/overrides",
        json=_override_payload(forecast, 300, original_predicted_demand="123"),
    )
    assert response.status_code == 409


def test_override_for_wrong_dates_is_rejected(client):
    item = make_item(client)
    backdate_item(item["id"])
    seed_history(item["id"], 9)
    forecast = _forecast(item["id"])
    response = client.post(
        f"/forecasting/{item['id']}/overrides",
        json=_override_payload(forecast, 300, forecast_start_date="2001-01-01", forecast_end_date="2001-01-30"),
    )
    assert response.status_code == 422


def test_override_cannot_be_created_when_no_forecast_exists(client):
    item = make_item(client)
    forecast_like = {"forecasts": [{
        "start_date": date.today(), "end_date": date.today() + timedelta(days=29), "predicted_demand": None,
    }]}
    response = client.post(
        f"/forecasting/{item['id']}/overrides",
        json=_override_payload(forecast_like, 100, original_predicted_demand="0"),
    )
    assert response.status_code == 422


def test_override_can_be_deleted_and_planning_reverts(client):
    item = make_item(client)
    backdate_item(item["id"])
    seed_history(item["id"], 9)
    forecast = _forecast(item["id"])
    override_id = client.post(
        f"/forecasting/{item['id']}/overrides", json=_override_payload(forecast, 300)
    ).json()["id"]
    assert client.delete(f"/forecasting/{item['id']}/overrides/{override_id}").status_code == 204
    assert _planning(item["id"])["planning_periods"][0]["adjustment_status"] == "ai_forecast"


def test_deleting_another_items_override_is_not_allowed(client):
    a = make_item(client, code="A-1", name="Alpha")
    b = make_item(client, code="B-1", name="Beta")
    backdate_item(a["id"]); seed_history(a["id"], 9)
    forecast = _forecast(a["id"])
    override_id = client.post(f"/forecasting/{a['id']}/overrides", json=_override_payload(forecast, 300)).json()["id"]
    assert client.delete(f"/forecasting/{b['id']}/overrides/{override_id}").status_code == 404
