"""diagnostic reports

CLAUDE-DIAGNOSTIC-BRIDGE-01: models.DiagnosticReport - a live product problem
captured in the application that produced it, for a development agent to
investigate later.

Hand-written for the same reason the two revisions before it were: app.py's
_register_database() always runs db.create_all() first, so autogenerate never
sees a diff to work from (migrations/README explains this in full).

WHY THE DATABASE AND NOT THE FLAT-JSON STORE, recorded here because a future
reader will reasonably ask given this project's standing flat-file preference:
routes/portal.py's Reset/Restore RENAMES the whole registry store directory away
and installs a staged replacement, so anything living there is wholesale
replaced by a project-data reset. A diagnostic about the APPLICATION must not
die because somebody reset a PROJECT. tools/dependency_fit.py warns on any new
database use and asks for exactly this justification; nothing new is being added
here in any case - this row sits beside users, password_reset_tokens and
verification_access_tokens, which are already the operator-scoped neighbours it
belongs with.

Revision ID: a3f1c07d92b4
Revises: d67fbff1ba5e
Create Date: 2026-08-25 11:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f1c07d92b4'
down_revision = 'd67fbff1ba5e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "diagnostic_reports",
        sa.Column("id", sa.Integer(), nullable=False),

        # What the Product Owner reported.
        sa.Column("reported_by", sa.String(length=120), nullable=False),
        sa.Column("reported_at", sa.DateTime(), nullable=False),
        sa.Column("summary", sa.String(length=300), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),

        # What the application already knew, so nobody retypes it. Identifiers
        # rather than content - an investigator reads the real material from the
        # project; this table does not hold a copy of it.
        sa.Column("surface", sa.String(length=300), nullable=True),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("case_id", sa.String(length=64), nullable=True),
        sa.Column("build_sha", sa.String(length=64), nullable=True),
        sa.Column("static_version", sa.String(length=32), nullable=True),
        sa.Column("trace", sa.Text(), nullable=True),

        # What the investigation concluded.
        # No server_default: models.DiagnosticReport.status uses a PYTHON-side
        # default, and tests/test_flask_migrate_baseline.py asserts this
        # migration's DDL matches db.create_all()'s exactly. A server_default
        # here would be a real schema divergence, not a harmless extra.
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("findings", sa.Text(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("affected", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("commit_status", sa.Text(), nullable=True),
        sa.Column("uncertainty", sa.Text(), nullable=True),
        sa.Column("investigated_at", sa.DateTime(), nullable=True),

        # Notification, a separate act again.
        sa.Column("emailed_at", sa.DateTime(), nullable=True),

        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_diagnostic_reports_project_id"),
                    "diagnostic_reports", ["project_id"], unique=False)
    op.create_index(op.f("ix_diagnostic_reports_status"),
                    "diagnostic_reports", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_diagnostic_reports_status"), table_name="diagnostic_reports")
    op.drop_index(op.f("ix_diagnostic_reports_project_id"), table_name="diagnostic_reports")
    op.drop_table("diagnostic_reports")
