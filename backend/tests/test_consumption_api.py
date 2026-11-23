from datetime import date, timedelta

from tests.helpers import count_rows, get_item_row, make_item


def test_consumption_reduces_on_hand(client):
    item = make_item(client, on_hand=100)
    response = client.post("/consumption", json={
        "inventory_item_id": item["id"], "consumption_date": date.today().isoformat(), "quantity_consumed": "30",
    })
    assert response.status_code == 201
    assert get_item_row(item["id"])[0] == 70


def test_future_consumption_is_rejected(client):
    item = make_item(client)
    response = client.post("/consumption", json={
        "inventory_item_id": item["id"],
        "consumption_date": (date.today() + timedelta(days=1)).isoformat(),
        "quantity_consumed": "1",
    })
    assert response.status_code == 422


def test_consumption_beyond_available_stock_is_rejected_and_nothing_changes(client):
    item = make_item(client, on_hand=20, reserved=5)
    response = client.post("/consumption", json={
        "inventory_item_id": item["id"], "consumption_date": date.today().isoformat(), "quantity_consumed": "16",
    })
    assert response.status_code == 422
    assert get_item_row(item["id"])[0] == 20
    assert count_rows("inventory_consumption") == 0


def test_consumption_for_inactive_item_is_not_found(client):
    item = make_item(client)
    client.patch(f"/inventory/{item['id']}", json={"is_active": False})
    response = client.post("/consumption", json={
        "inventory_item_id": item["id"], "consumption_date": date.today().isoformat(), "quantity_consumed": "1",
    })
    assert response.status_code == 404


def test_zero_or_negative_quantity_is_rejected(client):
    item = make_item(client)
    for qty in ("0", "-5"):
        response = client.post("/consumption", json={
            "inventory_item_id": item["id"], "consumption_date": date.today().isoformat(), "quantity_consumed": qty,
        })
        assert response.status_code == 422


def test_sequential_consumption_cannot_oversell(client):
    item = make_item(client, on_hand=10)
    payload = {"inventory_item_id": item["id"], "consumption_date": date.today().isoformat(), "quantity_consumed": "6"}
    assert client.post("/consumption", json=payload).status_code == 201
    assert client.post("/consumption", json=payload).status_code == 422
    assert get_item_row(item["id"])[0] == 4


def test_analytics_endpoint_reports_reorder_point_and_observed_days(client):
    item = make_item(client, on_hand=100)
    body = client.get(f"/consumption/analytics/{item['id']}").json()
    assert "reorder_point" in body
    assert body["observed_days"] == 0
    assert float(body["average_daily_consumption"]) == 0
