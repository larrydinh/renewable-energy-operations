"""The packaged frontend must load without a database connection or a CDN."""

from fastapi.testclient import TestClient

from energy_ops.api import create_app


def test_frontend_and_assets_are_served_without_database():
    with TestClient(create_app()) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "text/html" in page.headers["content-type"]
        assert 'type="module"' in page.text
        assert "/assets/app.js" in page.text
        for asset in ("app.js", "data.js", "styles.css"):
            response = client.get("/assets/" + asset)
            assert response.status_code == 200
            assert response.content
        assert client.get("/assets/unknown.js").status_code == 404
        assert client.get("/health/live").json() == {"status": "ok"}
