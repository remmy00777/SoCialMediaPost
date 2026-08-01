from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.storage import StorageManager


def test_storage_tree_and_atomic_write(tmp_path: Path):
    settings = Settings(storage_root=tmp_path, session_secret="x" * 32)
    manager = StorageManager(settings)
    target = manager.atomic_write_text(tmp_path / "reports" / "test.txt", "hello")
    assert target.read_text() == "hello"
    assert (tmp_path / "Ready to Post for TikTok").is_dir()


def test_storage_blocks_path_traversal(tmp_path: Path):
    settings = Settings(storage_root=tmp_path, session_secret="x" * 32)
    manager = StorageManager(settings)
    with pytest.raises(ValueError):
        manager.ensure_inside_root(tmp_path.parent / "outside.txt")


def test_storage_copy_move_mirror_and_usage(tmp_path: Path):
    settings = Settings(storage_root=tmp_path, session_secret='x' * 32)
    manager = StorageManager(settings)
    source_file = tmp_path / 'temporary' / 'source.txt'
    source_file.write_text('content')
    copied = manager.atomic_copy(source_file, tmp_path / 'reports' / 'copied.txt')
    assert copied.read_text() == 'content'
    draft = manager.package_dir('tiktok', 'drafts', 'pkg')
    draft.mkdir(parents=True)
    (draft / 'final_video.mp4').write_bytes(b'media')
    ready = manager.move_package('tiktok', 'pkg', 'drafts', 'ready_to_post')
    assert (ready / 'final_video.mp4').exists()
    mirror = manager.mirror_ready_package('tiktok', ready, 'pkg')
    assert (mirror / 'final_video.mp4').exists()
    assert manager.storage_usage()['file_count'] >= 3
