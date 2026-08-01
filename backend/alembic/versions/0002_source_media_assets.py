"""add rights-managed source media assets

Revision ID: 0002_source_media_assets
Revises: 0001_initial
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_source_media_assets"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "source_media_assets" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "source_media_assets",
        sa.Column("source_video_id", sa.String(length=36), nullable=False),
        sa.Column("uploaded_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("media_validation", sa.JSON(), nullable=False),
        sa.Column("rights_status", sa.String(length=40), nullable=False),
        sa.Column("rights_owner", sa.String(length=255), nullable=False),
        sa.Column("license_reference", sa.Text(), nullable=True),
        sa.Column("allow_full_reuse", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rights_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source_video_id"], ["source_videos.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path"),
    )
    op.create_index("ix_source_media_assets_source_video_id", "source_media_assets", ["source_video_id"])
    op.create_index("ix_source_media_assets_sha256", "source_media_assets", ["sha256"])
    op.create_index("ix_source_media_assets_rights_status", "source_media_assets", ["rights_status"])


def downgrade() -> None:
    if "source_media_assets" not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_index("ix_source_media_assets_rights_status", table_name="source_media_assets")
    op.drop_index("ix_source_media_assets_sha256", table_name="source_media_assets")
    op.drop_index("ix_source_media_assets_source_video_id", table_name="source_media_assets")
    op.drop_table("source_media_assets")
