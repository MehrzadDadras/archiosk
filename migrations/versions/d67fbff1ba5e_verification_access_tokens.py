"""verification access tokens

CLAUDE-LIVE-VERIFICATION-ACCOUNT-MECHANISM-01: models.
VerificationAccessToken, mirroring password_reset_tokens' own shape
exactly (see the baseline revision, f8620fa70917) - hand-written for
the same reason that one was: app.py's _register_database() always
runs db.create_all() first, so autogenerate never sees a diff to work
from (migrations/README explains this in full). This is the "NEXT real
schema change" that README predicted should be a normal Alembic
revision rather than another hand-written function in app.py.

Revision ID: d67fbff1ba5e
Revises: f8620fa70917
Create Date: 2026-08-17 16:25:50.608894

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd67fbff1ba5e'
down_revision = 'f8620fa70917'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "verification_access_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_verification_access_tokens_user_id", "verification_access_tokens", ["user_id"])
    op.create_index("ix_verification_access_tokens_token_hash", "verification_access_tokens", ["token_hash"], unique=True)


def downgrade():
    op.drop_table("verification_access_tokens")
