"""project access tokens, architect escalations, trial allowances

CLAUDE-RBAC-TOKENS-01/02 and CLAUDE-TRIAL-SAFE-LANDING-01. Three tables:

  project_access_tokens   which stakeholder may read which discipline of which
                          project, and until when.
  architect_escalations   a question GO could not answer, queued for a human.
  trial_allowances        how much model-backed work a trial project has used.

Hand-written for the same reason every revision before it was: app.py's
_register_database() always runs db.create_all() first, so autogenerate never
sees a diff to work from (migrations/README explains this in full).

WHY THE DATABASE AND NOT THE FLAT-JSON STORE, for all three. routes/portal.py's
Reset/Restore RENAMES the whole registry store directory away and installs a
staged replacement. Each of these would be destroyed by a project-data reset,
and each failure would be silent and bad in a different way: access grants would
vanish (or, worse, a quota would reset and hand out unlimited trial usage to
anyone who noticed); an unanswered question would disappear at exactly the
moment somebody was waiting for a reply. They belong beside users,
password_reset_tokens, verification_access_tokens, diagnostic_reports and
storage_agent_enrolments - the operator-scoped neighbours they share a
lifecycle with.

`project_id` is a plain indexed string rather than a foreign key throughout:
projects live in the flat-JSON store and have no table to reference, exactly as
ProjectWorkspace.owner and storage_agent_enrolments.project_id already do.

Only `token_hash` is stored on project_access_tokens - there is no column here
capable of holding a raw token, which is the point rather than an omission.
`byok_api_key_encrypted` is deliberately NOT here: it lives on the flat-JSON
ProjectWorkspace, is read for presence only, and this migration adds no column
anywhere that could hold a provider credential.

Revision ID: c92d4be13a77
Revises: b41ce7a9d305
Create Date: 2026-08-29 12:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c92d4be13a77'
down_revision = 'b41ce7a9d305'
branch_labels = None
depends_on = None


def upgrade():
    # Shaped to match db.create_all()'s output EXACTLY, following
    # b41ce7a9d305's precedent: primary_key on the column rather than a
    # PrimaryKeyConstraint, and NO sa.UniqueConstraint - `unique=True` on a
    # model Column renders as a unique INDEX, not a table-level constraint.
    # tests/test_flask_migrate_baseline.py compares a migrated database against
    # a created_all one precisely so this cannot drift, and it is what caught
    # these three tables being added to models.py with no revision at all.
    op.create_table(
        "project_access_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("disciplines", sa.String(length=255), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by", sa.String(length=255), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_project_access_tokens_project_id",
                    "project_access_tokens", ["project_id"])
    op.create_index("ix_project_access_tokens_token_hash",
                    "project_access_tokens", ["token_hash"], unique=True)

    op.create_table(
        "architect_escalations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.String(length=255), nullable=False),
        sa.Column("token_id", sa.Integer(),
                  sa.ForeignKey("project_access_tokens.id"), nullable=True),
        sa.Column("asked_by_role", sa.String(length=32), nullable=False),
        sa.Column("sheet_id", sa.String(length=64), nullable=True),
        sa.Column("view_box", sa.String(length=128), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("friction_signal", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_architect_escalations_project_id",
                    "architect_escalations", ["project_id"])
    op.create_index("ix_architect_escalations_token_id",
                    "architect_escalations", ["token_id"])

    op.create_table(
        "trial_allowances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.String(length=255), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.Column("first_used_at", sa.DateTime(), nullable=True),
        sa.Column("exhausted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_trial_allowances_project_id",
                    "trial_allowances", ["project_id"], unique=True)


def downgrade():
    op.drop_index("ix_trial_allowances_project_id",
                  table_name="trial_allowances")
    op.drop_table("trial_allowances")

    # architect_escalations before project_access_tokens: it holds the foreign
    # key, so dropping the parent first would fail wherever FKs are enforced.
    op.drop_index("ix_architect_escalations_token_id",
                  table_name="architect_escalations")
    op.drop_index("ix_architect_escalations_project_id",
                  table_name="architect_escalations")
    op.drop_table("architect_escalations")

    op.drop_index("ix_project_access_tokens_token_hash",
                  table_name="project_access_tokens")
    op.drop_index("ix_project_access_tokens_project_id",
                  table_name="project_access_tokens")
    op.drop_table("project_access_tokens")
