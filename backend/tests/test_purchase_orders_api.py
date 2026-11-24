from datetime import date

from tests.helpers import get_item_row, make_item


def _po(client, item_id, number="PO-1", ordered="100", **extra):
    payload = {
        "po_number": number,
        "inventory_item_id": item_id,
        "supplier_name": "Acme Textiles",
        "ordered_quantity": ordered,
        "order_date": date.today().isoformat(),
        "unit_cost": "1.5",
    }
    payload.update(extra)
    return client.post("/purchase-orders", json=payload)


def _advance(client, po_id, *statuses):
    for status in statuses:
        response = client.patch(f"/purchase-orders/{po_id}/status", json={"status": status})
        assert response.status_code == 200, response.text


def test_new_purchase_order_is_always_a_draft(client):
    item = make_item(client)
    response = _po(client, item["id"])
    assert response.status_code == 201
    assert response.json()["status"] == "draft"


def test_clients_cannot_create_a_purchase_order_in_an_approved_state(client):
    item = make_item(client)
    assert _po(client, item["id"], status="approved").status_code == 422


def test_purchase_order_for_inactive_item_is_not_found(client):
    item = make_item(client)
    client.patch(f"/inventory/{item['id']}", json={"is_active": False})
    assert _po(client, item["id"]).status_code == 404


def test_duplicate_po_number_is_conflict(client):
    item = make_item(client)
    assert _po(client, item["id"], number="PO-DUP").status_code == 201
    assert _po(client, item["id"], number="PO-DUP").status_code == 409


def test_invalid_status_transition_is_rejected(client):
    item = make_item(client)
    po_id = _po(client, item["id"]).json()["id"]
    response = client.patch(f"/purchase-orders/{po_id}/status", json={"status": "ordered"})
    assert response.status_code == 409


def test_receiving_stock_increases_on_hand_once_per_delta(client):
    item = make_item(client, on_hand=10)
    po_id = _po(client, item["id"]).json()["id"]
    _advance(client, po_id, "pending", "approved", "ordered")

    first = client.post(f"/purchase-orders/{po_id}/receive", json={"received_quantity": "40"})
    assert first.status_code == 200
    assert first.json()["status"] == "partially_received"
    assert get_item_row(item["id"])[0] == 50

    second = client.post(f"/purchase-orders/{po_id}/receive", json={"received_quantity": "100"})
    assert second.json()["status"] == "received"
    assert get_item_row(item["id"])[0] == 110


def test_receiving_more_than_ordered_is_rejected_and_stock_unchanged(client):
    item = make_item(client, on_hand=10)
    po_id = _po(client, item["id"], ordered="50").json()["id"]
    _advance(client, po_id, "pending", "approved", "ordered")
    response = client.post(f"/purchase-orders/{po_id}/receive", json={"received_quantity": "60"})
    assert response.status_code == 400
    assert get_item_row(item["id"])[0] == 10


def test_cannot_receive_against_a_draft(client):
    item = make_item(client, on_hand=10)
    po_id = _po(client, item["id"]).json()["id"]
    response = client.post(f"/purchase-orders/{po_id}/receive", json={"received_quantity": "5"})
    assert response.status_code == 400
    assert get_item_row(item["id"])[0] == 10


def test_received_stock_cannot_be_cancelled(client):
    item = make_item(client)
    po_id = _po(client, item["id"]).json()["id"]
    _advance(client, po_id, "pending", "approved", "ordered")
    client.post(f"/purchase-orders/{po_id}/receive", json={"received_quantity": "10"})
    assert client.patch(f"/purchase-orders/{po_id}/status", json={"status": "cancelled"}).status_code == 409


def test_list_can_filter_by_item(client):
    a = make_item(client, code="A-1", name="Alpha")
    b = make_item(client, code="B-1", name="Beta")
    _po(client, a["id"], number="PO-A")
    _po(client, b["id"], number="PO-B")
    rows = client.get(f"/purchase-orders?inventory_item_id={a['id']}").json()
    assert [r["po_number"] for r in rows] == ["PO-A"]


def test_unknown_purchase_order_is_not_found(client):
    assert client.get("/purchase-orders/999999").status_code == 404
