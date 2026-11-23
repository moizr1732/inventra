from tests.helpers import make_item


def test_create_and_fetch_item(client):
    item = make_item(client, on_hand=50, reserved=10)
    body = client.get(f"/inventory/{item['id']}").json()
    assert body["available_quantity"] == "40.000"


def test_duplicate_item_code_is_conflict(client):
    make_item(client)
    response = client.post("/inventory", json={"item_code": "FAB-001", "item_name": "Other"})
    assert response.status_code == 409


def test_reserved_above_on_hand_is_rejected_on_create(client):
    response = client.post("/inventory", json={
        "item_code": "X-1", "item_name": "X", "on_hand_quantity": "5", "reserved_quantity": "9",
    })
    assert response.status_code == 422


def test_listing_excludes_inactive_items(client):
    item = make_item(client)
    make_item(client, code="FAB-002", name="Linen")
    client.patch(f"/inventory/{item['id']}", json={"is_active": False})
    codes = [i["item_code"] for i in client.get("/inventory").json()]
    assert codes == ["FAB-002"]


def test_cannot_clear_required_reorder_level(client):
    item = make_item(client)
    response = client.patch(f"/inventory/{item['id']}", json={"reorder_level": None})
    assert response.status_code == 422


def test_cannot_clear_required_name(client):
    item = make_item(client)
    response = client.patch(f"/inventory/{item['id']}", json={"item_name": None})
    assert response.status_code == 422


def test_category_may_be_cleared(client):
    item = make_item(client)
    response = client.patch(f"/inventory/{item['id']}", json={"category": None})
    assert response.status_code == 200
    assert response.json()["category"] is None


def test_update_cannot_push_reserved_above_on_hand(client):
    item = make_item(client, on_hand=50, reserved=10)
    response = client.patch(f"/inventory/{item['id']}", json={"on_hand_quantity": "5"})
    assert response.status_code == 422


def test_unknown_item_is_not_found(client):
    assert client.get("/inventory/999999").status_code == 404
    assert client.patch("/inventory/999999", json={"unit_cost": "1"}).status_code == 404


def test_risk_endpoint_returns_fields_the_frontend_uses(client):
    item = make_item(client)
    body = client.get(f"/inventory/{item['id']}/risk").json()
    for field in ("risk_level", "available_quantity", "days_of_cover", "suggested_order_quantity", "requires_replenishment"):
        assert field in body
