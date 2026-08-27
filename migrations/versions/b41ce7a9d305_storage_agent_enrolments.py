"""storage agent enrolments

CLAUDE-STORAGE-BRIDGE-03: models.StorageAgentEnrolment - which private-network
agent may speak for which project, so ARCHIOSK can read authoritative files from
company-controlled storage without SMB or port 445 facing the internet.

Hand-written for the same reason the three revisions before it were: app.py's
_register_database() always runs db.create_all() first, so autogenerate never
sees a diff to work from (migrations/README explains this in full).

WHY THE DATABASE AND NOT THE FLAT-JSON STORE, recorded here because a future
reader will reasonably ask given this project's standing flat-file preference:
routes/portal.py's Reset/Restore RENAMES the whole registry store directory away
and installs a staged replacement. An enrolment living there would be destroyed
by a project-data reset, silently disconnecting a working agent in a way that
looks from the outside like the NAS itself had failed. This row also belongs
beside users, password_reset_tokens, verification_access_tokens and
diagnostic_reports - the operator-scoped neighbours it shares a lifecycle with.

`project_id` is a plain indexed string rather than a foreign key: projects live
in the flat-JSON store and have no table to reference, exactly as
ProjectWorkspace.owner already does.

Only `token_hash` is stored. There is no column here that can hold a raw token
or a NAS credential, which is the point rather than an omission.

Revision ID: b41ce7a9d305
Revises: a3f1c07d92b4
Create Date: 2026-08-27 14:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b41ce7a9d305'
down_revision = 'a3f1c07d92b4'
branch_labels = None
depends_on = None


def upgrade():
    # Shaped to match db.create_all()'s output EXACTLY, following
    # d67fbff1ba5e's precedent: primary_key on the column rather than a
    # PrimaryKeyConstraint, and NO sa.UniqueConstraint - `unique=True` on a
    # model Column renders as a unique INDEX, not a table-level constraint.
    # Emitting both made the two schemas differ and was caught by
    # tests/test_flask_migrate_baseline.py, which compares a migrated database
    # against a created_all one precisely so this cannot drift.
    op.create_table(
        "storage_agent_enrolments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.String(length=255), nullable=False),
        sa.Column("agent_label", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by", sa.String(length=255), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_storage_agent_enrolments_project_id",
                    "storage_agent_enrolments", ["project_id"])
    op.create_index("ix_storage_agent_enrolments_token_hash",
                    "storage_agent_enrolments", ["token_hash"], unique=True)


def downgrade():
    op.drop_index("ix_storage_agent_enrolments_token_hash",
                  table_name="storage_agent_enrolments")
    op.drop_index("ix_storage_agent_enrolments_project_id",
                  table_name="storage_agent_enrolments")
    op.drop_table("storage_agent_enrolments")
