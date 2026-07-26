from app.services.github_service import GitHubService


def test_headers():
    service = GitHubService()

    headers = service._headers("test-token")

    assert headers["Authorization"] == "Bearer test-token"
    assert "Accept" in headers