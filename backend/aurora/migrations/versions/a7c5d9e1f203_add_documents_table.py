"""add documents table

Revision ID: a7c5d9e1f203
Revises: ec328ff867b1
Create Date: 2026-08-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7c5d9e1f203"
down_revision: Union[str, None] = "ec328ff867b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_documents_table() -> None:
    op.create_table(
        "documents",
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("snapshot_id", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshots.snapshot_id"]),
        sa.PrimaryKeyConstraint("document_id", "snapshot_id"),
    )


def _documents_schema_differences(inspector, dialect) -> list[str]:
    differences = []
    expected_columns = [
        ("document_id", dialect.type_compiler.process(sa.String()).upper()),
        ("snapshot_id", dialect.type_compiler.process(sa.String()).upper()),
        ("payload", dialect.type_compiler.process(sa.JSON()).upper()),
    ]
    columns = inspector.get_columns("documents")
    actual_names = [column["name"] for column in columns]
    expected_names = [name for name, _type in expected_columns]
    if actual_names != expected_names:
        differences.append(
            f"columns are {actual_names!r}, expected {expected_names!r}"
        )
    for column, (expected_name, expected_type) in zip(columns, expected_columns):
        if column["name"] != expected_name:
            continue
        actual_type = dialect.type_compiler.process(column["type"]).upper()
        if actual_type != expected_type:
            differences.append(
                f"{expected_name} type is {actual_type}, expected {expected_type}"
            )
        if column.get("nullable", True):
            differences.append(f"{expected_name} must be NOT NULL")
        if column.get("default") is not None:
            differences.append(f"{expected_name} must not have a default")

    primary_key = inspector.get_pk_constraint("documents")
    expected_primary_key = ["document_id", "snapshot_id"]
    if primary_key.get("constrained_columns") != expected_primary_key:
        differences.append(
            "primary key is "
            f"{primary_key.get('constrained_columns')!r}, "
            f"expected {expected_primary_key!r}"
        )

    foreign_keys = inspector.get_foreign_keys("documents")
    expected_foreign_key = {
        "constrained_columns": ["snapshot_id"],
        "referred_schema": None,
        "referred_table": "snapshots",
        "referred_columns": ["snapshot_id"],
    }
    if len(foreign_keys) != 1:
        differences.append(
            f"foreign key count is {len(foreign_keys)}, expected 1"
        )
    else:
        foreign_key = foreign_keys[0]
        actual_foreign_key = {
            key: foreign_key.get(key)
            for key in expected_foreign_key
        }
        if actual_foreign_key != expected_foreign_key:
            differences.append(
                f"foreign key is {actual_foreign_key!r}, "
                f"expected {expected_foreign_key!r}"
            )
        if any(value is not None for value in foreign_key.get("options", {}).values()):
            differences.append(
                f"foreign key options must be empty, got {foreign_key['options']!r}"
            )

    for label, constraints in (
        ("unique constraints", inspector.get_unique_constraints("documents")),
        ("check constraints", inspector.get_check_constraints("documents")),
        ("indexes", inspector.get_indexes("documents")),
    ):
        if constraints:
            differences.append(f"unexpected {label}: {constraints!r}")
    return differences


def upgrade() -> None:
    context = op.get_context()
    if context.as_sql:
        _create_documents_table()
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("documents"):
        _create_documents_table()
        return

    differences = _documents_schema_differences(inspector, bind.dialect)
    if differences:
        raise RuntimeError(
            "refusing to adopt incompatible documents table: "
            + "; ".join(differences)
        )


def downgrade() -> None:
    op.drop_table("documents")
