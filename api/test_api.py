from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_get_products_returns_list():
    response = client.get("/products")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_nova_filter_returns_only_matching_group():
    response = client.get("/products?nova_group=1")
    assert response.status_code == 200
    for product in response.json():
        assert product["nova_group"] == 1


def test_get_product_by_id():
    products = client.get("/products").json()
    if products:
        pid = products[0]["product_id"]
        response = client.get(f"/products/{pid}")
        assert response.status_code == 200
        assert response.json()["product_id"] == pid


def test_get_product_not_found_returns_404():
    response = client.get("/products/invalid_id_that_does_not_exist")
    assert response.status_code == 404


def test_stats_shape():
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_products" in data
    assert "enrichment_rate" in data
    assert "nova_counts" in data
