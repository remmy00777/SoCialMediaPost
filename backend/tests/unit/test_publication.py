from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.db import SessionLocal
from app.core.security import SecretBox
from app.models import (
    ContentPackage,
    OAuthCredential,
    OriginalityCheck,
    PlatformAccount,
    PlatformVariant,
    PolicyCheck,
    PublicationJob,
)
from app.services.publication import PublicationService


class FakeAdapter:
    platform = 'youtube'
    def verify_permissions(self, token): return {'valid': token == 'access'}
    def validate_media(self, path): return {'platform_valid': path.is_file()}
    def upload_media(self, path, metadata, token): return {'upload_id': 'upload-1'}
    def publish_media(self, upload_id, metadata, token): return {'id': 'post-1', 'status': 'published'}
    def retrieve_publish_status(self, post_id, token): return {'status': 'published'}
    def refresh_authorization(self, token): return {'access_token': 'access', 'expires_in': 3600}


class FakeRegistry:
    def get(self, platform):
        assert platform == 'youtube'
        return FakeAdapter()


def test_publication_preflight_and_idempotency(tmp_path: Path):
    media = tmp_path / 'video.mp4'
    media.write_bytes(b'valid fixture')
    with SessionLocal() as db:
        package = ContentPackage(
            concept_id='concept-fixture', status='ready_to_post', title='Original title',
            storage_path=str(tmp_path / 'generated'), quality_score=91,
            predicted_performance={}, generation_metadata={}, approval_mode='review',
            idempotency_key='package-key',
        )
        db.add(package); db.flush()
        db.add_all([
            PolicyCheck(content_package_id=package.id, passed=True, checks={}, blocking_reasons=[]),
            OriginalityCheck(content_package_id=package.id, passed=True, component_scores={}, thresholds={}, blocking_reasons=[]),
        ])
        variant = PlatformVariant(content_package_id=package.id, platform='youtube', status='ready_to_post', media_path=str(media), metadata_json={})
        account = PlatformAccount(platform='youtube', external_account_id='channel-1', authorization_status='connected', token_health='healthy', publishing_eligible=True)
        db.add_all([variant, account]); db.flush()
        db.add(OAuthCredential(platform_account_id=account.id, encrypted_access_token=SecretBox().encrypt('access'), expires_at=datetime.now(UTC) + timedelta(hours=1)))
        job = PublicationJob(platform_variant_id=variant.id, platform_account_id=account.id, status='queued', idempotency_key='publication-key')
        db.add(job); db.commit()
        service = PublicationService(db, adapters=FakeRegistry())
        post = service.process(job.id)
        assert post.external_post_id == 'post-1'
        assert db.get(PublicationJob, job.id).status == 'submitted'
        assert service.process(job.id).id == post.id
        assert service.poll(post.id).status == 'published'


def test_publication_helpers_and_pause_block(tmp_path: Path):
    from app.models import ErrorEvent, SystemSetting
    from app.services.publication import PublicationBlocked
    media = tmp_path / 'video.mp4'; media.write_bytes(b'valid')
    with SessionLocal() as db:
        package = ContentPackage(concept_id='c2', status='ready_to_post', title='Title', storage_path=str(tmp_path / 'g2'), quality_score=90, predicted_performance={}, generation_metadata={}, approval_mode='review', idempotency_key='pk2')
        db.add(package); db.flush()
        db.add_all([PolicyCheck(content_package_id=package.id, passed=True), OriginalityCheck(content_package_id=package.id, passed=True)])
        variant = PlatformVariant(content_package_id=package.id, platform='youtube', media_path=str(media))
        account = PlatformAccount(platform='youtube', external_account_id='channel-2', authorization_status='connected', token_health='healthy', publishing_eligible=True)
        db.add_all([variant, account]); db.flush()
        db.add(OAuthCredential(platform_account_id=account.id, encrypted_access_token=SecretBox().encrypt('access'), expires_at=datetime.now(UTC) + timedelta(hours=1)))
        job = PublicationJob(platform_variant_id=variant.id, platform_account_id=account.id, status='queued', idempotency_key='job2')
        db.add_all([job, SystemSetting(key='global_pause', value=True)]); db.commit()
        service = PublicationService(db, adapters=FakeRegistry())
        try:
            service.process(job.id)
        except PublicationBlocked as exc:
            assert 'pause' in str(exc).lower()
        else:
            raise AssertionError('pause should block publication')
        assert db.get(PublicationJob, job.id).status == 'blocked'
        assert db.query(ErrorEvent).count() == 1
        assert PublicationService._platform_metadata('instagram', account, {})['ig_user_id'] == 'channel-2'
        account.app_review_required = True
        assert PublicationService._platform_metadata('tiktok', account, {})['privacy_level'] == 'SELF_ONLY'
        assert PublicationService._status_name({'data': {'status_code': 'COMPLETE'}}) == 'complete'
