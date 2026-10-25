"""account 主键改为 UUIDv7，public_id 改为 9 位数字

Revision ID: 3d9c1a7f5b20
Revises: 76baff02eb9e
Create Date: 2026-10-25 22:10:00

设计变更：
- ``account.id``：integer → UUIDv7（时间有序、不可枚举、不对外暴露）
- ``account.public_id``：12 位 base62 → 9 位数字（方便用户口述/报障），仍是唯一索引
- 5 张子表的 ``account_id``：integer → UUID，跟随主键类型
- 其余表主键保持自增（非重要表，无需全局唯一）

实现方式：整表重建（建 ``*_v2`` → 拷数据 → 删旧表 → 改名 → 重建索引），
对 SQLite 与 PostgreSQL 都适用，且**保留现有数据**。
注意：旧账户的主键与编号会被替换，旧客户端凭证因此失效（401 后客户端会自动重建账户）。
"""

from __future__ import annotations

import secrets
import string
from typing import Any

import sqlalchemy as sa
from alembic import op

import app.models.base
from app.core.ids import new_public_id, uuid7

revision: str = "3d9c1a7f5b20"
down_revision: str | None = "76baff02eb9e"
branch_labels = None
depends_on = None

TS = app.models.base.UTCDateTime(timezone=True)

# 外键依赖顺序：父表在前
TABLES: tuple[str, ...] = (
    "account",
    "checkin_setting",
    "checkin_record",
    "guardian",
    "safety_alert",
    "notification_record",
)
CHILD_TABLES: tuple[str, ...] = TABLES[1:]


def _spec(id_type: sa.types.TypeEngine, public_id_len: int) -> dict[str, list[tuple[str, Any, bool]]]:
    """按目标主键类型给出每张表的列定义（DDL 与数据拷贝共用）。

    三元组为 (列名, 类型, 是否可空)，与模型定义保持一致。
    """
    return {
        "account": [
            ("created_at", TS, False),
            ("updated_at", TS, False),
            ("id", id_type, False),
            ("public_id", sa.String(public_id_len), False),
            ("secret_hash", sa.String(64), False),
            ("init_key", sa.String(64), True),
            ("platform", sa.String(32), False),
            ("app_version", sa.String(32), True),
            ("status", sa.String(16), False),
        ],
        "checkin_setting": [
            ("created_at", TS, False),
            ("updated_at", TS, False),
            ("id", sa.Integer(), False),
            ("account_id", id_type, False),
            ("period_days", sa.Integer(), False),
            ("checkin_time_local", sa.String(5), False),
            ("timezone", sa.String(64), False),
            ("reminder_offsets", sa.JSON(), False),
            ("alert_offset_minutes", sa.Integer(), False),
            ("reminders_enabled", sa.Boolean(), False),
        ],
        "checkin_record": [
            ("created_at", TS, False),
            ("updated_at", TS, False),
            ("id", sa.Integer(), False),
            ("account_id", id_type, False),
            ("checked_in_at", TS, False),
            ("client_time", TS, True),
            ("due_at", TS, True),
            ("idempotency_key", sa.String(64), False),
            ("source", sa.String(16), False),
            ("note", sa.String(200), True),
        ],
        "guardian": [
            ("created_at", TS, False),
            ("updated_at", TS, False),
            ("id", sa.Integer(), False),
            ("account_id", id_type, False),
            ("name", sa.String(32), False),
            ("email", sa.String(254), False),
            ("relation", sa.String(16), True),
            ("sort_order", sa.Integer(), False),
        ],
        "safety_alert": [
            ("created_at", TS, False),
            ("updated_at", TS, False),
            ("id", sa.Integer(), False),
            ("account_id", id_type, False),
            ("due_at", TS, False),
            ("triggered_at", TS, False),
            ("status", sa.String(16), False),
            ("resolved_at", TS, True),
            ("resolved_by", sa.String(32), True),
            ("overdue_minutes", sa.Integer(), False),
            ("guardian_count", sa.Integer(), False),
            ("notified_guardian_count", sa.Integer(), False),
        ],
        "notification_record": [
            ("created_at", TS, False),
            ("updated_at", TS, False),
            ("id", sa.Integer(), False),
            ("alert_id", sa.Integer(), False),
            ("account_id", id_type, False),
            ("guardian_id", sa.Integer(), True),
            ("channel", sa.String(16), False),
            ("kind", sa.String(16), False),
            ("recipient_email", sa.String(254), False),
            ("recipient_name", sa.String(32), False),
            ("subject", sa.String(200), False),
            ("dedupe_key", sa.String(128), False),
            ("status", sa.String(16), False),
            ("attempts", sa.Integer(), False),
            ("max_attempts", sa.Integer(), False),
            ("next_attempt_at", TS, False),
            ("last_attempt_at", TS, True),
            ("sent_at", TS, True),
            ("last_error", sa.String(500), True),
            ("simulated", sa.Boolean(), False),
        ],
    }


def _create_tables(spec: dict[str, list[tuple[str, Any]]], *, suffix: str, fk_account: str) -> None:
    """按 spec 建一套表；``fk_account`` 是父表在库中的实际名字。"""
    def name(base: str) -> str:
        return f"{base}{suffix}"

    def cols(base: str) -> list[sa.Column]:
        return [sa.Column(n, t, nullable=nullable) for n, t, nullable in spec[base]]

    op.create_table(
        name("account"),
        *cols("account"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        name("checkin_setting"),
        *cols("checkin_setting"),
        sa.ForeignKeyConstraint(["account_id"], [f"{fk_account}.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", name=f"uq_setting_account{suffix}"),
    )
    op.create_table(
        name("checkin_record"),
        *cols("checkin_record"),
        sa.ForeignKeyConstraint(["account_id"], [f"{fk_account}.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "idempotency_key", name=f"uq_checkin_account_key{suffix}"),
    )
    op.create_table(
        name("guardian"),
        *cols("guardian"),
        sa.ForeignKeyConstraint(["account_id"], [f"{fk_account}.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "email", name=f"uq_guardian_account_email{suffix}"),
    )
    op.create_table(
        name("safety_alert"),
        *cols("safety_alert"),
        sa.ForeignKeyConstraint(["account_id"], [f"{fk_account}.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "due_at", name=f"uq_alert_account_due{suffix}"),
    )
    op.create_table(
        name("notification_record"),
        *cols("notification_record"),
        sa.ForeignKeyConstraint(["account_id"], [f"{fk_account}.id"]),
        sa.ForeignKeyConstraint(["alert_id"], [f"{name('safety_alert')}.id"]),
        sa.ForeignKeyConstraint(["guardian_id"], [f"{name('guardian')}.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name=f"uq_notification_dedupe{suffix}"),
    )


def _create_indexes() -> None:
    op.create_index("ix_account_init_key", "account", ["init_key"], unique=True)
    op.create_index("ix_account_public_id", "account", ["public_id"], unique=True)
    op.create_index("ix_checkin_setting_account_id", "checkin_setting", ["account_id"])
    op.create_index("ix_checkin_record_account_id", "checkin_record", ["account_id"])
    op.create_index("ix_checkin_record_checked_in_at", "checkin_record", ["checked_in_at"])
    op.create_index("ix_checkin_account_time", "checkin_record", ["account_id", "checked_in_at"])
    op.create_index("ix_guardian_account_id", "guardian", ["account_id"])
    op.create_index("ix_guardian_email", "guardian", ["email"])
    op.create_index("ix_safety_alert_account_id", "safety_alert", ["account_id"])
    op.create_index("ix_alert_status_triggered", "safety_alert", ["status", "triggered_at"])
    op.create_index("ix_notification_record_account_id", "notification_record", ["account_id"])
    op.create_index("ix_notification_record_alert_id", "notification_record", ["alert_id"])
    op.create_index("ix_notification_record_guardian_id", "notification_record", ["guardian_id"])
    op.create_index("ix_notification_status_next", "notification_record", ["status", "next_attempt_at"])


def _read(bind: sa.engine.Connection) -> dict[str, list[dict[str, Any]]]:
    """反射旧表并读出全部数据（时间列由方言解析成 datetime）。"""
    meta = sa.MetaData()
    tables = {name: sa.Table(name, meta, autoload_with=bind) for name in TABLES}
    return {
        name: [dict(row) for row in bind.execute(sa.select(tables[name])).mappings().all()]
        for name in TABLES
    }


def _write(bind: sa.engine.Connection, table_name: str,
           columns: list[tuple[str, Any, bool]], rows: list[dict[str, Any]]) -> None:
    """用 Core insert 写入，让 UTCDateTime / JSON / Uuid 的类型处理器按方言生效。"""
    if not rows:
        return
    table = sa.Table(table_name, sa.MetaData(), *[sa.Column(n, t) for n, t, _ in columns])
    bind.execute(table.insert(), rows)


def _reset_sequences(bind: sa.engine.Connection) -> None:
    """PG 下把自增序列推到 max(id)，避免重建后主键冲突。"""
    if bind.dialect.name != "postgresql":
        return
    for table in CHILD_TABLES:
        bind.execute(
            sa.text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)"
            )
        )


def _drop_tables(names: tuple[str, ...] = TABLES) -> None:
    # 先删子表，避免外键约束报错
    for table in reversed(names):
        op.drop_table(table)


def _rename(suffix: str) -> None:
    for table in TABLES:  # 父表先改名，子表的外键引用会跟着更新
        op.rename_table(f"{table}{suffix}", table)


UNIQUE_CONSTRAINTS: tuple[tuple[str, str], ...] = (
    ("checkin_setting", "uq_setting_account"),
    ("checkin_record", "uq_checkin_account_key"),
    ("guardian", "uq_guardian_account_email"),
    ("safety_alert", "uq_alert_account_due"),
    ("notification_record", "uq_notification_dedupe"),
)


def _rename_constraints(suffix: str) -> None:
    """把建表时的临时约束名还原成规范名（PostgreSQL 专用）。

    建表阶段必须用临时名，否则与旧表上的同名唯一约束（底层索引同名）冲突。
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite 不追踪约束名，无需处理

    def rename(table: str, old: str, new: str) -> None:
        bind.execute(sa.text(f'ALTER TABLE {table} RENAME CONSTRAINT "{old}" TO "{new}"'))

    for table in TABLES:
        rename(table, f"{table}{suffix}_pkey", f"{table}_pkey")

    for table, canonical in UNIQUE_CONSTRAINTS:
        rename(table, f"{canonical}{suffix}", canonical)

    fk_columns = {
        "checkin_setting": ["account_id"],
        "checkin_record": ["account_id"],
        "guardian": ["account_id"],
        "safety_alert": ["account_id"],
        "notification_record": ["account_id", "alert_id", "guardian_id"],
    }
    for table, columns in fk_columns.items():
        for column in columns:
            rename(table, f"{table}{suffix}_{column}_fkey", f"{table}_{column}_fkey")


def upgrade() -> None:
    bind = op.get_bind()
    old = _read(bind)

    # 1) 先生成新的 UUID 与 9 位编号
    account_map: dict[int, Any] = {}
    new_accounts: list[dict[str, Any]] = []
    used_public_ids: set[str] = set()
    for row in sorted(old["account"], key=lambda r: r["id"]):
        new_id = uuid7()
        public_id = new_public_id()
        while public_id in used_public_ids:
            public_id = new_public_id()
        used_public_ids.add(public_id)
        account_map[row["id"]] = new_id
        new_accounts.append({**row, "id": new_id, "public_id": public_id})

    new_spec = _spec(sa.Uuid(), 9)

    # 2) 建新表并写入
    _create_tables(new_spec, suffix="_v2", fk_account="account_v2")
    _write(bind, "account_v2", new_spec["account"], new_accounts)

    for table in CHILD_TABLES:
        rows = [{**row, "account_id": account_map[row["account_id"]]}
                for row in old[table] if row["account_id"] in account_map]
        _write(bind, f"{table}_v2", new_spec[table], rows)

    # 3) 删旧表 → 改名 → 重建索引
    _drop_tables()
    _rename("_v2")
    _rename_constraints("_v2")
    _create_indexes()
    _reset_sequences(bind)


def downgrade() -> None:
    bind = op.get_bind()
    old = _read(bind)

    # UUID → 自增整数（按原顺序重新编号）；9 位数字 → 16 位随机串
    account_map: dict[Any, int] = {}
    new_accounts: list[dict[str, Any]] = []
    alphabet = string.ascii_letters + string.digits
    for index, row in enumerate(sorted(old["account"], key=lambda r: str(r["id"])), start=1):
        account_map[row["id"]] = index
        public_id = "".join(secrets.choice(alphabet) for _ in range(16))
        new_accounts.append({**row, "id": index, "public_id": public_id})

    old_spec = _spec(sa.Integer(), 32)

    _create_tables(old_spec, suffix="_v1", fk_account="account_v1")
    _write(bind, "account_v1", old_spec["account"], new_accounts)

    for table in CHILD_TABLES:
        rows = [{**row, "account_id": account_map[row["account_id"]]}
                for row in old[table] if row["account_id"] in account_map]
        _write(bind, f"{table}_v1", old_spec[table], rows)

    _drop_tables()
    _rename("_v1")
    _rename_constraints("_v1")
    _create_indexes()
    _reset_sequences(bind)
