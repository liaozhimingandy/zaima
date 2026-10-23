# 在吗 · V1

> 每天点一下，让有人知道你还在。

一个「安全确认」小工具：你设置一个确认周期（每天 / 每 2 天 / 每 3 天 / 每 7 天），到点打开应用点一下「我在」。
如果长时间没点，系统会在本地分阶段提醒你；超过阈值后给你的**守护人**发一封**中性措辞**的邮件，提示对方主动联系你。

> 这不是紧急救援服务。超时未确认**不等于**发生事故或死亡，产品文案与邮件文案都严格遵守这一点。

---

## 当前状态（本次交付）

| 项目 | 结果 |
| --- | --- |
| 后端单元/接口测试 | **71 / 71 通过**（SQLite 与 PostgreSQL 各完整跑一遍） |
| 数据库迁移 | `alembic upgrade head` / `downgrade base` 往返验证通过 |
| 前端类型检查 | `vue-tsc --noEmit` 0 error |
| 前端构建 | H5 / 微信小程序 / 支付宝小程序 / App 资源 **均构建成功** |
| 端到端联调 | 真实 PostgreSQL + 真实 HTTP 服务完成「确认 → 超时 → 异常事件 → 邮件 → 恢复」闭环 |
| 未完成项 | 见 [docs/LIMITATIONS.md](docs/LIMITATIONS.md)（含真机与真实 SMTP 未验证项） |

---

## 技术栈

- 前端：uni-app + Vue 3 + TypeScript + Pinia + SCSS
- 后端：FastAPI + SQLModel + PostgreSQL + Alembic
- 定时任务：进程内 Scheduler + PostgreSQL advisory lock（单实例保护）
- 邮件：SMTP 适配器 + 开发环境模拟适配器（写入本地 `.mailbox` 目录）

## 目录结构

```
.
├── backend/                 FastAPI 服务
│   ├── app/
│   │   ├── api/             路由与依赖（账户 / 确认 / 守护人 / 健康检查 / dev）
│   │   ├── core/            配置、数据库、日志、统一响应、异常、凭证
│   │   ├── models/          SQLModel 数据模型（6 张表）
│   │   ├── schemas/         Pydantic DTO（对外 camelCase）
│   │   ├── services/        业务逻辑（确认、守护人、异常事件、邮件、通知派发）
│   │   ├── main.py          应用入口（含请求追踪中间件）
│   │   └── scheduler.py     定时任务入口
│   ├── alembic/             数据库迁移
│   ├── tests/               pytest 测试（71 例）
│   ├── Dockerfile
│   └── .env.example
├── frontend/                uni-app 客户端
│   ├── src/
│   │   ├── api/             统一 HTTP 封装 + 接口模块 + DTO 类型
│   │   ├── components/      StatusCard / CheckinButton / AppTabBar / StateView / ConfirmDialog / NavBar
│   │   ├── pages/           index（首页）/ history（记录）/ settings（我的）/ guardians/edit（守护人）
│   │   ├── stores/          Pinia：account / checkin / guardian
│   │   ├── utils/           时间、存储、校验、通知适配、布局
│   │   ├── config/env.ts    环境变量与常量
│   │   ├── pages.json / manifest.json / uni.scss
│   ├── .env.development / .env.production
│   └── vite.config.ts
├── docs/                    接口 / 部署 / 测试报告 / 已知限制 / 隐私 / CI-CD
├── .github/workflows/        ci.yml（PR 检查）、release.yml（构建与镜像发布）
├── Dockerfile.app           一体化调试镜像（API + H5 同源，容器启动即可访问）
├── .dockerignore            根上下文构建忽略（node_modules / dist / .env）
├── package.json             根目录快捷脚本（转发到 frontend/）
└── docker-compose.yml       API / 一体化调试容器
```

---

## 快速开始

### 1. 准备 PostgreSQL

任选其一：

```bash
# A. 用 compose 里自带的 db 服务（需 docker-compose.yml 中 db 服务未被注释）
docker compose up -d db

# B. 已有 PostgreSQL（16+），直接建库并把 DATABASE_URL 指过去
docker run -d --name zaima-pg -p 55432:5432 \
  -e POSTGRES_USER=zaima -e POSTGRES_PASSWORD=zaima -e POSTGRES_DB=zaima \
  postgres:16-alpine
```

> `backend/.env` 的 `DATABASE_URL` 需与这里保持一致（默认 `postgresql+psycopg://zaima:zaima@127.0.0.1:55432/zaima`）。

### 2. 启动后端

```bash
cd backend
python -m venv .venv
# Windows Git Bash
./.venv/Scripts/python.exe -m pip install -i https://pypi.org/simple -r requirements-dev.txt
cp .env.example .env          # 按需修改
./.venv/Scripts/alembic.exe upgrade head
./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

- API 文档：<http://127.0.0.1:8010/docs>
- 健康检查：<http://127.0.0.1:8010/api/health>

### 3. 启动前端

```bash
cd frontend
npm install --registry=https://registry.npmjs.org   # 默认镜像源缺少个别版本时使用官方源
npm run dev:h5                                     # http://127.0.0.1:5173
```

其他平台：

```bash
npm run dev:mp-weixin     # 微信开发者工具导入 dist/dev/mp-weixin
npm run dev:mp-alipay     # 支付宝开发者工具导入 dist/dev/mp-alipay
npm run dev:app           # HBuilderX 导入 dist/dev/app
npm run build:h5          # 生产构建
```

### 4. 镜像一览（两个镜像，用途不同）

| 镜像 | 构建文件 | 内容 | 体积 | 用途 |
| --- | --- | --- | --- | --- |
| **API 服务端** | `backend/Dockerfile` | 只有 Python 运行时 + API，**不含任何前端文件** | **81 MB** | 生产部署 |
| **调试镜像** | `Dockerfile.app` | API + H5 同源，容器启动即可在浏览器打开页面 | **82 MB** | 排查问题 / 演示 |

两者共用同一份 `requirements.txt`，体积压缩手段：alpine 基础镜像、不装 `uvicorn[standard]` 的 uvloop/watchfiles/websockets、
`pip --no-compile`、装完卸载 pip/setuptools/wheel。原来基于 `python:3.13-slim` 时两者都是 209 MB。

`docker-compose.yml` 里两个服务正好对应这两种镜像：

| 服务 | 镜像 | 端口 | 说明 |
| --- | --- | --- | --- |
| `api` | `zaima-api:local`（`backend/Dockerfile`） | `127.0.0.1:8099` | 生产形态，`/` 只返回 JSON，`/app/static` 不存在 |
| `app` | `zaima-app:local`（`Dockerfile.app`） | `127.0.0.1:8098` | 测试形态，`/` 直接打开 H5 |

### 5. 一步启动调试镜像（排查问题 / 演示用）

不需要装 Node、Python、数据库：镜像内已包含 API + H5，**容器起来就能在浏览器看到页面**。

```bash
docker compose up -d --build app
# 打开 http://localhost:8098/
```

等价的手动方式：

```bash
docker build -f Dockerfile.app -t zaima-app:local .
docker run --rm -p 8098:8000 zaima-app:local
```

镜像默认值（**仅用于调试，不要用于生产**）：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `dev` | 开放 `/docs`、`/api/dev/*`、`X-Debug-Now` 时间模拟 |
| `DATABASE_URL` | `sqlite+pysqlite:////data/zaima.db` | 免装数据库，`/data` 已声明为 volume |
| `AUTO_CREATE_TABLES` | `true` | 首次启动自动建表 |
| `EMAIL_ADAPTER` | `mock` | 邮件写到 `/data/mailbox/*.eml`，不会真发 |
| `STATIC_DIR` | `/app/static` | H5 构建产物目录，由后端同端口托管（**仅 `APP_ENV=dev` 生效**） |

页面访问收窄了范围，避免被人随手打开：

- **只有 `APP_ENV=dev` 才托管前端**；把镜像改成 `APP_ENV=prod` 后，`/` 只返回一行 JSON API 信息，`/assets/*`、`/index.html` 全部 404。
- **只开放 `/` 与 `/assets/*`**：不挂载整目录、不开启目录列表，`/index.html`、`/pages/...`、`/app/main.py` 一律 404。
- compose 中端口只绑回环：`127.0.0.1:8098:8000`，同一局域网的其他机器无法访问。
- 可选口令（默认关闭）：设置 `STATIC_ACCESS_KEY=xxx` 后，必须用 `http://localhost:8098/?k=xxx` 打开，校验通过写 Cookie 并跳回干净 URL；静态资源同样要求 Cookie。

排查技巧：

```bash
# 一条命令跑完「超时未确认 → 给守护人发邮件」全流程（不用真等 24 小时）
bash scripts/dev-mail-test.sh
# 指定地址 / 收件人 / 容器名
bash scripts/dev-mail-test.sh http://127.0.0.1:8080
GUARDIAN_EMAIL=me@example.com CONTAINER=dev-zaima-app-01 bash scripts/dev-mail-test.sh

# 手动模拟时间推进，触发提醒/异常事件（需先有账户 token）
curl -X POST "http://localhost:8098/api/dev/scheduler/run" \
  -H "Authorization: Bearer <token>" -H "X-Debug-Now: 2026-06-03T00:00:00Z"

# 查看"已发送"的邮件
# ⚠️ Git Bash / MSYS 会把 /data 转成 Windows 路径，必须加 MSYS_NO_PATHCONV=1
MSYS_NO_PATHCONV=1 docker exec dev-zaima-app-01 ls -l /data/mailbox

# 直接查数据库（镜像内没有 sqlite3 CLI，用 Python 标准库）
MSYS_NO_PATHCONV=1 docker exec dev-zaima-app-01 python -c "import sqlite3;print(sqlite3.connect('/data/zaima.db').execute('select count(*) from checkin_record').fetchone())"
```

邮件与调度排查要点：

- `/data/mailbox` 由应用在启动时创建（`EMAIL_ADAPTER=mock` 时）；**没有发过邮件之前也可能为空目录**，属正常。
- 若脚本第 2 步报 `BAD_REQUEST / There was an error parsing the body`：是终端编码问题（Windows 控制台代码页 936 把中文按 GBK 转码，服务端按 UTF-8 解析失败）。脚本已把请求体改成 stdin 管道传递；仍失败时用 `chcp 65001` 或 `LANG=C.UTF-8 bash scripts/dev-mail-test.sh`。
- 邮件任务在 `notification_record` 表里，接口 `GET /api/dev/notifications` 可直接看状态（`pending/sent/failed/cancelled`）与 `lastError`。
- 一次异常事件只会给**事件创建时已存在**的守护人发信；事件创建后再加守护人不会补发。
- 账户点「我在」恢复正常后，未发出的任务会被置为 `cancelled`。

> 生产环境请使用 `backend/Dockerfile`（纯 API 镜像，非 root、无调试接口、不含前端），见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

---

## 核心业务规则

### 时间语义

- 服务端全程使用 **UTC** 存储与比较；只在计算「本地确认时刻」时转换到用户时区（IANA，如 `Asia/Shanghai`）。
- **应确认时间** = 上次确认所在本地日期 + 确认周期天数，取该天设定的本地时刻（默认 08:00），再转 UTC。
- 首次使用以**账户创建时间**为锚点，因此第一次应确认时间总在 24 小时之后，不会刚安装就被判超时。
- 客户端上报的时间只作展示，**服务端时间才是唯一判定依据**（用户改系统时间无效）。

### 阶段状态机（默认规则）

| 阶段 | 时间窗口 | 含义 |
| --- | --- | --- |
| `NORMAL` | `now < due` | 状态正常 |
| `PENDING` | `due ≤ now < due+30min` | 已到确认时间（宽限期） |
| `REMINDING` | `due+30min ≤ now < due+24h` | 提醒阶段，08:30 / 12:00 / 20:00 三次提醒 |
| `ALERT` | `now ≥ due+24h` | 创建异常事件并邮件通知守护人 |

- 提醒偏移可配置（`REMINDER_OFFSETS_MINUTES=30,240,720`），异常阈值可配置（`ALERT_OFFSET_MINUTES=1440`）。
- 任意阶段完成确认 → 立即回到 `NORMAL`，后续提醒全部取消，未发送的邮件任务置为 `cancelled`。
- 关闭提醒（`remindersEnabled=false`）时，到期后保持 `PENDING` 直到异常阈值。

### 幂等与去重（四层）

| 维度 | 机制 |
| --- | --- |
| 账户初始化 | `account.init_key` 唯一索引；重复/并发初始化返回 409 `ACCOUNT_EXISTS`，客户端换 key 重试 |
| 确认记录 | `(account_id, idempotency_key)` 唯一约束；重复 requestId 返回原记录（`duplicated=true`） |
| 异常事件 | `(account_id, due_at)` 唯一约束 + 「单账户仅一条 open 事件」双重保护 |
| 邮件任务 | `notification_record.dedupe_key` 唯一约束（事件+守护人+渠道） |

Scheduler 每轮扫描重复执行不会产生重复事件或重复邮件；进程崩溃后卡在 `sending` 的任务会在 10 分钟后自动重新入队。

---

## 接口一览

统一响应：`{ "code": "OK", "message": "success", "data": ..., "requestId": "..." }`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| POST | `/api/account/init` | 初始化匿名账户，返回访问凭证 |
| GET | `/api/account/me` | 当前账户与设置 |
| GET | `/api/checkin/status` | 当前状态（阶段 / 倒计时 / 提醒进度） |
| POST | `/api/checkin` | 「我在」确认（幂等） |
| GET | `/api/checkin/history` | 确认历史（游标分页） |
| GET | `/api/checkin/settings` | 确认设置 |
| PUT | `/api/checkin/settings` | 修改周期 / 时间 / 时区 |
| GET/POST | `/api/guardians` | 守护人列表 / 新增 |
| PUT/DELETE | `/api/guardians/{id}` | 编辑 / 删除守护人 |
| POST | `/api/dev/scheduler/run` | 手动触发扫描（仅非生产） |
| GET | `/api/dev/notifications` | 查看通知任务（仅非生产） |

详细字段与示例见 [docs/API.md](docs/API.md)。

### 模拟时间推进（联调用）

非生产环境下所有接口都支持 `X-Debug-Now` 请求头：

```bash
curl -X POST http://127.0.0.1:8010/api/dev/scheduler/run \
  -H "Authorization: Bearer <token>" \
  -H "X-Debug-Now: 2026-03-03T00:00:00Z"
```

---

## 测试

```bash
cd backend

# SQLite（默认，最快）
./.venv/Scripts/python.exe -m pytest -q

# PostgreSQL（与生产同构）
TEST_DATABASE_URL="postgresql+psycopg://zaima:zaima@127.0.0.1:55432/zaima_test" \
  ./.venv/Scripts/python.exe -m pytest -q
```

覆盖：确认周期计算、时区与夏令时、重复确认、历史分页、守护人增删改查与上限、越权隔离、状态流转、Scheduler 幂等、异常事件去重、邮件成功/失败重试/上限/中断恢复、凭证失效、响应契约。详见 [docs/TEST-REPORT.md](docs/TEST-REPORT.md)。

---

## CI/CD

| 工作流 | 触发 | 做什么 | 是否推送镜像 |
| --- | --- | --- | --- |
| `.github/workflows/ci.yml` | Pull Request、手动 | 后端测试（sqlite + postgres 双矩阵）、前端类型检查与 H5 构建、Dockerfile 构建与容器冒烟 | 否 |
| `.github/workflows/release.yml` | push `main` / `v*` Tag、手动 | 测试 → 前端三端产物 → 镜像构建 → 条件推送 → GitHub Release → 汇总报告 | 仅 main 与 `v*` Tag |

镜像标签：

| 触发 | 标签 |
| --- | --- |
| `main` | `dev-<7位sha>`、`sha-<完整sha>` |
| `v1.2.3` | `1.2.3`、`sha-<完整sha>`、`latest` |

需在仓库配置 `DOCKERHUB_USERNAME`、`DOCKERHUB_TOKEN`（Secrets）与 `DOCKER_REPOSITORY`（Variables）。
完整说明见 [docs/CI-CD.md](docs/CI-CD.md)：触发矩阵、标签策略、发布手册、安全设计、验证记录。

---

## 文档索引

- [docs/API.md](docs/API.md) — 接口文档
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — 生产部署（Docker、SMTP、HTTPS、迁移、备份）
- [docs/CI-CD.md](docs/CI-CD.md) — GitHub Actions 与 Docker Hub 发布流程、凭据配置、验证记录
- [docs/TEST-REPORT.md](docs/TEST-REPORT.md) — 测试报告与验收结论
- [docs/LIMITATIONS.md](docs/LIMITATIONS.md) — 已知问题、V1 边界、待验证项
- [docs/PRIVACY.md](docs/PRIVACY.md) — 隐私政策与用户须知

## V1 明确不做

不做注册登录、不做短信验证、不做远程 Push / 小程序订阅消息、不做 SOS / 定位 / 健康数据 / 聊天 / AI / 付费会员，
也不会把「超时未确认」判定为死亡。
