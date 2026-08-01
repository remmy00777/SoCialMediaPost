from pathlib import Path

from fastapi.testclient import TestClient

from app.services.media_validation import probe_media


def test_auth_csrf_and_pause(client: TestClient, csrf: dict[str, str]):
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/system/pause").status_code == 403
    paused = client.post("/api/system/pause", headers=csrf)
    assert paused.status_code == 200
    assert paused.json()["paused"] is True
    resumed = client.post("/api/system/resume", headers=csrf)
    assert resumed.json()["paused"] is False


def test_import_trend_and_list(client: TestClient, csrf: dict[str, str]):
    response = client.post(
        "/api/trends/import",
        headers=csrf,
        json={"platform": "youtube", "url": "https://youtu.be/demo123", "title": "Manual trend", "topic": "testing", "metrics": {"views": 1000}},
    )
    assert response.status_code == 200
    trends = client.get("/api/trends").json()
    assert len(trends) == 1
    assert trends[0]["source_label"] == "Manual Url Import"


def test_demo_workflow_renders_three_valid_variants(client: TestClient, csrf: dict[str, str]):
    response = client.post("/api/workflows/demo", headers=csrf)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["content_run"]["status"] == "succeeded"
    assert payload["simulated_publication"]["status"] == "simulated"
    assert payload["sample_analytics"]["metrics"]["views"] == 18400
    packages = client.get("/api/content-packages").json()
    assert len(packages) == 1
    assert len(packages[0]["variants"]) == 3
    for variant in packages[0]["variants"]:
        path = Path(variant["media_path"])
        assert path.exists()
        probe = probe_media(path)
        assert probe["valid"]
        assert probe["width"] == 1080
        assert probe["height"] == 1920
        assert probe["video_codec"] == "h264"
        assert probe["audio_codec"] == "aac"
        package_dir = path.parent
        for required in ["final_video.mp4", "preview.mp4", "thumbnail.png", "subtitles.srt", "subtitles.vtt", "script.md", "caption.txt", "title.txt", "description.txt", "hashtags.txt", "metadata.json", "trend_analysis.json", "generation_report.json", "compliance_report.json", "originality_report.json", "publishing_status.json", "analytics.json"]:
            assert (package_dir / required).exists(), required


def test_backup_and_reports(client: TestClient, csrf: dict[str, str]):
    backup = client.post("/api/backup", headers=csrf)
    assert backup.status_code == 200
    assert Path(backup.json()["path"]).exists()
    csv_report = client.get("/api/reports/daily_trends.csv")
    assert csv_report.status_code == 200
    assert "text/csv" in csv_report.headers["content-type"]
    pdf_report = client.get("/api/reports/platform_comparison.pdf")
    assert pdf_report.status_code == 200
    assert pdf_report.content.startswith(b"%PDF")


def test_portal_and_root_redirect(client: TestClient):
    root = client.get('/', follow_redirects=False)
    assert root.status_code in {302, 307}
    assert root.headers['location'] == '/portal/'
    portal = client.get('/portal/')
    assert portal.status_code == 200
    assert 'SoCialMediaPost Studio' in portal.text
    js = client.get('/portal/app.js')
    assert js.status_code == 200
    assert 'Pause All Automation' in js.text


def test_managed_file_rejects_traversal(client: TestClient):
    response = client.get('/files/../../etc/passwd')
    assert response.status_code in {404, 422}
