"""station enrolments

SPIKE / CLAUDE-STATION-01: models.StationEnrolment - a physical surface that
mounts exactly one project, so the working canvas has no switcher to hide.

Hand-written like every revision before it: app.py's _register_database() runs
db.create_all() first, so autogenerate never sees a diff.

Shaped to match db.create_all()'s output EXACTLY, following d67fbff1ba5e and
b41ce7a9d305: primary_key on the column rather than a PrimaryKeyConstraint, plain
op.create_index rather than batch_alter_table, and NO sa.UniqueConstraint -
`unique=True` on a model Column renders as a unique INDEX, not a table-level
constraint. Emitting both is what made b41ce7a9d305 fail
tests/test_flask_migrate_baseline.py, which compares a migrated database against
a created_all one precisely so the two cannot drift.

WHY THE DATABASE. Same reason StorageAgentEnrolment and DiagnosticReport give:
routes/portal.py's Reset/Restore renames the whole registry store directory away,
so anything in the flat-JSON store is wholesale replaced by a project reset. A
station is a piece of hardware in a site office - it must not lose its identity
because somebody reset a project it happened to be showing.

`mounted_project_id` is a plain indexed string, not a foreign key: projects live
in the flat-JSON store and have no table, exactly as ProjectWorkspace.owner
already works. It is nullable because a newly enrolled station is hardware with
no job yet, and it is MUTABLE where token_hash is not - re-pointing a table at
next month's job must not destroy its identity or its companion pairings.

Revision ID: c72da4e1b806
Revises: b41ce7a9d305
Create Date: 2026-08-28 09:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c72da4e1b806'
down_revision = 'b41ce7a9d305'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "station_enrolments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("mounted_project_id", sa.String(length=255), nullable=True),
        sa.Column("mounted_at", sa.DateTime(), nullable=True),
        sa.Column("mounted_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by", sa.String(length=255), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_station_enrolments_token_hash",
                    "station_enrolments", ["token_hash"], unique=True)
    op.create_index("ix_station_enrolments_mounted_project_id",
                    "station_enrolments", ["mounted_project_id"])


def downgrade():
    op.drop_index("ix_station_enrolments_mounted_project_id",
                  table_name="station_enrolments")
    op.drop_index("ix_station_enrolments_token_hash",
                  table_name="station_enrolments")
    op.drop_table("station_enrolments")
