from datetime import date, timedelta
from decimal import Decimal as D

from app.database.session import SessionLocal
from app.inventory.stock_risk import get_item_stock_risk
from tests.helpers import make_item, seed_analytics_window, seed_daily


def _risk(item_id, overstock_days=60):
    db = SessionLocal()
    try:
        return get_item_stock_risk(db, item_id, overstock_days=overstock_days)
    finally:
        db.close()


def _po(client, item_id, po_number, ordered, status="draft", received=0):
    created = client.post("/purchase-orders", json={
        "po_number": po_number,
        "inventory_item_id": item_id,
        "supplier_name": "Acme Textiles",
        "ordered_quantity": str(ordered),
        "order_date": date.today().isoformat(),
        "unit_cost": "1.5",
    })
    assert created.status_code == 201, created.text
    po_id = created.json()["id"]
    if status != "draft":
        for step in ["pending", "approved"] if status in ("approved", "partially_received", "received") else ["pending"]:
            assert client.patch(f"/purchase-orders/{po_id}/status", json={"status": step}).status_code == 200
        if status == "partially_received":
            assert client.post(f"/purchase-orders/{po_id}/receive", json={"received_quantity": str(received)}).status_code == 200
    return po_id


def test_healthy_item_is_normal_with_no_order_needed(client):
    item = make_item(client, on_hand=100, safety_stock=20, lead_time_days=5)
    seed_analytics_window(item["id"], 10)
    risk = _risk(item["id"])
    assert risk["average_daily_consumption"] == D("10.000")
    assert risk["days_of_cover"] == D("10.00")
    assert risk["calculated_reorder_point"] == D("70.000")
    assert risk["risk_level"] == "normal"
    assert risk["requires_replenishment"] is False


def test_average_uses_tracked_days_not_full_window(client):
    # Tracked for only 20 days at 10/day. Dividing by 90 would wrongly give 2.22/day.
    item = make_item(client, on_hand=100, lead_time_days=5)
    end = date.today() - timedelta(days=1)
    seed_daily(item["id"], 10, end - timedelta(days=19), end)
    risk = _risk(item["id"])
    assert risk["observed_days"] == 20
    assert risk["average_daily_consumption"] == D("10.000")


def test_shortage_suggests_order_up_to_reorder_point(client):
    item = make_item(client, on_hand=30, safety_stock=20, lead_time_days=5)
    seed_analytics_window(item["id"], 10)
    risk = _risk(item["id"])
    assert risk["risk_level"] == "critical"
    assert risk["suggested_order_quantity"] == D("40.000")
    assert risk["requires_replenishment"] is True


def test_open_purchase_order_reduces_suggested_order(client):
    item = make_item(client, on_hand=30, safety_stock=20, lead_time_days=5)
    seed_analytics_window(item["id"], 10)
    _po(client, item["id"], "PO-OPEN-1", 50, status="approved")
    risk = _risk(item["id"])
    assert risk["outstanding_open_po_quantity"] == D("50.000")
    assert risk["suggested_order_quantity"] == D("0.000")
    assert risk["requires_replenishment"] is False
    # Physical shortage remains critical even though an order is inbound.
    assert risk["risk_level"] == "critical"


def test_draft_purchase_orders_are_not_counted(client):
    item = make_item(client, on_hand=30, safety_stock=20, lead_time_days=5)
    seed_analytics_window(item["id"], 10)
    _po(client, item["id"], "PO-DRAFT-1", 500)
    risk = _risk(item["id"])
    assert risk["outstanding_open_po_quantity"] == D("0.000")
    assert risk["suggested_order_quantity"] == D("40.000")


def test_partially_received_order_counts_only_remaining_quantity(client):
    item = make_item(client, on_hand=30, safety_stock=20, lead_time_days=5)
    seed_analytics_window(item["id"], 10)
    _po(client, item["id"], "PO-PART-1", 100, status="partially_received", received=60)
    risk = _risk(item["id"])
    # 100 ordered, 60 received -> 40 still outstanding, counted exactly once.
    assert risk["outstanding_open_po_quantity"] == D("40.000")


def test_no_consumption_means_no_demand_data(client):
    item = make_item(client, on_hand=30)
    risk = _risk(item["id"])
    assert risk["risk_level"] == "no_demand_data"
    assert risk["days_of_cover"] is None
    assert risk["suggested_order_quantity"] == D("0.000")


def test_overstock_detected_when_cover_exceeds_threshold(client):
    item = make_item(client, on_hand=1000, lead_time_days=5)
    seed_analytics_window(item["id"], 10)
    assert _risk(item["id"], overstock_days=60)["risk_level"] == "overstock"


def test_inactive_item_has_no_risk(client):
    item = make_item(client)
    client.patch(f"/inventory/{item['id']}", json={"is_active": False})
    assert _risk(item["id"]) is None
    assert client.get(f"/inventory/{item['id']}/risk").status_code == 404
