def test_robots_txt(client):
    """Test robots.txt returns correct content"""
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response["Content-Type"] == "text/plain"
    assert "User-agent: *\nDisallow: /" in response.content.decode()
