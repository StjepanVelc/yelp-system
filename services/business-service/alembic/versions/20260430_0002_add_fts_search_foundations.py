"""add fts search foundations

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-30

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (
            setweight(to_tsvector('simple', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('simple', coalesce(categories, '')), 'B') ||
            setweight(to_tsvector('simple', coalesce(city, '')), 'C') ||
            setweight(to_tsvector('simple', coalesce(state, '')), 'D')
        ) STORED
        """
    )

    op.execute(
        "CREATE INDEX ix_businesses_search_vector ON businesses USING GIN (search_vector)"
    )
    op.execute(
        "CREATE INDEX ix_businesses_name_trgm ON businesses USING GIN (name gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_businesses_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_businesses_search_vector")
    op.execute("ALTER TABLE businesses DROP COLUMN IF EXISTS search_vector")
