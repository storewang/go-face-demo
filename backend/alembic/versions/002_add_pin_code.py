"""Add pin_code column to users table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("users", sa.Column("pin_code", sa.String(255), nullable=True, comment="PIN码bcrypt哈希"))

def downgrade() -> None:
    op.drop_column("users", "pin_code")
