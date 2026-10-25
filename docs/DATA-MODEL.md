# 数据模型设计

> 目标：**对外可读、对内不可猜**。重要实体用 UUIDv7 做主键，其余表保持自增；对外只暴露一个 9 位数字编号。

## 1. 主键策略

| 表 | 主键 | 类型 | 说明 |
| --- | --- | --- | --- |
| `account`（重要） | `id` | **UUIDv7** | 不对外暴露；时间有序，写入时索引局部性好；不可枚举 |
| `checkin_setting` | `id` | bigint 自增 | 每账户一行，无外部引用 |
| `checkin_record` | `id` | bigint 自增 | 量大、无需外泄 |
| `guardian` | `id` | bigint 自增 | 仅账户内可见 |
| `safety_alert` | `id` | bigint 自增 | 仅内部引用 |
| `notification_record` | `id` | bigint 自增 | 仅内部引用 |

**为什么只给 `account` 用 UUIDv7**：它是唯一需要跨系统、跨设备引用且不能泄露规模与顺序的实体。
其余表都是账户内部数据，自增主键更省空间、索引更小、调试更方便。

**为什么是 UUIDv7 而不是 UUIDv4**：v7 前 48 位是毫秒时间戳，按时间单调递增，
插入时新行总落在 B 树右端，避免 v4 随机主键造成的页分裂与缓存抖动；
同时保留 74 位随机性，不可枚举。Python 3.13 尚未内置 `uuid7()`，
实现见 `app/core/ids.py`（同一毫秒内用 12 位计数器保证严格递增）。

## 2. 对外标识：9 位数字

```text
凭证 = zm_<9位数字账户编号>.<secret>
例：  zm_481920735.xY3k...
```

| 属性 | 值 |
| --- | --- |
| 范围 | `100_000_000` – `999_999_999`（9 亿个） |
| 形式 | 纯数字，首位非 0（不会被误读成少一位/丢前导零） |
| 唯一性 | 唯一索引 `ix_account_public_id`（建表时 `unique=True`） |
| 生成 | `secrets.randbelow` 均匀随机，**非自增**，不泄露注册顺序与规模 |
| 碰撞处理 | 先查一遍 + 唯一索引兜底 + `IntegrityError` 换号重试（最多 8 次，见 `account_service._allocate_public_id`） |

为什么不用自增数字：自增 ID 会泄露"一共有多少用户"，也能被顺次遍历；
9 位随机数字在保持可口述的同时避免了这两个问题。

碰撞概率（生日问题）：1 万账户时约 0.006%，10 万时约 0.55%，重试机制足以消化。

## 3. 表关系

```text
account (1) ──< checkin_setting      (唯一约束 account_id)
          ├──< checkin_record        (唯一约束 account_id + idempotency_key)
          ├──< guardian              (唯一约束 account_id + email)
          └──< safety_alert          (唯一约束 account_id + due_at)
                    └──< notification_record  (唯一 dedupe_key)
guardian  ──< notification_record    (guardian_id，删除时 SET NULL，保留发信快照)
```

外键统一 `account_id` 为 UUID，随主键类型走；`ondelete` 只在 `notification_record.guardian_id` 上使用 `SET NULL`，
保证删除守护人后历史发信记录仍然可查。

## 4. 关键索引

| 索引 | 表 | 用途 |
| --- | --- | --- |
| `ix_account_public_id` (unique) | account | 凭证定位账户 |
| `ix_account_init_key` (unique) | account | 初始化幂等 |
| `uq_checkin_account_key` | checkin_record | 同一 requestId 不重复落库 |
| `ix_checkin_account_time` | checkin_record | 取账户最近一次确认 |
| `ix_checkin_record_checked_in_at` | checkin_record | 历史倒序分页 |
| `uq_guardian_account_email` | guardian | 邮箱去重 + 上限校验 |
| `uq_alert_account_due` | safety_alert | 同一到期时间只建一条事件 |
| `ix_alert_status_triggered` | safety_alert | 调度扫描 |
| `uq_notification_dedupe` | notification_record | 事件×守护人×渠道只发一封 |
| `ix_notification_status_next` | notification_record | 派发队列（status, next_attempt_at） |

## 5. 迁移说明

- 迁移文件：`alembic/versions/3d9c1a7f5b20_uuid7_account_ids.py`
- 做了什么：`account.id` int → UUIDv7、`public_id` 12 位 base62 → 9 位数字、5 张子表 `account_id` int → UUID
- 方式：整表重建（建 `*_v2` → 拷数据 → 删旧表 → 改名 → 还原约束名 → 重建索引），
  **保留现有数据**，PostgreSQL 与 SQLite 都已实测
- 副作用：旧账户的主键与编号被替换，**旧客户端凭证失效**（客户端收到 401 后会重建账户）；
  旧账户关联的守护人/确认记录/事件全部保留
- 可回滚：`alembic downgrade 76baff02eb9e` 会重建整数主键（编号重新生成为 16 位随机串）

验证记录：

```
PostgreSQL 16：2 账户 / 3 守护人 / 3 确认 / 1 事件 / 2 通知 → 迁移后数量一致，外键零孤儿，
               id 形如 01a17366-d2ff-7000-...（version=7），public_id 为 9 位数字，
               约束名恢复为 account_pkey / checkin_record_account_id_fkey / uq_*，
               自增序列已推进到 max(id)+1
SQLite：同样升级成功，主键以 32 位十六进制存储（SQLAlchemy Uuid 的 SQLite 表示）
```
