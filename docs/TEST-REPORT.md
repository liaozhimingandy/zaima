# 测试报告（V1）

> 本文所有结果均为实际执行输出，未运行或未通过的项目在最后单独列出，不做"标记通过"。

---

## 1. 环境

| 项目 | 值 |
| --- | --- |
| OS | Windows 11 (win32) |
| Python | 3.13.14（venv：`backend/.venv`） |
| Node.js | 22.22.2 |
| PostgreSQL | 16-alpine（Docker，容器 `zaima-pg`，宿主端口 55432） |
| 后端依赖 | FastAPI 0.115.6 / SQLModel 0.0.22 / SQLAlchemy 2.0.36 / Alembic 1.14.0 |
| 前端依赖 | uni-app 3.0.0-5020620260917001 / Vue 3.4.21 / Vite 5.2.8 |
| 数据通道 | SQLite（默认）与 PostgreSQL（`TEST_DATABASE_URL`）各跑一遍 |

---

## 2. 后端自动化测试

### 2.1 执行命令

```bash
cd backend

# SQLite
./.venv/Scripts/python.exe -m pytest -q

# PostgreSQL
TEST_DATABASE_URL="postgresql+psycopg://zaima:zaima@127.0.0.1:55432/zaima_test" \
  ./.venv/Scripts/python.exe -m pytest -q
```

### 2.2 结果

| 数据库 | 结果 |
| --- | --- |
| SQLite | **71 passed in 5.89s** |
| PostgreSQL 16 | **71 passed in 10.21s** |

> 早期版本曾出现 `starlette.testclient` 的 `anyio` 弃用告警，已在 `pyproject.toml` 中过滤；当前运行无告警输出。

### 2.3 用例分布

| 文件 | 数量 | 覆盖内容 |
| --- | --- | --- |
| `tests/test_schedule.py` | 10 | 应确认时间计算、周期 1/2/3/7、阶段流转（08:00→08:30→12:00→20:00→次日 08:00）、提醒关闭、美东夏令时前进/回退、非法输入、进度边界 |
| `tests/test_account.py` | 7 | 匿名账户创建、凭证格式与熵、重复 init 409、短 initKey 422、`/me`、无效/畸形/错误 secret 凭证 401、跨账户隔离、健康检查 |
| `tests/test_checkin.py` | 15 | 默认状态、确认成功、幂等（重复 requestId 不新增记录）、客户端时间不可信、历史分页（3 页游标）、空状态、非法游标、周期 1/2/3/7 参数化、非法周期/时间/时区、时区切换、5 个时间点的阶段流转 |
| `tests/test_guardians.py` | 8 | 空列表、增删改查、邮箱小写归一、3 位上限、重复邮箱（含大小写）、编辑成重复邮箱、非法邮箱、空姓名、删除不存在 |
| `tests/test_alert_flow.py` | 10 | 阈值前不建事件、提醒阶段不发邮件、事件创建+模拟邮件发送、Scheduler 三次重复执行幂等、确认后恢复、确认取消待发邮件、3 名守护人全部通知、无守护人不通知、账户隔离、账户数超单批上限时全量扫描（键集分页） |
| `tests/test_email.py` | 7 | Mock 适配器落盘 `.eml`、SMTP 未配置立即永久失败、失败两次后成功（退避重试）、超上限失败且不再重试、`sending` 中断恢复、dedupe 去重、生产环境禁止 mock 适配器 |
| `tests/test_contract.py` | 14 | 成功/失败响应信封、`X-Request-ID` 回显、未知路由 404 信封、OpenAPI 可用、确认幂等唯一约束、事件唯一约束、守护人上限配置、非法 `X-Debug-Now` |
| **合计** | **71** | |

### 2.4 数据库迁移

```bash
alembic upgrade head      # OK
alembic downgrade base    # OK
alembic upgrade head      # OK
alembic current           # 76baff02eb9e (head)
```

迁移生成的 6 张表：`account`、`checkin_setting`、`checkin_record`、`guardian`、`safety_alert`、`notification_record`，
包含唯一约束（`account.init_key`、`(account_id, idempotency_key)`、`(account_id, email)`、`(account_id, due_at)`、`dedupe_key`）与复合索引。

---

## 3. 前端验证

### 3.1 类型检查

```bash
cd frontend && npx vue-tsc --noEmit -p tsconfig.json
# 退出码 0，无输出（0 error）
```

### 3.2 多平台构建

| 命令 | 结果 | 产物 |
| --- | --- | --- |
| `npx uni build` | DONE Build complete | `dist/build/h5` |
| `npx uni build -p mp-weixin` | DONE Build complete | `dist/build/mp-weixin` |
| `npx uni build -p mp-alipay` | DONE Build complete | `dist/build/mp-alipay` |
| `npx uni build -p app` | DONE Build complete | `dist/build/app` |

构建期提示「未配置 Appid，uni 统计不可用」——属预期（`manifest.json` 中 appid 为占位符）。

### 3.3 模块编译验证（Vite dev server）

逐个请求页面与组件模块，确认 SFC + SCSS 编译无错误（HTTP 200 且返回编译后 JS）：

| 模块 | 结果 |
| --- | --- |
| `src/pages/index/index.vue` | 200 · 32.8 KB |
| `src/pages/history/index.vue` | 200 · 26.0 KB |
| `src/pages/settings/index.vue` | 200 · 67.9 KB |
| `src/pages/guardians/edit.vue` | 200 · 60.0 KB |
| `StatusCard / CheckinButton / AppTabBar / StateView / ConfirmDialog / NavBar` | 均为 200 |
| `utils/notify.ts`、`stores/account.ts`、`stores/checkin.ts` | 均为 200 |

### 3.4 未执行的前端验证

- 未做浏览器截图/像素级视觉验收（当前环境无法启动无头浏览器）。
- 未在微信开发者工具、支付宝开发者工具、真机中运行。
- 因此**「页面视觉与交互在真机上的最终效果」属于待验证项**，见 `LIMITATIONS.md`。

---

## 4. 端到端联调（真实 PostgreSQL + 真实 HTTP 服务）

服务：`uvicorn app.main:app --host 127.0.0.1 --port 8010`（`APP_ENV=dev`，`EMAIL_ADAPTER=mock`）

### 4.1 完整闭环

| 步骤 | 请求 | 实际结果 |
| --- | --- | --- |
| 1 | `POST /api/account/init` | `201`，返回 `accessToken=zm_gFkRAW8Bv9Pykmg.zO_Ygahk...`、`accountId=gFkRAW8Bv9Pykmg` |
| 2 | `POST /api/guardians` | `201`，`{"id":1,"name":"妈妈","email":"mom.e2e@example.com","relation":"family"}` |
| 3 | `POST /api/checkin`（`X-Debug-Now: 2026-03-01T00:00:00Z`） | `stage=NORMAL`，`last=2026-03-01T00:00:00Z`，`next=2026-03-02T00:00:00Z` |
| 4 | `GET /api/checkin/status`（`2026-03-02T12:00:00Z`） | `stage=REMINDING`，`remindersPassed=3`，`hasOpenAlert=false` |
| 5 | `POST /api/dev/scheduler/run`（`2026-03-03T00:00:00Z`） | `scan.alertsCreated=1`，`scan.notificationsCreated=1`，`dispatch.sent=1`，`dispatch.simulated=1` |
| 6 | 检查 `.mailbox/` | 生成 `20261023062045-76340d18.eml`，主题 `【在吗】你关注的人已超过 24 小时未完成安全确认`，含 text/plain + text/html 双版本 |
| 7 | `POST /api/checkin`（`2026-03-03T01:00:00Z`） | `resolvedAlert=true`，`stage=NORMAL`，`next=2026-03-04T00:00:00Z` |
| 8 | 另一账户：扫描后确认 | 通知任务状态由 `pending` → `cancelled`，`lastError=账户已恢复正常，取消发送` |
| 9 | `GET /api/checkin/history` | `count=2`，`hasMore=false` |

### 4.2 重复扫描幂等

同一 `due_at` 连续三次执行 `POST /api/dev/scheduler/run`：`alertsCreated` 均为 0、`alertsExisting=1`、`notificationsCreated=0`、`dispatch.picked=0`（对应 `test_scheduler_is_idempotent`）。

---

## 5. 需求覆盖矩阵

| 需求域 | 状态 | 证据 |
| --- | --- | --- |
| 匿名账户（无注册/无短信） | 完成 | `test_account.py`，`POST /api/account/init` |
| 应用重启恢复账户 | 完成（前端逻辑） | `stores/account.ts::runBootstrap`，凭证存本地；真机未验证 |
| 服务端生成强随机凭证 | 完成 | `core/security.py`（96bit publicId + 256bit secret，SHA-256 入库） |
| 账户数据隔离 | 完成 | `test_account_data_isolation`、`test_other_account_alert_not_affected` |
| 周期 1/2/3/7 + 默认 08:00 | 完成 | `test_update_period`（参数化 4 例） |
| 时区与夏令时 | 完成 | `test_dst_spring_forward_uses_real_local_time`、`test_dst_fall_back_keeps_local_time` |
| 服务端 UTC 存储 | 完成 | `models/base.py::UTCDateTime` |
| 首页状态/剩余时间/提醒阶段 | 完成 | `GET /api/checkin/status` |
| 「我在」确认 + 反馈 | 完成 | `POST /api/checkin`，前端 `CheckinButton` + toast/modal |
| 重复请求不产生重复记录 | 完成 | `test_duplicate_request_does_not_create_second_record` + DB 唯一约束 |
| 客户端改时间无效 | 完成 | `test_server_time_wins_over_client_time` |
| 确认历史 + 分页 + 空态 | 完成 | `test_history_pagination`、`test_history_empty_state` |
| 守护人 CRUD + 上限 3 + 邮箱校验 | 完成 | `test_guardians.py`（8 例） |
| 越权保护 | 完成 | 跨账户 404（不泄露存在性） |
| Scheduler 扫描 + 四阶段状态机 | 完成 | `test_stage_progression_matches_default_rules`、`test_alert_flow.py` |
| 状态幂等（重复扫描） | 完成 | 唯一约束 + savepoint + `test_scheduler_is_idempotent` |
| 异常事件不重复创建 | 完成 | `test_alert_unique_per_due`、`alertsExisting` 计数 |
| 恢复后不再发旧事件提醒 | 完成 | `test_checkin_cancels_pending_notifications` |
| SMTP + Mock 双适配器 | 完成 | `mail/adapters.py`，`test_mock_sender_writes_eml` |
| 失败重试 + 上限 + 中断恢复 | 完成 | `test_retry_until_success`、`test_max_attempts_marks_failed`、`test_stale_sending_is_recovered` |
| 生产缺配置明确报错 | 完成 | `test_config_missing_is_permanent_failure`、`test_production_requires_smtp_adapter` |
| 多守护人通知 | 完成 | `test_multiple_guardians_all_notified` |
| 统一响应/错误处理/请求追踪 | 完成 | `test_contract.py` |
| 前端四页 + 通用组件 | 完成（构建通过） | `src/pages/*`、`src/components/*` |
| 五平台构建 | 4 平台构建通过；H5 已构建，Android/iOS 为 App 资源（需 HBuilderX 打包） | 见 3.2 |
| 通知能力分层与降级 | 完成（实现） | `utils/notify.ts`：页面内提醒始终可用，系统通知为可选增强 |
| Docker 部署配置 | 完成 | `backend/Dockerfile`、`docker-compose.yml`、健康检查、迁移入口 |
| 部署/接口/隐私/限制文档 | 完成 | `docs/*.md` |

---

## 6. 未通过 / 未执行（如实记录）

| 项目 | 原因 | 影响 |
| --- | --- | --- |
| 真实 SMTP 发信 | 无可用生产邮箱凭据 | 未验证真实投递、垃圾邮件判定、SPF/DKIM |
| 微信/支付宝小程序真机运行 | 无 appid、无开发者工具授权 | 未验证小程序端布局与请求域名限制 |
| iOS/Android 真机 | 需 HBuilderX 云打包证书 | 未验证 App 端表现 |
| 浏览器视觉验收 | 当前环境无法启动无头浏览器 | 未验证像素级布局 |
| 并发压力 / 多实例 | 未做压测 | 未验证高并发下的连接池与锁竞争 |
| 账户删除与数据清理 | V1 未提供接口 | 见 `LIMITATIONS.md` |

---

## 7. 验收结论

- 后端核心业务闭环（账户 → 设置 → 确认 → 超时 → 异常事件 → 邮件 → 恢复）在 SQLite 与 PostgreSQL 上均**全部测试通过**，并在真实服务上完成一次端到端联调。
- 前端类型检查通过，四个平台产物构建成功；页面逻辑与状态流与后端契约一致。
- 剩余风险集中在「真实第三方环境」（SMTP 投递、小程序/App 真机、多实例压测），已在 `LIMITATIONS.md` 逐条列出，不影响 V1 功能闭环的正确性。
- **结论：V1 核心闭环可用，可进入联调验收；上线前必须完成 SMTP 真实发信验证与目标平台真机验证。**
