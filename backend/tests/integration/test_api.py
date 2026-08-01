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


def test_authorized_source_voiceover_and_permanent_delete(client: TestClient, csrf: dict[str, str], tmp_path: Path):
    import subprocess

    imported = client.post(
        "/api/trends/import",
        headers=csrf,
        json={
            "platform": "youtube",
            "url": "https://youtu.be/owned-demo",
            "title": "Attention management demonstration",
            "topic": "attention management",
            "metrics": {"views": 50000},
        },
    )
    assert imported.status_code == 200, imported.text
    candidate_id = imported.json()["candidate_id"]

    source = tmp_path / "owned-source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=360x640:r=24:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    with source.open("rb") as handle:
        uploaded = client.post(
            f"/api/trends/{candidate_id}/source-media",
            headers=csrf,
            files={"file": (source.name, handle, "video/mp4")},
            data={
                "rights_status": "user_owned",
                "rights_owner": "Test User",
                "license_reference": "",
                "allow_full_reuse": "true",
            },
        )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["source_media"]["allow_full_reuse"] is True

    generated = client.post("/api/workflows/content?max_items=1", headers=csrf)
    assert generated.status_code == 200, generated.text
    assert generated.json()["status"] == "succeeded"
    packages = client.get("/api/content-packages").json()
    assert len(packages) == 1
    package = packages[0]
    assert package["generation_metadata"]["source_media_used"] is True
    assert len(package["variants"]) == 3
    for variant in package["variants"]:
        media = Path(variant["media_path"])
        assert media.exists()
        probe = probe_media(media)
        assert probe["valid"]
        assert probe["duration"] > 2
        metadata = variant["metadata_json"]
        assert metadata["content_mode"] == "authorized_source_with_voiceover_intro"

    deleted = client.request(
        "DELETE",
        f"/api/content-packages/{package['id']}/permanent",
        headers=csrf,
        json={"confirmation": "DELETE"},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    assert deleted.json()["files_deleted"] > 0
    assert client.get(f"/api/content-packages/{package['id']}").status_code == 404


def test_accounts_endpoint_supports_multiple_accounts(client: TestClient):
    from app.core.db import SessionLocal
    from app.models import PlatformAccount, User

    with SessionLocal() as db:
        user = db.query(User).first()
        db.add_all(
            [
                PlatformAccount(
                    user_id=user.id,
                    platform="youtube",
                    external_account_id="channel-a",
                    display_name="Channel A",
                    authorization_status="connected",
                ),
                PlatformAccount(
                    user_id=user.id,
                    platform="youtube",
                    external_account_id="channel-b",
                    display_name="Channel B",
                    authorization_status="connected",
                ),
            ]
        )
        db.commit()
    rows = client.get("/api/accounts").json()
    youtube = next(row for row in rows if row["platform"] == "youtube")
    assert youtube["multiple_accounts_supported"] is True
    assert {item["display_name"] for item in youtube["accounts"]} == {"Channel A", "Channel B"}
