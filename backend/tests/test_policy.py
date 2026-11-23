from decimal import Decimal as D

from app.inventory.policy import (
    calculate_days_of_cover,
    calculate_reorder_point,
    calculate_suggested_order,
    classify_risk,
)


def test_reorder_point_is_demand_over_lead_time_plus_safety_stock():
    assert calculate_reorder_point(D("10"), 5, D("20"), D("0")) == D("70.000")


def test_reorder_point_never_below_configured_reorder_level():
    assert calculate_reorder_point(D("10"), 5, D("20"), D("100")) == D("100.000")


def test_days_of_cover_is_none_without_demand():
    assert calculate_days_of_cover(D("50"), D("0")) is None


def test_zero_demand_is_no_demand_data_not_critical():
    assert classify_risk(D("0"), D("50"), None, 5, D("10"), 60) == "no_demand_data"


def test_zero_available_stock_is_critical():
    assert classify_risk(D("10"), D("0"), D("0"), 5, D("70"), 60) == "critical"


def test_cover_within_lead_time_is_critical():
    # 40 units at 10/day = 4 days of cover, lead time 5 days.
    assert classify_risk(D("10"), D("40"), D("4"), 5, D("70"), 60) == "critical"


def test_at_or_below_reorder_point_is_low_stock():
    assert classify_risk(D("10"), D("60"), D("6"), 5, D("70"), 60) == "low_stock"


def test_healthy_stock_is_normal():
    assert classify_risk(D("10"), D("100"), D("10"), 5, D("70"), 60) == "normal"


def test_excess_cover_is_overstock():
    assert classify_risk(D("10"), D("200"), D("20"), 5, D("70"), 15) == "overstock"


def test_suggested_order_restores_reorder_point():
    assert calculate_suggested_order(D("70"), D("50")) == D("20.000")


def test_suggested_order_is_zero_when_position_covers_reorder_point():
    assert calculate_suggested_order(D("70"), D("80")) == D("0.000")
