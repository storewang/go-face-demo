"""v2.1.0 initial schema: users, attendance_logs, devices, system_config

Revision ID: 0001
Revises: -
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === users ===
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("face_encoding_path", sa.String(255), nullable=True),
        sa.Column("face_image_path", sa.String(255), nullable=True),
        sa.Column("status", sa.Integer(), server_default="1", nullable=True),
        sa.Column("role", sa.String(20), server_default="employee", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_employee_id", "users", ["employee_id"], unique=True)

    # === attendance_logs ===
    op.create_table(
        "attendance_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("employee_id", sa.String(50), nullable=True),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("action_type", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("snapshot_path", sa.String(255), nullable=True),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attendance_logs_id", "attendance_logs", ["id"])
    op.create_index("ix_attendance_logs_user_id", "attendance_logs", ["user_id"])
    op.create_index("ix_attendance_logs_device_id", "attendance_logs", ["device_id"])
    op.create_index(
        "ix_attendance_logs_employee_id", "attendance_logs", ["employee_id"]
    )
    op.create_index("ix_attendance_logs_created_at", "attendance_logs", ["created_at"])

    # === devices ===
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("status", sa.Integer(), server_default="1", nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_devices_device_code", "devices", ["device_code"], unique=True)

    # === system_config ===
    op.create_table(
        "system_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("config_key", sa.String(100), nullable=False),
        sa.Column("config_value", sa.Text(), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_system_config_config_key", "system_config", ["config_key"], unique=True
    )


def downgrade() -> None:
    op.drop_table("system_config")
    op.drop_table("devices")
    op.drop_table("attendance_logs")
    op.drop_table("users")
