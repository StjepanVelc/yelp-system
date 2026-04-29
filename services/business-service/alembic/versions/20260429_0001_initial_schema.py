"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "businesses",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("postal_code", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("stars", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("is_open", sa.Boolean(), nullable=True),
        sa.Column("categories", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_businesses_city", "businesses", ["city"])
    op.create_index("ix_businesses_state", "businesses", ["state"])
    op.create_index("ix_businesses_stars", "businesses", ["stars"])
    op.create_index("ix_businesses_city_stars", "businesses", ["city", "stars"])
    op.create_index("ix_businesses_is_open", "businesses", ["is_open"])

    op.create_table(
        "reviews",
        sa.Column("review_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("business_id", sa.String(), nullable=True),
        sa.Column("stars", sa.Float(), nullable=True),
        sa.Column("useful", sa.Integer(), nullable=True),
        sa.Column("funny", sa.Integer(), nullable=True),
        sa.Column("cool", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("date", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("review_id"),
    )
    op.create_index("ix_reviews_business_id", "reviews", ["business_id"])
    op.create_index("ix_reviews_user_id", "reviews", ["user_id"])
    op.create_index("ix_reviews_stars", "reviews", ["stars"])
    op.create_index("ix_reviews_business_stars", "reviews", ["business_id", "stars"])
    op.create_index("ix_reviews_date", "reviews", ["date"])

    op.create_table(
        "users",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("yelping_since", sa.String(), nullable=True),
        sa.Column("useful", sa.Integer(), nullable=True),
        sa.Column("funny", sa.Integer(), nullable=True),
        sa.Column("cool", sa.Integer(), nullable=True),
        sa.Column("fans", sa.Integer(), nullable=True),
        sa.Column("average_stars", sa.Float(), nullable=True),
        sa.Column("elite", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_users_name", "users", ["name"])
    op.create_index("ix_users_average_stars", "users", ["average_stars"])
    op.create_index("ix_users_fans", "users", ["fans"])

    op.create_table(
        "tips",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("business_id", sa.String(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("date", sa.String(), nullable=True),
        sa.Column("compliment_count", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tips_business_id", "tips", ["business_id"])
    op.create_index("ix_tips_user_id", "tips", ["user_id"])
    op.create_index("ix_tips_date", "tips", ["date"])

    op.create_table(
        "checkins",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("business_id", sa.String(), nullable=True),
        sa.Column("date", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_checkins_business_id", "checkins", ["business_id"])


def downgrade() -> None:
    op.drop_index("ix_checkins_business_id", table_name="checkins")
    op.drop_table("checkins")

    op.drop_index("ix_tips_date", table_name="tips")
    op.drop_index("ix_tips_user_id", table_name="tips")
    op.drop_index("ix_tips_business_id", table_name="tips")
    op.drop_table("tips")

    op.drop_index("ix_users_fans", table_name="users")
    op.drop_index("ix_users_average_stars", table_name="users")
    op.drop_index("ix_users_name", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_reviews_date", table_name="reviews")
    op.drop_index("ix_reviews_business_stars", table_name="reviews")
    op.drop_index("ix_reviews_stars", table_name="reviews")
    op.drop_index("ix_reviews_user_id", table_name="reviews")
    op.drop_index("ix_reviews_business_id", table_name="reviews")
    op.drop_table("reviews")

    op.drop_index("ix_businesses_is_open", table_name="businesses")
    op.drop_index("ix_businesses_city_stars", table_name="businesses")
    op.drop_index("ix_businesses_stars", table_name="businesses")
    op.drop_index("ix_businesses_state", table_name="businesses")
    op.drop_index("ix_businesses_city", table_name="businesses")
    op.drop_table("businesses")
