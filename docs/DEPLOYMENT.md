# 生产部署说明

适用于 V1（单实例 API + PostgreSQL）。多实例部署请阅读第 6 节。

---

## 1. 环境要求

| 组件 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.11+ | 镜像使用 `python:3.13-slim` |
| PostgreSQL | 14+ | 推荐 16；需要 `pg_try_advisory_lock` |
| Node.js | 18+ | 仅构建前端时需要 |
| Docker | 24+ | 可选，推荐 |

---

## 2. 关键环境变量

完整清单见 `backend/.env.example`。生产**必须**关注：

| 变量 | 生产建议值 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `prod` | 非 `prod` 才会注册 `/api/dev/*` 与 `X-Debug-Now` |
| `DEBUG` | `false` | |
| `AUTO_CREATE_TABLES` | `false` | 生产必须走 Alembic |
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/zaima` | 使用独立账号，仅授权本库 |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 10 / 20 | 按实例数调整，注意 PG `max_connections` |
| `CORS_ORIGINS` | `https://your-domain.com` | 多个用逗号分隔，**不要用 `*`** |
| `DOCS_ENABLED` | `false`（可选） | 关闭 `/docs` |
| `EMAIL_ADAPTER` | `smtp` | `prod` 下若为 `mock`，`get_sender()` 直接抛错 |
| `SMTP_HOST/PORT/USERNAME/PASSWORD/FROM` | 真实值 | 见第 4 节 |
| `EMAIL_MAX_ATTEMPTS` | 3 | 失败上限 |
| `EMAIL_RETRY_BACKOFF_SECONDS` | 60 | 退避基数（第 n 次失败后等待 `n × base` 秒） |
| `SCHEDULER_ENABLED` | `true`（仅一个实例） | 多实例时见第 6 节 |
| `SCHEDULER_INTERVAL_SECONDS` | 60 | 扫描间隔 |
| `ALLOW_TIME_TRAVEL` | `false` | 关闭时间模拟 |

> 敏感配置只通过环境变量注入，不要提交到仓库。

---

## 3. Docker 部署

```bash
# 1) 准备环境文件（放在 compose 同级目录，命名 .env）
cp backend/.env.example .env
# 编辑 .env：APP_ENV=prod、EMAIL_ADAPTER=smtp、SMTP_*、CORS_ORIGINS、DB 密码等

# 2) 启动
docker compose up -d --build

# 3) 查看状态
docker compose ps
docker compose logs -f api | head -50

# 4) 冒烟
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8000/openapi.json | head -c 200
```

容器启动时 `docker-entrypoint.sh` 会在 `RUN_MIGRATIONS=true` 时先执行 `alembic upgrade head`，再启动 uvicorn。

`docker-compose.yml` 中的 `db` 服务用于本地/单机部署；生产建议使用托管 PostgreSQL，并删除 `db` 服务、把 `DATABASE_URL` 指向托管实例。

> 若你已在 `docker-compose.yml` 中注释掉 `db` 服务（改为使用外部 PostgreSQL），请同步把 `api` 服务的 `DATABASE_URL` 指向真实数据库地址，并去掉 `depends_on: db`；下面涉及 `compose exec db` 的备份/恢复命令需替换成你实际数据库的连接方式。

### 仓库里有两种镜像，不要混用

| 文件 | 产物 | 体积 | 内容 | 用途 |
| --- | --- | --- | --- | --- |
| `backend/Dockerfile` | 纯 API 镜像 | **81 MB** | 只有 Python 运行时 + API，**不含任何前端文件** | ✅ 生产用这个（前端由 Nginx/CDN 托管） |
| `Dockerfile.app` | API + H5 同源合一 | **82 MB** | API + H5（约 0.6 MB 前端产物） | ❌ 仅排查问题 / 演示 |

`Dockerfile.app` 默认 `APP_ENV=dev`（开放 `/docs`、`/api/dev/*`、`X-Debug-Now`）、SQLite、模拟邮件。
不要把它当生产镜像：调试接口会让任何人触发全量扫描，模拟邮件也不会真的通知到守护人。

页面访问已经做了三层收窄：

1. **环境门禁**：只有 `APP_ENV=dev` 才托管前端。改成 `prod` 后即使 `STATIC_DIR` 仍指向产物目录，`/` 也只返回一行 JSON，`/assets/*` 全 404（启动日志会打 WARNING）。
2. **路径白名单**：只暴露 `/`（index.html）与 `/assets/*`，不挂载整目录、不开目录列表；`/index.html`、`/pages/...`、`/app/main.py`、`/assets/../index.html` 均 404。
3. **端口绑定**：`docker-compose.yml` 中为 `127.0.0.1:8098:8000`，局域网/公网的其他机器无法直接访问。手动 `docker run` 时请同样加 `-p 127.0.0.1:PORT:8000`。

---

## 4. SMTP 配置

以常见服务商为例（465 端口走 SSL，587 端口走 STARTTLS）：

```env
EMAIL_ADAPTER=smtp
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USERNAME=no-reply@your-domain.com
SMTP_PASSWORD=<授权码，不是登录密码>
SMTP_FROM=no-reply@your-domain.com
SMTP_FROM_NAME=在吗
SMTP_USE_TLS=true
SMTP_TIMEOUT_SECONDS=15
```

验证要点：

1. `POST /api/dev/scheduler/run` 仅在非生产可用；生产验证请用真实时间推进或临时把某账户的周期设为 1 天并等到 `ALERT` 阶段。
2. 检查 `notification_record`：`status='sent'`、`simulated=false`、`sent_at` 有值。
3. 检查守护人邮箱是否收到邮件（注意垃圾邮件箱、SPF/DKIM 配置）。
4. 失败时 `last_error` 会记录 `SMTPAuthenticationError` / `SMTPServerDisconnected` 等真实原因。

> `SMTP_PASSWORD` 请使用邮箱服务商的「授权码」或应用专用密码，不要使用账号登录密码。

---

## 5. 数据库：迁移、备份与恢复

### 迁移

```bash
# 容器内
docker compose exec api alembic upgrade head
docker compose exec api alembic current
docker compose exec api alembic history

# 回滚一版
docker compose exec api alembic downgrade -1
```

迁移只新增表/索引，当前唯一版本 `76baff02eb9e_initial_schema`。回滚会删表，务必先备份。

### 备份

```bash
# 每日全量备份（示例，建议放进 crontab）
docker compose exec -T db pg_dump -U zaima -Fc zaima > backup/zaima-$(date +%F).dump
```

### 恢复

```bash
docker compose exec -T db pg_restore -U zaima -d zaima --clean --if-exists < backup/zaima-2026-01-01.dump
```

### 验证恢复（必须做一次）

```bash
# 恢复到临时库并比对行数
docker compose exec -T db createdb -U zaima zaima_restore_check
cat backup/zaima-2026-01-01.dump | docker compose exec -T db pg_restore -U zaima -d zaima_restore_check
docker compose exec db psql -U zaima -d zaima_restore_check -c "select count(*) from account;"
docker compose exec db dropdb -U zaima zaima_restore_check
```

---

## 6. Scheduler：单实例与分布式锁

- 每个 tick 通过 `pg_try_advisory_lock(SCHEDULER_LOCK_KEY)` 抢占执行权；抢不到的实例只记一条日志并跳过本轮。
- 因此**多副本同时开启 Scheduler 也是安全的**（同一时刻只有一个实例在扫描），但会产生无用的空转。
- 推荐做法：
  - 单副本：`SCHEDULER_ENABLED=true`。
  - 多副本：仅一个副本（或独立 worker 容器）设 `true`，其余设 `false`。
- 进程重启后：`notification_record` 中 `pending` 的任务会在下一轮被取走；卡在 `sending` 超过 10 分钟的任务由 `recover_stale()` 重新入队。

独立 worker 示例（同一个镜像，换启动命令；API 容器需设 `SCHEDULER_ENABLED=false`）：

```yaml
  worker:
    build: ./backend
    command: ["python", "-m", "app.worker"]
    environment:
      DATABASE_URL: postgresql+psycopg://zaima:zaima@db:5432/zaima
      SCHEDULER_INTERVAL_SECONDS: "60"
      EMAIL_ADAPTER: smtp
      SMTP_HOST: ${SMTP_HOST}
      SMTP_PORT: ${SMTP_PORT}
      SMTP_USERNAME: ${SMTP_USERNAME}
      SMTP_PASSWORD: ${SMTP_PASSWORD}
      SMTP_FROM: ${SMTP_FROM}
    depends_on:
      db:
        condition: service_healthy
```

`backend/app/worker.py` 是独立的循环进程，收到 `SIGTERM` 后会等待当前轮次结束再退出。

---

## 7. HTTPS 反向代理（Nginx 示例）

```nginx
server {
    listen 443 ssl http2;
    server_name api.your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/api.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.your-domain.com/privkey.pem;

    client_max_body_size 1m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }
}

server {
    listen 80;
    server_name api.your-domain.com;
    return 301 https://$host$request_uri;
}
```

uvicorn 已在 compose 中启用 `--proxy-headers`。

---

## 8. 日志

- 默认输出到 stdout（`LOG_JSON=false` 为可读文本，`true` 为 JSON）。
- 容器日志用 Docker 自带轮转：

```yaml
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "5"
```

- 日志中**不输出**访问凭证（`app/core/security.py::mask_token` 仅用于调试脱敏）；邮箱地址按 `前2位***@域名` 脱敏。
- 建议采集：`level >= WARNING` 单独告警，尤其是 `邮件发送失败`、`未处理异常`、`调度轮次失败`。

---

## 9. 前端构建与发布

```bash
cd frontend
npm ci --registry=https://registry.npmjs.org

# H5（产物 dist/build/h5，可直接静态托管）
VITE_API_BASE_URL=https://api.your-domain.com npm run build:h5

# 微信小程序（产物 dist/build/mp-weixin）
npm run build:mp-weixin

# 支付宝小程序（产物 dist/build/mp-alipay）
npm run build:mp-alipay

# App 资源（产物 dist/build/app，用 HBuilderX 云打包或离线打包）
npm run build:app
```

发布前置条件：

| 平台 | 需要做的事 |
| --- | --- |
| H5 | 配置 `VITE_API_BASE_URL`、HTTPS、静态托管（Nginx/OSS/CDN） |
| 微信小程序 | 在 `src/manifest.json` 填 `mp-weixin.appid`；后台配置 request 合法域名（必须 HTTPS） |
| 支付宝小程序 | 填 `mp-alipay.appid`；配置服务器域名白名单 |
| App | 在 `manifest.json` 填 `appid`，申请证书后用 HBuilderX 云打包；`app-plus.distribute` 中已声明 INTERNET / ACCESS_NETWORK_STATE |

> `manifest.json` 当前 `appid` 为空，属占位符，正式发版前必须补齐。

---

## 10. 上线检查清单

- [ ] `APP_ENV=prod`、`DEBUG=false`、`AUTO_CREATE_TABLES=false`
- [ ] `alembic upgrade head` 已在生产执行，`alembic current` 指向 head
- [ ] `CORS_ORIGINS` 为具体域名
- [ ] SMTP 已配置，且真实发过一封测试邮件（`simulated=false`）
- [ ] HTTPS 证书有效，HTTP 已 301 到 HTTPS
- [ ] `/api/health` 返回 `status=ok`
- [ ] Scheduler 只在一个实例开启，或确认 advisory lock 生效（日志无重复扫描）
- [ ] 数据库每日备份 + **已做过一次恢复演练**
- [ ] 日志轮转已配置，错误日志有告警渠道
- [ ] 前端 `VITE_API_BASE_URL` 指向生产 HTTPS 域名
- [ ] 各平台 appid 已填写，域名白名单已配置
- [ ] 隐私政策与「不是紧急救援服务」的说明已上线
