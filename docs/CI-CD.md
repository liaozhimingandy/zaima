# CI/CD 说明（GitHub Actions + Docker Hub）

本文件说明「在吗」项目的持续集成与镜像发布流程、必须人工配置的凭据、发布操作手册，以及**实际验证到什么程度**。

> 原则：本文只记录真实执行过的验证。未能执行的部分（GitHub 云端运行、真实 Docker Hub 推送、原生 App 打包）在「验证记录」与「已知限制」中明确标注。

---

## 1. 为什么是两个工作流而不是三个

任务书建议拆成 `ci.yml` / `build.yml` / `docker-publish.yml`。本项目采用 **2 个文件**，原因如下：

- 若 `build.yml` 与 `docker-publish.yml` 都监听 `push`，两者会**并行启动**，镜像可能在测试结束前就开始推送，违反「仅在 CI 全部通过后推送」。
- 用 `workflow_run` 串联虽然可行，但依赖关系隐式、调试成本高，且仍会重复跑一遍检查。
- 合并到 `release.yml` 后，`needs:` 显式表达「测试 → 构建 → 推送 → Release」的顺序，且每个环节只跑一次。

对应关系：

| 任务书建议 | 本项目实现 |
| --- | --- |
| `ci.yml`（PR 检查） | `.github/workflows/ci.yml` |
| `build.yml`（前端产物） | `.github/workflows/release.yml` 中的 `frontend-artifacts` job |
| `docker-publish.yml`（镜像发布） | `.github/workflows/release.yml` 中的 `docker` job |

---

## 2. 触发矩阵

| 事件 | 工作流 | 后端测试 | 前端检查 | 前端产物 | API 镜像 | 一体化镜像（API+H5） | 镜像推送 | GitHub Release |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pull Request | `ci.yml` | ✅ sqlite + postgres | ✅ | ❌ | ✅ 构建 | ✅ 构建 + 冒烟 | ❌ | ❌ |
| 手动（默认） | `ci.yml` / `release.yml` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| 手动 + `publish=true`（main） | `release.yml` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ `dev-<sha>` / `dev-<sha>-app` | ❌ |
| 手动 + `publish=true`（v* Tag） | `release.yml` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ 正式标签 / 正式标签 `-app` | ✅ |
| push → `main` | `release.yml` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ `dev-<sha>` / `dev-<sha>-app` | ❌ |
| push → `v*` Tag | `release.yml` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ `vA.B`/`vA.B.C` 正式标签 + `sha-<sha>` + `latest`（含 `-app` 变体） | ✅ |

约束：

- PR 流程**不读取任何发布 Secrets**（整个工作流只声明 `contents: read`）。
- PR 流程中镜像 `push: false`，且关闭 attestation（`load: true` 需要）。
- 手动触发默认 `publish=false`；勾选 publish 时若分支既不是 `main` 也不是 `v*` Tag，**直接失败**并给出原因。
- 版本号采用 **Django 风格**（参考 https://docs.djangoproject.com/en/6.1/internals/release-process/）：
  - `vA.B` = 功能发布 feature release（如 `v1.0`、`v2.1`）
  - `vA.B.C` = 补丁发布 patch release（如 `v1.0.1`、`v2.1.3`）
  - `vA.B(a|b|rc)N` = 预发布 alpha/beta/rc（如 `v1.0a1`、`v1.0rc2`），**不会**占用 `latest`，GitHub Release 标记为 prerelease
  - 不匹配上述格式的 Tag（如 `v1`、`1.0`、`ver-1.0`）一律拒绝发布。

---

## 3. 工作流结构

### 3.1 `ci.yml`

```
backend-tests (matrix: sqlite | postgres, 带 postgres service)
frontend-checks (npm ci → type-check → lint? → test? → build:h5 → 校验产物)
docker-build    (API 镜像：buildx 构建 → 校验非 root → 容器启动冒烟 → 收集日志)
app-image       (一体化镜像：构建 → 启动 → 校验 / 返回 H5 入口 + 静态资源可访问 + /api/health)
report          (always，汇总结果；任一失败则本 job 失败)
```

`app-image` 的存在意义：**验证「容器启动就能在浏览器看到 H5」这件事真的成立**，而不是只在本地手工试过。它会启动容器并断言首页含 `<div id="app">`、首页引用的静态资源能 200 返回。

两个镜像还各有反向断言，防止日后互相污染：

| 镜像 | 断言 |
| --- | --- |
| API（`backend/Dockerfile`） | 不含 `/app/static`、镜像内无 `index.html`、`GET /` 必须返回 JSON |
| 调试（`Dockerfile.app`） | 必须存在 `/app/static/index.html`、`GET /` 返回 HTML 且含 `<div id="app">` |

`release.yml` 在**推送之后**还会回拉镜像再校验一次（`should_push=true` 时）：生产镜像若出现 `/app/static` 或任何 `index.html`，直接失败。

两者都会把镜像体积写进本次运行的 Summary，体积异常增大时能从 CI 页面直接看到。

PR 里也跑一次 H5 构建，是为了让「能不能编译」在合并前暴露，而不是等到发布时才发现。

### 3.2 `release.yml`

```
meta（唯一决策点：版本号 / 镜像标签 / 是否推送 / 是否正式发布）
 ├── backend-tests (matrix: sqlite | postgres)
 ├── frontend-checks
 └── 两者通过后：
      ├── frontend-artifacts（h5 / mp-weixin / mp-alipay → 3 个 Artifact）
      └── docker（凭据校验 → 版本不可变校验 → 登录 → buildx push → 输出 Digest）
             └── github-release（仅正式 Tag 且推送成功）
report（always）
```

`meta` 把「版本怎么算」收敛到一处 bash 脚本，其余 job 只消费它的 outputs，避免各 job 各算一套导致标签不一致。

---

## 4. 必须人工配置的凭据

在 GitHub 仓库 **Settings → Secrets and variables → Actions** 中配置。

### 4.1 Secrets（敏感，写入后不可读）

| 名称 | 必填 | 说明 |
| --- | --- | --- |
| `DOCKERHUB_USERNAME` | 是 | Docker Hub 用户名（也可放到 Variables 的 `DOCKER_USERNAME`） |
| `DOCKERHUB_TOKEN` | 是 | Docker Hub **Access Token**（Account Settings → Security → New Access Token，权限 Read & Write） |

### 4.2 Variables（非敏感，日志可见）

| 名称 | 必填 | 示例 | 说明 |
| --- | --- | --- | --- |
| `DOCKER_REPOSITORY` | 是 | `liaozhiming/zaima-api` | **生产镜像**仓库（纯 API，不含前端） |
| `DOCKER_APP_REPOSITORY` | 否 | `liaozhiming/zaima-test` | **测试镜像**仓库（含 H5）。不配置时退回「同一仓库 + `-app` 后缀」 |
| `ENABLE_FLOATING_TAGS` | 否 | `false` | 设为 `true` 才推送 `1.0`、`1` 浮动标签 |
| `BUILD_H5` / `BUILD_MP_WEIXIN` / `BUILD_MP_ALIPAY` | 否 | `true` | 设为 `false` 可临时跳过某平台构建，用于排查 |

### 4.3 与任务书命名的差异（重要）

任务书写的是「`DOCKER_PASSWORD` 放 Repository Variables」。本项目改为：

| 任务书 | 本项目 | 原因 |
| --- | --- | --- |
| `vars.DOCKER_USERNAME` | 支持（作为 `secrets.DOCKERHUB_USERNAME` 的回退） | 用户名不敏感，放 Variables 合理 |
| `vars.DOCKER_PASSWORD` | **改为 `secrets.DOCKERHUB_TOKEN`** | 密码/Token 放 Variables 会对所有能看 Actions 日志的人可见，属于凭据泄露 |
| `vars.DOCKER_REPOSITORY` | `vars.DOCKER_REPOSITORY` | 一致 |

工作流同时兼容旧命名：`${{ secrets.DOCKERHUB_TOKEN || secrets.DOCKER_PASSWORD }}`、`${{ secrets.DOCKERHUB_USERNAME || vars.DOCKER_USERNAME }}`。
若你已按任务书把密码写进 Variables，请**先删除该 Variable**，再把它作为 Secret 重新添加。

### 4.4 Docker Hub 仓库

1. 登录 Docker Hub → Create Repository → 名称 `zaima-api`（命名空间用你的用户名）。
2. 可见性建议 Private（镜像内不含密钥，但私有更稳妥）。
3. 建议开启 **2FA**，CI 只使用 Access Token，不要使用账号密码。

### 4.5 凭据缺失时的行为

`docker` job 在推送前有独立的校验步骤，缺任意一项都会 `exit 1` 并输出 `::error title=...`，**不会静默跳过发布**。

---

## 5. 镜像标签策略

| 触发 | 标签 | 说明 |
| --- | --- | --- |
| push `main` | `dev-<7位sha>`、`sha-<完整sha>` | 开发版本，**不会**写 `latest` |
| push `v1.0`（功能发布） | `1.0`、`sha-<完整sha>`、`latest` | 正式版本（A.B） |
| push `v1.0.1`（补丁发布） | `1.0.1`、`sha-<完整sha>`、`latest` | 正式版本（A.B.C），并滚动更新 `1.0`（见浮动标签） |
| `v1.0.1` + `ENABLE_FLOATING_TAGS=true` | 追加 `1.0`、`1` | `1.0` 指向该小版本最新补丁；默认关闭 |
| push `v1.0a1`（预发布） | `1.0a1`、`sha-<完整sha>` | **不**写 `latest`，GitHub Release 标记为 prerelease |
| 手动 publish（main） | `dev-<7位sha>`、`sha-<完整sha>` | 同 push main |
| PR | 不产生远程标签 | 仅本地 `zaima-api:ci` / `zaima-app:ci` |

### 两个镜像，标签互不重叠

| 镜像 | 内容 | 标签（配了 `DOCKER_APP_REPOSITORY`） | 标签（未配置时） |
| --- | --- | --- | --- |
| 生产 | 纯 API，**无前端** | `<DOCKER_REPOSITORY>:1.0`（或 `:1.0.1`）/ `:sha-<sha>` / `:latest` | 同左 |
| 测试 | API + H5（含 `/app/static`） | `<DOCKER_APP_REPOSITORY>:1.0` / `:sha-<sha>` / `:latest` | `<DOCKER_REPOSITORY>:1.0-app` 等 |

推荐给测试镜像单独建仓库（`zaima-test`），这样 `docker pull` 时不会拿错；两个仓库的标签完全对称，版本一一对应。

规则：

- `latest` **只**由 `v*` Tag 的正式发布更新；开发构建永远不碰 `latest`。
- `sha-<完整sha>` 恒定存在，可精确追溯代码。
- 正式版本默认**不可变**：推送前用 `docker buildx imagetools inspect` 检查 `1.2.3` 是否已存在，存在则失败。确需重发时，手动触发并勾选 `force_tag`。
- 每次推送后输出 **Digest**，并写入 `image-manifest` Artifact；部署可用 `repo@sha256:...` 固定版本。

---

## 6. 发布操作手册

### 6.1 提 PR

推送分支 → 创建 PR → `ci.yml` 自动运行。全绿才合并。此流程不会产生任何镜像。

### 6.2 合入 main（开发版）

合并后自动运行 `release.yml`：

1. 测试通过 → 2. 生成 3 个前端 Artifact → 3. 推送 `dev-<sha>` 与 `sha-<sha>` 镜像。

验证：

```bash
docker pull <DOCKER_REPOSITORY>:dev-<sha>
```

### 6.3 正式发布

```bash
git checkout main && git pull
git tag -a v1.0 -m "在吗 V1.0（首个功能发布）"
git push origin v1.0
# 补丁发布用 vA.B.C：git tag -a v1.0.1 -m "在吗 V1.0.1" && git push origin v1.0.1
# 预发布用 vA.B(a|b|rc)N：git tag -a v1.1rc1 -m "在吗 V1.1 RC1" && git push origin v1.1rc1
```

流水线会：跑全量测试 → 构建三端产物 → 推送 `1.0` / `sha-...` / `latest` → 创建 GitHub Release（已存在则跳过）。

> 若某个 Tag 在修复前已推送但发布失败（如早期 `v1.0` 被旧规则拒绝），需**重新推送该 Tag 才会重跑**：先 `git push origin :refs/tags/v1.0` 删除远程旧 Tag，再 `git push origin v1.0`（强制覆盖同名的本地/远程 Tag 可用 `git tag -f v1.0 && git push -f origin v1.0`，注意这会让该 Tag 指向的 commit 不变、只重跑流水线）。

回滚：

```bash
docker pull <DOCKER_REPOSITORY>@sha256:<digest>   # 用不可变 digest 回滚
```

**不要**删除并重建同名 Tag——旧 Tag 删除后新 Tag 可能指向不同 commit，而镜像标签需保持不可变。

### 6.4 手动运行

Actions → 选择工作流 → Run workflow：

- `publish=false`（默认）：只做检查与构建，不推送。
- `publish=true`：在 `main` 上等价于开发版发布；在 `v*` Tag 上等价于正式发布。
- `force_tag=true`：仅用于修复失败发布，允许覆盖已存在的版本标签，会打 `::warning`。

---

## 7. 产物下载

Actions → 选择某次运行 → 页面底部 **Artifacts**：

| Artifact 名称 | 内容 |
| --- | --- |
| `zaima-frontend-h5-<version>-<sha>` | H5 静态站点（根目录即 `index.html`） |
| `zaima-frontend-mp-weixin-<version>-<sha>` | 微信小程序工程（用开发者工具导入） |
| `zaima-frontend-mp-alipay-<version>-<sha>` | 支付宝小程序工程 |
| `pytest-report-<version>-<db>` | JUnit 测试报告（可用 `--junitxml` 格式在任意 CI 面板展示） |
| `image-manifest-<version>-<sha>` | 镜像清单：commit / tags / digest |

保留期：前端产物 30 天，JUnit 报告 14 天，镜像清单 90 天。

---

## 8. 安全设计

| 项 | 做法 |
| --- | --- |
| 权限 | 工作流默认 `permissions: contents: read`；只有 `github-release` job 提升为 `contents: write` |
| PR 隔离 | PR 工作流不含任何 secret 引用；`pull_request` 事件本身无法读取仓库 secrets（fork 场景） |
| Action 固定 | 所有第三方 Action 固定到**完整 commit SHA**（见下表），不使用浮动 tag |
| 凭据 | Docker Hub 使用 Access Token，仅存于 Secrets；日志中不打印 |
| checkout | 一律 `persist-credentials: false`，避免 Token 残留在 `.git/config` |
| 镜像内容 | 生产镜像默认 `APP_ENV=prod`、`AUTO_CREATE_TABLES=false`、`RUN_MIGRATIONS=false`；不 COPY `.env`；`.dockerignore` 二次拦截 |
| 前端产物 | 构建后校验 `dist/build` 下不存在 `.env*` 文件 |
| 构建期密钥 | 镜像 build-args 仅传 `APP_VERSION` / `VCS_REF`，不传任何数据库或 SMTP 凭据 |

固定到 SHA 的 Action：

| Action | 版本 | SHA |
| --- | --- | --- |
| `actions/checkout` | v4 | `11d5960a326750d5838078e36cf38b85af677262` |
| `actions/setup-node` | v4 | `49933ea5288caeca8642d1e84afbd3f7d6820020` |
| `actions/setup-python` | v5 | `a26af69be951a213d495a4c3e4e4022e16d87065` |
| `actions/upload-artifact` | v4 | `ea165f8d65b6e75b540449e92b4886f43607fa02` |
| `docker/setup-buildx-action` | v3 | `8d2750c68a42422c14e847fe6c8ac0403b4cbd6f` |
| `docker/login-action` | v3 | `c94ce9fb468520275223c153574b00df6fe4bcc9` |
| `docker/build-push-action` | v6 | `10e90e3645eae34f1e60eeb005ba3a3d33f178e8` |

升级动作时：改 SHA 的同时更新本表，并在 PR 中说明原因。

---

## 9. 本地复现

### 9.1 前端（与 CI 完全一致的步骤）

```bash
# 在干净目录中复现，避免受本地 node_modules 影响
mkdir -p /tmp/fe-ci && cd /tmp/fe-ci
cp -r <repo>/frontend/{package.json,package-lock.json,tsconfig.json,vite.config.ts,index.html,src} .
npm ci --registry=https://registry.npmjs.org --no-audit --no-fund
npm run type-check
VITE_APP_VERSION=1.0.0 npm run build:h5
npm run build:mp-weixin
npm run build:mp-alipay
```

> Windows 下 `npm ci` 会批量删除 `node_modules`，若你的环境有安全删除保护，请在干净目录执行。

### 9.2 后端

```bash
cd backend
pip install -r requirements-dev.txt

# 需一个可用的 PostgreSQL
export DATABASE_URL="postgresql+psycopg://zaima:zaima@127.0.0.1:55432/zaima_ci"
export TEST_DATABASE_URL="$DATABASE_URL"
alembic upgrade head && alembic downgrade base && alembic upgrade head
pytest -q --junitxml=pytest-postgres.xml
```

### 9.3 镜像

```bash
docker build -f backend/Dockerfile \
  --build-arg APP_VERSION=1.0.0 \
  --build-arg VCS_REF=$(git rev-parse HEAD) \
  -t zaima-api:local backend

docker run --rm --entrypoint id zaima-api:local -u          # 应为 10001，不是 0
docker run -d --name zaima-smoke -p 18000:8000 \
  -e APP_ENV=dev -e AUTO_CREATE_TABLES=true -e SCHEDULER_ENABLED=false \
  -e DATABASE_URL=sqlite+pysqlite:////tmp/zaima.db zaima-api:local
curl -fsS http://127.0.0.1:18000/api/health
```

### 9.4 工作流静态校验

```bash
# 安装 actionlint 后在仓库根目录执行
actionlint
```

---

## 10. 验证记录

执行时间：2026-10-23，环境：Windows 11 + Docker 28.1.1 + Node 22.22.2 + Python 3.13.14。

| 验证项 | 方式 | 结果 |
| --- | --- | --- |
| 工作流 YAML 语法与表达式 | `actionlint 1.7.12`（对 `.github/workflows/` 全部文件） | **通过，0 error** |
| actionlint 是否真的在校验 | 注入 `needs.not-a-job.result` 后重跑 | **被检出**（`property "not-a-job" is not defined`），证明校验生效 |
| Action 版本固定 | 通过 GitHub API 解析 tag → commit SHA | 7 个 Action 均为真实 commit SHA |
| 前端依赖可复现 | 干净目录 `npm ci` | **562 packages，1m，成功** |
| 前端类型检查 | `npm run type-check` | 通过（无输出，0 error） |
| 前端三平台构建 | `build:h5` / `build:mp-weixin` / `build:mp-alipay` | 三个均 `DONE Build complete` |
| 产物存在性 | 校验 `h5/index.html`、`mp-weixin/app.json`、`mp-alipay/app.json` | 全部存在 |
| 版本注入 | `VITE_APP_VERSION=1.0.0` 构建后检索产物 | 产物中出现 `1.0.0` |
| 产物无 `.env` | `find dist/build -name '.env*'` | 未发现 |
| 后端迁移往返 | `upgrade → downgrade → upgrade`（PG 16） | 通过，`alembic current` = `76baff02eb9e (head)` |
| 后端测试（postgres） | `pytest --junitxml` | **66 passed**，JUnit: tests=66 failures=0 errors=0 |
| 后端测试（sqlite） | 同上 | **66 passed** |
| 镜像构建 | `docker build`（与 CI 相同 build-args） | 成功，209 MB |
| 非 root | `docker run --entrypoint id -u` | `10001` |
| 镜像内不含 `.env` / `tests` | 容器内 `ls` | 均不存在 |
| 生产安全默认 | 不传 `APP_ENV` 启动，请求 `/api/dev/scheduler/run` | `404 NOT_FOUND`（调试接口未注册） |
| 容器启动 | `docker run` + `/api/health` | `status=ok`，`database.ok=true` |
| HEALTHCHECK | `docker inspect .State.Health.Status` | `healthy` |
| 优雅退出 | `docker stop` | 1 秒退出，`ExitCode=0` |
| 一体化镜像构建 | `docker build -f Dockerfile.app .` | 成功，209 MB |
| 一体化镜像启动（无任何环境变量） | `docker run -p 8080:8000` | healthcheck `healthy` |
| 容器内 H5 可访问 | `GET /` | 200，`text/html`，含 `<div id="app">` |
| 容器内静态资源 | `GET /assets/index-*.js` | 200 |
| 容器内接口 | `GET /api/health` | 200，`database.ok=true`（SQLite 自动建表） |
| 容器内业务闭环 | 注册→添加守护人→确认→时间推进→触发事件 | `alertsCreated=1`、`sent=1`、`.eml` 落盘 `/data/mailbox` |
| 调试接口鉴权 | 无 token 调 `POST /api/dev/scheduler/run` | **401**（带 token 为 200） |
| 页面托管环境门禁 | `APP_ENV=prod` + `STATIC_DIR` 仍设置 | `/` 返回 JSON、`/assets/*` 与 `/index.html` 全部 **404**，日志给出警示 |
| 托管路径白名单 | dev 环境逐个探测 | `/` 200、`/assets/*` 200；`/index.html`、`/pages/...`、`/app/main.py`、`/assets/../index.html` 均 **404** |
| 端口暴露面 | `docker port dev-zaima-app-01` | 仅绑定 **127.0.0.1:8098**，局域网不可达 |
| Docker Hub 登录与推送 | — | **未验证**（无凭据，未执行） |
| 工作流在 GitHub 上真实运行 | — | **未验证**（本地无仓库远端/Token） |

### 10.1 版本推导脚本的场景验证

`meta` job 的版本/标签推导是纯 bash，已抽出在本地逐场景执行（`GITHUB_SHA=3f8a1b2c...`，仓库 `liaozhiming/zaima-api`）：

| 场景 | version | should_push | is_release | 产出的标签 |
| --- | --- | --- | --- | --- |
| push tag `v1.0.0` | `1.0.0` | true | true | `1.0.0`、`sha-3f8a1b2c…`、`latest` |
| 同上 + `ENABLE_FLOATING_TAGS=true` | `1.0.0` | true | true | 追加 `1.0`、`1` |
| push `main` | `dev-3f8a1b2` | true | false | `dev-3f8a1b2`、`sha-…`（无 `latest`） |
| push `feature/x` | `dev-3f8a1b2` | false | false | 不推送 |
| push tag `v1.0`（非法） | — | — | — | **失败**，提示不符合规范 |
| 手动 `publish=false` | `dev-3f8a1b2` | false | false | 不推送 |
| 手动 `publish=true`（main） | `dev-3f8a1b2` | true | false | `dev-…`、`sha-…` |
| 手动 `publish=true`（feature/x） | — | — | — | **失败**，提示只允许 main / Tag |
| 手动 `publish=true`（tag `v2.1.3`） | `2.1.3` | true | true | `2.1.3`、`sha-…`、`latest` |
| 未配置 `DOCKER_REPOSITORY` | `dev-3f8a1b2` | true | false | 镜像名回退为 `zaima-api`，凭据校验步骤**报错退出** |
| 配置了 `DOCKER_APP_REPOSITORY`（main） | `dev-3f8a1b2` | true | false | 测试镜像推到独立仓库：`zaima-test:dev-3f8a1b2`、`zaima-test:sha-…` |
| 配置了 `DOCKER_APP_REPOSITORY`（tag） | `1.2.3` | true | true | `zaima-test:1.2.3`、`:sha-…`、`:latest` |

---

## 11. 已知限制与未完成事项

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 工作流未在 GitHub 云端跑过 | ⚠️ 待验证 | 本机无法创建远端仓库并触发 Actions，仅做了 actionlint 静态校验与「本地等价执行」。首次推送后请检查第一次运行结果。 |
| Docker Hub 推送未真实执行 | ⚠️ 待验证 | 需要你在仓库配置 `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` / `DOCKER_REPOSITORY`。 |
| Android / iOS 安装包 | ❌ 未实现 | uni-app 原生包需 HBuilderX 云打包或离线原生工程 + 签名证书（`manifest.json` 的 appid 仍为空）。流水线只产出 App 资源检查提示，**不会**用 H5 产物冒充安装包。 |
| ESLint | ❌ 未配置 | 项目无 ESLint 配置文件。工作流已做能力探测：一旦 `package.json` 增加 `lint` 脚本即自动执行。 |
| 前端单元测试 | ❌ 未配置 | 同上，已做 `test` 脚本探测。 |
| 镜像漏洞扫描 | ❌ 未接入 | 预留位置：可在 `docker` job 后加 Trivy/`docker scout` 并对正式发布设置阈值。当前未加，避免引入未验证的门禁。 |
| 多架构镜像 | ❌ 未启用 | 默认仅 `linux/amd64`。启用前需确认目标服务器架构与 `psycopg` 依赖兼容性。 |
| 一体化镜像定位 | ⚠️ 仅调试 | `Dockerfile.app` 默认 `APP_ENV=dev` + SQLite + 模拟邮件，会开放 `/api/dev/*`；**不可直接用于生产**，生产用 `backend/Dockerfile`。 |
| 生产部署 | ❌ 不在本任务范围 | 不 SSH、不自动迁移、不改 DNS/HTTPS、不发小程序审核版，详见 `DEPLOYMENT.md`。 |
| SBOM / Provenance | ✅ 仅正式推送 | `docker` job 在 push 时生成 attestation；PR 构建关闭（`load: true` 不兼容）。 |

---

## 12. 后续生产部署建议

1. **镜像固定到 Digest**：部署清单里写 `repo@sha256:...`，避免 `latest` 漂移。
2. **迁移与发布分离**：CI 不跑生产迁移。上线流程为「拉镜像 → `alembic upgrade head`（一次性 job）→ 滚动更新」，`RUN_MIGRATIONS` 在生产保持 `false`。
3. **多环境分 Tag**：如需要 staging，可新增 `v*-rc*` 规则并推送 `rc-<sha>` 标签，但**不要**让它更新 `latest`。
4. **加固门禁**：接入 Trivy 扫描（失败即阻断正式发布）、接入 CodeQL、为 `main` 设置 required status checks（`CI 汇总`）。
5. **密钥管理**：生产 `DATABASE_URL` / `SMTP_*` 用部署平台的 Secret 管理，绝不写入镜像或仓库。
