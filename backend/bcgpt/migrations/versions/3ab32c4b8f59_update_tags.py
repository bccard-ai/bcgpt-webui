"""Update tags — change primary key to composite (id, user_id).

Revision ID: 3ab32c4b8f59
Revises: 1af9b942657b
Create Date: 2024-10-09 21:02:35.241684

Drops the single-column primary key on ``tag.id`` and replaces it with
a composite primary key on ``(id, user_id)``, then removes the now-
redundant ``uq_id_user_id`` unique constraint.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.sql import column, select, table, update

revision = "3ab32c4b8f59"
down_revision = "1af9b942657b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Replace the tag table PK with a composite key on (id, user_id)."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    existing_pk = inspector.get_pk_constraint("tag")
    unique_constraints = inspector.get_unique_constraints("tag")
    existing_indexes = inspector.get_indexes("tag")

    print(f"Primary Key: {existing_pk}")
    print(f"Unique Constraints: {unique_constraints}")
    print(f"Indexes: {existing_indexes}")

    with op.batch_alter_table("tag", schema=None) as batch_op:
        # Drop the old single-column primary key.
        if existing_pk and existing_pk.get("constrained_columns"):
            pk_name = existing_pk.get("name")
            if pk_name:
                print(f"Dropping primary key constraint: {pk_name}")
                batch_op.drop_constraint(pk_name, type_="primary")

        # Create the new composite primary key.
        print("Creating new primary key with 'id' and 'user_id'.")
        batch_op.create_primary_key("pk_id_user_id", ["id", "user_id"])

        # Drop unique constraints that overlap with the new PK.
        for constraint in unique_constraints:
            if constraint["name"] == "uq_id_user_id":
                print(f"Dropping unique constraint: {constraint['name']}")
                batch_op.drop_constraint(constraint["name"], type_="unique")

        for index in existing_indexes:
            if index["unique"]:
                if not any(
                    constraint["name"] == index["name"]
                    for constraint in unique_constraints
                ):
                    print(f"Dropping unique index: {index['name']}")
                    batch_op.drop_index(index["name"])


def downgrade() -> None:
    """Restore the original single-column primary key on tag.id."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    current_pk = inspector.get_pk_constraint("tag")

    with op.batch_alter_table("tag", schema=None) as batch_op:
        if current_pk and "pk_id_user_id" == current_pk.get("name"):
            batch_op.drop_constraint("pk_id_user_id", type_="primary")

        batch_op.create_primary_key("pk_id", ["id"])
        batch_op.create_unique_constraint("uq_id_user_id", ["id", "user_id"])
