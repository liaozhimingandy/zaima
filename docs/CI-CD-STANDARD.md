# 项目公共工程规范与 CI/CD 接入手册

> 一次整理，长期复用。新项目只需：复制公共模板 → 修改项目配置 → 配置 Secrets → git push。

---

## 0. 阅读须知：事实依据与可信度标记

本手册遵循「以当前项目**实际可运行配置**为事实依据，不凭空设计」原则。

分析覆盖 5 个真实仓库（均 `github.com:liaozhimingandy/`）：

| 仓库 | 技术栈 | 真实存在的工程配置 |
|---|---|---|
| `fastapi_tuiwen` | Python/FastAPI (uv) | ✅ **GitHub Actions**(docker-build.yaml) / ✅ Dockerfile(uv多阶段) / ✅ docker-compose / ✅ `VERSION` 文件 / ✅ `.env.production`(用 `*_FILE` 引用密钥) / ✅ 真实标签 v0.1.0~v0.3.1 |
| `vue_tuiwen` | Vue3/Vite | ✅ **GitHub Actions**(build.yml→Cloudflare Pages, docker.yml→Docker Hub) / ✅ 4 个 Dockerfile(assets/nginx/static/standalone) / ✅ `package.json` 版本 / ✅ `.env.production`(仅 VITE_APP_* 公开变量) |
| `rhapsody` | Rhapsody 引擎镜像 | ✅ Dockerfile(ubuntu多阶段) / ✅ docker-compose / ✅ .gitattributes(Git LFS) / ✅ deploy.py(推 ACR) |
| `AlphaQuant` | Python 量化(uv) | Git(main+develop)、pyproject/uv、scripts/、docs/；**无 Docker/CI** |
| `RhapsodyRDK` | Java/Eclipse OSGi | Git(main)、build.properties；**无 Docker/CI** |

**可信度标记（全文统一）**：

- ✅ **已验证** —— 直接来自上述真实仓库、已实际存在/运行过的配置。
- 📋 **公共模板/推荐** —— 在真实模式基础上**改进**得到的统一模板（补多架构、缓存、lint/test、sha/latest 标签），需在接入项目时应用。

> ⚠️ **首次整理时的重要纠正**：初稿曾假设「Docker Hub + 统一 Secret 名 `REGISTRY_*` + 无 Cloudflare」。核实真实仓库后修正为：
> 1. 真实 **Secret 名是 `DOCKER_USERNAME` / `DOCKER_PASSWORD`**（fastapi 用于阿里云 ACR，vue 用于 Docker Hub，同一对名跨仓库复用）；Cloudflare 用 `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID`。
> 2. **Cloudflare Pages 已真实接入**（vue build.yml，用 `cloudflare/wrangler-action@v4`）。
> 3. **registry 不统一**：fastapi→阿里云 ACR，vue→Docker Hub。公共规范以 `REGISTRY` 变量统一，Secret 名沿用 `DOCKER_*`。

---

## 1. 文档目的

建立跨项目复用的公共工程规范，覆盖：本地开发 → Git → GitHub → GitHub Actions → 代码检查/测试 → 构建(Docker 镜像 / 静态资源) → 推送(镜像仓库 / Cloudflare) → Release → 部署 → 回滚。

---

## 2. 整体架构

```text
本地开发
   ↓  git commit / push (tag vX.Y.Z)
GitHub (github.com:liaozhimingandy/<repo>, 默认分支 main + develop)
   ↓  自动触发
GitHub Actions
   ├── CI 作业        : setup → 依赖安装 → lint → test          (PR / push)
   ├── docker 作业     : build → 推送镜像仓库(API: ACR / Docker Hub)
   ├── static 作业     : 构建 → Cloudflare Pages 部署            (前端项目)
   └── release 作业    : 打 v* tag → GitHub Release
   ↓
镜像仓库                      静态资源
ACR / Docker Hub              Cloudflare Pages
   ↓                              ↓
docker compose / 部署          CDN
```

> ✅ CI/Cloudflare/Docker 三个作业均已在 `fastapi_tuiwen` / `vue_tuiwen` 验证；本手册模板在其基础上补齐多架构、缓存与回滚标签。

---

## 3. 项目标准目录

✅ 基于真实仓库归纳（不强制套用）：

```text
project/
├── .github/workflows/   # ✅ fastapi: docker-build.yaml；vue: build.yml + docker.yml
│                        # 📋 公共模板: ci-cd.yml(统一) / ci.yml / docker.yml / docker-assets.yml / static.yml / release.yml
├── .github/ISSUE_TEMPLATE/  pull_request_template.md  CODEOWNERS
├── hooks/               # 📋 用户自定义步骤（可选）: ci.sh / pre-build.sh / post-build.sh / pre-deploy.sh / post-deploy.sh
├── docs/                # ✅ AlphaQuant、fastapi 均有
├── scripts/             # ✅ vue 有 build-*.sh / push-images.sh；AlphaQuant 有审计脚本
├── src/ 或 app/
├── tests/ 或 test_*.py / scripts/smoke_*
├── Dockerfile           # ✅ fastapi 单文件；vue 用 docker/<ver>/Dockerfile.*
├── docker/<ver>/        # ✅ vue 多镜像变体目录（含 .env 存版本号）
├── docker-assets/        # 📋 静态资源独立镜像 Dockerfile.assets（仅前端启用）
├── docker-compose.yml   # ✅ fastapi
├── .dockerignore  .gitignore  .gitattributes
├── VERSION              # ✅ fastapi（版本单一来源之一）
├── .env.example / .env.production  # ✅ 提交示例/生产配置，密钥走 *_FILE
├── pyproject.toml 或 package.json  # ✅ 含版本号（后端/前端的自动探测依据）
├── LICENSE  README.md  CHANGELOG.md # ✅ 三件套，vue/fastapi 已有 CHANGELOG
└── project.config.yaml  # 📋 项目专属配置单一来源（人类可读清单）
```

---

## 4. Git 规范

✅ **分支（真实一致）**：`main`（默认/保护）+ `develop`（开发）。fastapi、vue、AlphaQuant 均如此；rhapsody/RDK 单 `main`。
📋 公共推荐：新项目默认 `main`+`develop`，或单 `main`。

✅ **Commit（真实）**：约定式提交，scope 可选：
```text
fix(core): 重构部分代码
feat(search,profile): 增强搜索页与个人中心页
fix(security,ux): 修复 XSS 与竞态
```
`type` ∈ `feat|fix|refactor|docs|test|chore|perf|ci`。

✅ **Tag（真实）**：语义化 `v<major>.<minor>.<patch>`。fastapi 有 `v0.1.0`~`v0.3.1`；vue 有 `v26.9.17`、`v26.9.19`。**Docker 构建由 `v*` tag 触发**（fastapi/vue 一致）。

✅ **Release**：由 tag 触发工作流生成（见 §16 release.yml）。

✅ **.gitignore（真实可复用原则）**：
- 忽略：`.venv/ __pycache__/ *.py[cod] build/ dist/ .pytest_cache .mypy_cache .ruff_cache`、运行产物、`logs/* *.sqlite3`、IDE(`.idea .vscode`)、系统文件。
- ⚠️ **真实踩坑（AlphaQuant）**：忽略数据目录须写 `/data/`（带斜杠），裸 `data/` 会误伤源码包。
- ✅ **安全（fastapi 真实做法）**：`.env.develop` / `.env*.local` / `*.pem` / `*.key` 忽略；`.env.production` **允许跟踪但只能用 `*_FILE` 引用密钥**（密钥值放仓库外的 `/d/Git/secrets/*.txt`）。

---

## 5. GitHub Repository 规范

✅ 命名小写语义清晰；默认 `main` 开分支保护；README/LICENSE/CHANGELOG 三件套（fastapi/vue 满足）。
📋 新增：分支保护（禁直推 main、要求 PR 与 status check）、`CODEOWNERS`（多维护者时）。

---

## 6. GitHub Actions 规范

✅ **真实作业拆解（来自 fastapi/vue）**：

| 作业 | 触发 | 关键步骤 | Secret |
|---|---|---|---|
| fastapi `docker-build.yaml` | `push: tags: ['v*']` | checkout(fetch-depth:0) → setup-python → 取仓库名/最新tag去v → `docker login` ACR → `docker build` → `docker push` | `DOCKER_USERNAME`,`DOCKER_PASSWORD` |
| vue `build.yml` | `push: tags:['v*']` + dispatch | checkout → setup-node@v4(npm cache) → `npm ci` → `npm run build` → `cloudflare/wrangler-action@v4` | `CLOUDFLARE_API_TOKEN`,`CLOUDFLARE_ACCOUNT_ID` |
| vue `docker.yml` | `push: branches:[main]` + dispatch | buildx → `docker login` Docker Hub → 跑 4 个 build 脚本 → `push-images.sh` | `DOCKER_USERNAME`,`DOCKER_PASSWORD` |

📋 **公共模板改进点**（真实存在的不足，模板已补）：
- 用 `docker/setup-buildx-action` + `platforms: linux/amd64,linux/arm64`（真实仅 amd64）。
- 加 `cache-from/to: type=gha`（真实无缓存）。
- 镜像标签补 `sha-<commit>` 与 `latest`（真实仅版本号 / `latest`）。
- CI 作业补 `lint` + `test`（真实 docker 作业无测试）。

---

## 7. Docker 规范

✅ **已验证三种范式**：

**(A) Python/uv 多阶段（fastapi，推荐后端模板）**
```dockerfile
ARG TAG=3.14-slim
FROM python:${TAG} AS builder-image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-cache -i https://pypi.org/simple/
FROM python:${TAG}
COPY --from=builder-image /app/.venv /app/.venv
COPY . /app
ENV VIRTUAL_ENV=/app/.venv PATH="$VIRTUAL_ENV/bin:$PATH"
CMD ["fastapi","run","main.py","--host","0.0.0.0","--port","8000","--proxy-headers"]
```
要点：slim 基础镜像、`uv sync --frozen` 锁版本、层缓存（先拷依赖）、`.venv` 整体拷贝。

**(B) 静态资源独立镜像（assets image，vue 已验证 → 公共约定）**

把「静态文件」与「运行时不耦合」，单独打成一个**空镜像层（`scratch`）镜像**，可独立构建、推送、拉取、分发，供多个下游镜像（nginx / standalone）或边缘节点共用。

- **构建**：`Dockerfile.assets` 以 `FROM scratch` 为基础，仅 `COPY dist/ /usr/share/nginx/html/`，产物即镜像（模板见本交付 `docker-assets/Dockerfile.assets`）。
- **标签**：`<repo>:<ver>-assets` + `:latest-assets` + `:sha-xxxx-assets`（见 §9、docker-assets.yml）。
- **消费**：`Dockerfile.nginx` / `Dockerfile.standalone` 用 `COPY --from=<repo>:<ver>-assets /usr/share/nginx/html /usr/share/nginx/html` 取资源，无需各自重新 build 前端。
- **收益**：① 静态资源可单独 CI/CD（改前端不影响后端/运行镜像）；② 体积远小于含 nginx 的镜像，分发快；③ 多架构只需构建一次；④ 支持「一份资源，多处挂载/复制」。
- ✅ **真实依据**：vue 的 `Dockerfile.base` 即此模式（标签 `<repo>:latest-assets`）。本规范将其提炼为通用约定，并要求补上版本号/sha 标签（见 D4）。

> 📋 **何时用**：有独立静态资源、且希望静态与运行时分离分发的前端项目启用；纯后端项目不启用。

**(B2) 前端完整运行镜像变体（vue 已验证）**
- `Dockerfile.nginx`：`FROM nginx` + `COPY --from=<assets>`（标签 `<ver>-nginx`）。
- `Dockerfile.static`：`FROM lipanski/docker-static-website`（标签 `<ver>-static`）。
- `Dockerfile.standalone`：额外用 golang 编译 `md` 二进制（标签 `<ver>`）。
- 版本号来自 `docker/<ver>/.env` 的 `VER_APP` 等（当前 vue 设为 `latest`，⚠️ 见 D4 应改版本号）。

**(C) 重安装型（rhapsody，已验证）**
ubuntu:24.04 + 阿里云 apt 源 + OpenJDK17 + 静默安装引擎 + 时区 Asia/Shanghai + 非 root 用户。适合「二进制安装包」类项目。

📋 公共约定：多阶段、最小基础镜像、`--no-install-recommends`、`rm -rf /var/lib/apt/lists/*`、非 root、时区 `Asia/Shanghai`（中国环境）、LABEL maintainer。

✅ **.dockerignore**：参考 fastapi 的 `.venv static/media logs*` 等；⚠️ fastapi 误把 `Dockerfile` 自身写进忽略，**应移除**（保留 `Dockerfile` 在上下文）。

---

## 8. 镜像仓库（Registry）规范 ⚠️ 当前不统一

✅ **事实**：
- **fastapi → 阿里云 ACR**：`registry.cn-hangzhou.aliyuncs.com/liaozhiming/<repo>:<tag>`（deploy.py 与 docker-build.yaml 一致）。
- **vue → Docker Hub**：`liaozhiming/vue_tuiwen:<tag>`（docker.yml 登录 Docker Hub）。
- 两者**共用同一对 Secret 名** `DOCKER_USERNAME` / `DOCKER_PASSWORD`（在各自仓库的 Secrets 中分别填 ACR / Docker Hub 凭证）。

📋 **公共统一方案**：用变量 `REGISTRY` 控制目标；Secret 名固定为 `DOCKER_*`。

| 目标 | REGISTRY 值 | 镜像全名示例 |
|---|---|---|
| 阿里云 ACR（fastapi 真实默认） | `registry.cn-hangzhou.aliyuncs.com` | `registry.cn-hangzhou.aliyuncs.com/liaozhiming/fastapi_tuiwen:0.3.1` |
| Docker Hub（vue 真实） | 留空 `""` | `liaozhiming/vue_tuiwen:26.9.17` |

> **迁移建议**：新项目二选一并写进 `project.config.yaml`；存量项目（rhapsody）compose 混用 Docker Hub 命名，应统一为单一 registry。

---

## 9. 镜像 Tag 规范

✅ **真实现状（不统一，待统一）**：
- fastapi：`v0.3.1` tag → 镜像 `…/fastapi_tuiwen:0.3.1`（去 v 的版本号）。
- vue：`docker/<ver>/.env` 的 `VER_APP=latest` → 镜像 `…:latest` / `:latest-nginx` / `:latest-static` / `:latest-assets`（**无版本号，仅 latest**）。

📋 **公共推荐（语义版本 + 增量构建号 + sha + latest）**：

| Tag | 何时构建 | 可变 | 用途 / 锁定建议 |
|---|---|---|---|
| `sha-<short>`（`sha-a1b2c3d`） | 每次构建 | 否 | **回滚锚点（首选）** |
| `<version>-b<build>`（`1.4.2-b128`） | 每次构建 | 否 | **精确定位某次打包**（构建号自增） |
| `<version>`（去 v） | 推送 `v*` tag | 否 | 版本发布、生产可锁定 |
| `latest` | **仅 `main` 分支成功构建** | 是 | 便捷试用；**生产禁止锁定**（会漂移） |
| `<version>-b<build>-assets` / `latest-assets` | 静态资源镜像（见 §7B） | 否/是 | 独立分发静态文件 |
| `<version>-nginx`/`-static` | 前端多变体 | 否 | vue 式运行镜像后缀 |

**构建号 `BUILD_NUMBER`**：取 `github.run_number`，每次工作流运行**自增、永不重复**——这就是「每次打包一个版本序号」。

**构建信息**：CI 生成 `build-info.json`（version / build_number / full_version / git_sha / git_ref / build_date / run_id），并写入镜像 label：
`build.number`、`build.date`、`build.full_version`、`org.opencontainers.image.revision`。
定位只需：`docker inspect <img> | grep build.` 或 `cat /app/build-info.json`。

**标签构建规则（ci-cd.yml / docker.yml / docker-assets.yml 已实现）**：

```text
推送 vX.Y.Z tag  → :<X.Y.Z-bN> + :<X.Y.Z> + :sha-xxxx       （不打 latest）
推送 main 分支    → :<X.Y.Z-bN> + :latest  + :sha-xxxx       （version 读 VERSION，缺省 0.0.0）
手动 workflow_dispatch → 同 main
静态资源镜像       → 上述标签统一加 -assets 后缀
```

- `latest` 仅 main；生产锁定 `:sha-xxxx` 或 `:<version>` 或 `:<version>-bN`。
- 版本号优先级：git tag `vX.Y.Z` > `VERSION` 文件 > `0.0.0`；**不需要 `PROJECT_VERSION` 变量**（修复旧模板版本号缺失 bug）。
- **升级/回滚**：`docker pull repo:1.4.2-b128` 精确锁版；用 `build.number` 判断新旧。

> 弃用 vue 当前纯 `latest` 打法（无法追溯/回滚）；统一为 构建版本 + 语义版本 + sha + latest 四者齐备。

---

## 10. Cloudflare 静态资源规范 ✅ 已验证（vue）

- **服务**：Cloudflare Pages。
- **流程**：`npm ci` → `npm run build` → `cp dist/index.html dist/404.html` → `cloudflare/wrangler-action@v4` 执行 `pages deploy dist --project-name=tuiwen --branch main`。
- **Secret**：`CLOUDFLARE_API_TOKEN`（需 `Account > Cloudflare Pages > Edit`）、`CLOUDFLARE_ACCOUNT_ID`。
- **构建输出**：`dist/`（Vite 默认；`base: '/'`）。
- **SPA 回退**：`cp dist/index.html dist/404.html`（vue 已做，保证前端路由 404 兜底）。
- **回滚**：Pages 控制台 Deployments 一键回退；或 `wrangler pages deployment` 相关命令。
- **缓存**：产物文件名带哈希；Pages 默认 CDN。

> 无静态资源项目（fastapi/rhapsody/AlphaQuant/RDK）不启用。

---

## 11. 环境配置规范

✅ **真实分层（fastapi 范例）**：
- 本地：`.env.develop`（**忽略，不提交**）。
- 生产：`.env.production`（**提交，但密钥不落地**）：
  - `POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password.txt`
  - `REDIS_PASSWORD_FILE=...`、`SECRET_KEY_FILE=...`、`TURNSTILE_SECRET_KEY_FILE=...`
  - docker-compose 把宿主机 `/d/Git/secrets/*.txt` 以只读挂进容器 `/run/secrets/*`。
- 前端：vue `.env.production` 仅 `VITE_APP_*` 公开变量（安全，可提交）。

**覆盖优先级（低→高）**：默认值 < 配置文件(.env) < 环境变量 < compose `environment`/Docker secrets file < CI Secret。

> 原则：**密钥值永不进仓库**；要么进 GitHub Secrets，要么进仓库外文件经 `*_FILE` 注入。

---

## 12. Secrets / Variables 规范 ✅ 已验证真实命名

| 名称 | 类型 | 用途 | 敏感 | 配置位置 |
|---|---|---|---|---|
| `DOCKER_USERNAME` | Secret | 镜像仓库用户名（ACR 或 Docker Hub） | 是 | GitHub Secrets |
| `DOCKER_PASSWORD` | Secret | 镜像仓库密码/Token（ACR 或 Docker Hub） | **是** | GitHub Secrets |
| `CLOUDFLARE_API_TOKEN` | Secret | Cloudflare API Token（Pages:Edit） | **是** | GitHub Secrets |
| `CLOUDFLARE_ACCOUNT_ID` | Secret | Cloudflare 账户 ID | 视情况 | GitHub Secrets |
| `REGISTRY` | Variable | 镜像仓库地址（ACR 默认；Docker Hub 留空） | 否 | GitHub Variables |
| `DOCKER_IMAGE` | Variable | 镜像名 `<namespace>/<project>` | 否 | GitHub Variables |
| `PROJECT_VERSION` | Variable | 语义化版本（CI 也可从 tag/VERSION 读取） | 否 | GitHub Variables |
| `CLOUDFLARE_PROJECT` | Variable | Cloudflare Pages 项目名 | 否 | GitHub Variables |
| `STATIC_BUILD_CMD` / `STATIC_DIST_DIR` | Variable | 静态构建命令 / 输出目录 | 否 | GitHub Variables |

分层：**GitHub Secrets**（token/密码，日志自动脱敏）｜**GitHub Variables**（非敏感配置）｜**项目 .env**（本地，禁提交真实值）｜**Docker ENV/secrets file**（运行时）。

**绝对禁止提交**：`.env` 真实值、`*.pem`、`*.key`、明文密码/Token/密钥。✅ 当前仓库已遵守（已核实无明文密钥入库）。

---

## 13. 版本规范

✅ **真实来源（需统一）**：

| 项目 | 版本来源 | 现状 |
|---|---|---|
| fastapi | `VERSION` 文件=`0.3.6`；git tag `v0.3.1`；pyproject=`0.1.0` | ⚠️ 三者不一致，pyproject 偏旧 |
| vue | `package.json`=`26.9.17` = git tag；Docker 用 `docker/latest/.env` 的 `VER_APP=latest` | ⚠️ Docker tag 与版本脱节 |

📋 **公共模型：三层（语义版本 + 构建号 + 构建信息）**

| 层 | 名称 | 来源 | 示例 |
|---|---|---|---|
| 1 | 语义版本 `VERSION` | git tag `vX.Y.Z`（优先）> `VERSION` 文件 > `0.0.0` | `1.4.2` |
| 2 | 构建号 `BUILD_NUMBER` | `github.run_number`（每次运行自增、不重复） | `128` |
| 3 | 完整构建版本 | `<version>-b<build>` | `1.4.2-b128` |
| 附加 | 构建信息 | sha / 日期 / 分支 / run_id → `build-info.json` + 镜像 label | — |

- 语义版本只由「发布」决定：`scripts/bump_version.sh patch` 自增 → commit → 打 `v*` tag。
- **构建号不手动维护**：每次 CI 运行自动 +1，保证每次打包都能被精确引用。
- GitHub Release 随 `v*` tag 自动生成；镜像同时具备 `1.4.2`、`1.4.2-b128`、`sha-xxx`。
- `VERSION` 文件须与 tag 对齐；本地用 `bump_version.sh` 统一改。

> 对照 §9：`v1.4.2` → `:1.4.2` + `:1.4.2-b128` + `:sha-a1b2c3d`（+ `:latest` 若 main）。

---

## 14. 标准发布流程

✅ **真实流程（fastapi/vue）** + 📋 模板增强：

```text
1. 本地开发/测试                 （人工）
2. git commit（约定式）          （人工）
3. 合并 develop → main           （人工/PR+保护）
4. 打版本: git tag vX.Y.Z        （人工）
5. git push --tags               （人工）
6. GitHub Actions 触发:
   - 后端/前端 docker 作业 → build+push 镜像 (ACR/Docker Hub)   ✅
   - 前端 static 作业 → Cloudflare Pages 部署                   ✅
   - release 作业 → 生成 GitHub Release                        📋
7. 生产 docker compose pull && up （人工/脚本）                  ✅(fastapi compose)
8. 验证                          （人工）
```

| 步骤 | 自动/人工 | 可回滚 | 失败能否继续 |
|---|---|---|---|
| 1-5 | 人工 | — | — |
| 6 构建推送 | 自动 | 重新 push 旧 sha tag | 否 |
| 6 Cloudflare | 自动 | 控制台回退 | 否 |
| 7 部署 | 人工 | 见 §15 | 否 |
| 8 验证 | 人工 | — | — |

---

## 15. 回滚流程

**Docker 回滚** ✅（结合 §9）：
```text
生产锁定 :sha-<commit> （不可变，首选）
   ↓ 回退
compose 中 image 改为 <registry>/<repo>:sha-<旧commit>  → pull && up
# 或回退到 :<旧version>
```
**Cloudflare 回滚** ✅：Pages Deployments 一键回退。
**Git 回滚**：
- `git revert <commit>` ✅ 推荐（保留历史，适已推送）。
- `git reset --hard` ⚠️ 改写历史，仅限未推送私有分支。

> 禁止用 `latest` 作生产回滚锚点（可变）。锁定 `:sha-<commit>` 或 `:<version>`。

---

## 16. 公共模板（复制即用）

> 📋 全部收在**独立文件夹 `ci-cd-template/`**，基于真实模式改进（多架构/缓存/构建号/lint+test），并做到「**任意工程 drop-in**」。

### 16.0 独立文件夹与安装（不覆盖项目文件）

模板与你的项目代码**物理隔离**：

```text
ci-cd-template/          # ★ 整个文件夹拷到项目即可
├── .github/workflows/   # 🟢 通用
├── hooks/               # 🟢 通用（可选）
├── docker-assets/       # 🟢 通用
├── scripts/             # 🟢 通用
├── docs/                # 🟢 通用
├── examples/            # 🟡 项目专属示例（需你改）
├── install.sh/ps1       # 🟢 安装器（不会被拷进项目）
└── README.md            # 通用 vs 专属 对照表
```

- **安全安装**：`bash install.sh /path/to/project`（或 `install.ps1 -Target ...`）。默认**跳过已存在文件**，绝不覆盖你的配置；`--dry-run` 可先预览。
- **区分通用/专属**：`examples/` 以外基本通用；`examples/` 里的 `.example` 需按项目改（如 `project.config.yaml`）。
- **必须放在项目根**：工作流只有位于 `<项目>/.github/workflows/` 才生效，`install.sh` 已按此结构落盘。

### 16.1 模板清单

- **`ci-cd.yml`** ⭐ **首选统一模板**：一个文件覆盖 CI→构建镜像→静态资源→部署→Release，自动识别后端/前端/全栈，按 `project.config.yaml` / GitHub Variables 自适应。
- **`ci.yml`** —— 仅 CI（lint/test），按 `pyproject/requirements` 或 `package.json` 自动识别语言。
- **`docker.yml`** —— 应用镜像构建+推送（多架构、sha/version/latest 三标签）。
- **`docker-assets.yml`** —— 把 `dist/` 打成 `scratch`「静态资源独立镜像」（`<ver>-assets`/`:latest-assets`/`:sha-xxxx-assets`），可独立分发（见 §7B）。
- **`static.yml`** —— `cloudflare/wrangler-action@v4` 部署 Pages。
- **`release.yml`** —— `v*` tag 自动生成 GitHub Release。
- 支撑：`hooks/`（用户自定义步骤）、`pull_request_template.md`、`CODEOWNERS`、`ISSUE_TEMPLATE/bug_report.md`、`docker-assets/Dockerfile.assets`、`scripts/build_push_image.py`、`scripts/bump_version.sh`、`.dockerignore`/`.gitattributes`、`project.config.yaml`。

> 选 `ci-cd.yml` 即可一个文件搞定；若项目希望把构建/部署拆成独立触发或独立权限，再拆用模块化 `ci/docker/docker-assets/static/release`。**两者共用同一套 Variables 与 hooks。**

### 16.2 后端 / 前端自适应逻辑（ci-cd.yml）

`setup` 作业在 checkout 后探测项目类型，输出供后续作业作为 `if` 条件：

| 探测依据 | 判定 |
|---|---|
| 存在 `pyproject.toml` / `requirements.txt` / `setup.py` | `is_backend=true` → 跑 Python lint/test，启用应用镜像自动探测 |
| 存在 `package.json` | `is_frontend=true` → 跑 Node lint/test，启用静态资源/Cloudflare 路径 |
| 二者都有 | `type=fullstack` |
| 存在 `Dockerfile`（或 `ENABLE_DOCKER_APP=true`） | 启用「应用镜像」构建 |
| 存在 `package.json` 且 `ENABLE_DOCKER_ASSETS!=false` | 启用「静态资源独立镜像」 |
| `ENABLE_STATIC_CLOUDFLARE=true` | 启用 Cloudflare Pages 部署 |

变量均为 `auto` 时**零配置即可用**；按需用 `true/false` 覆盖。

### 16.3 是否需要「编译成 HTML」

- **后端项目**（无 `package.json`）：不编译 HTML，只构建应用镜像、跑 Python 测试。
- **前端 / 全栈项目**：`docker-assets.yml` 与 `static.yml` 在执行到「静态资源」路径时，才会运行 `STATIC_BUILD_CMD`（默认 `npm run build`）把源码编译成 `dist/` HTML；编译产物随后用于：
  - 打「静态资源独立镜像」（`docker-assets`，`-assets` 标签）独立分发；
  - 或部署到 Cloudflare Pages（`static`）。
- 若项目**不需要**静态分发/部署，把 `ENABLE_DOCKER_ASSETS=false`、`ENABLE_STATIC_CLOUDFLARE=false`，则完全跳过 HTML 编译，零额外耗时。

### 16.4 预留用户自定义步骤（钩子机制）

公共模板**不实现任何业务命令**，全部留给项目填充。在仓库根 `hooks/` 放入同名脚本即被自动调用（仅当文件存在时执行，不破坏既有流程）：

| 钩子文件 | 触发阶段 | 典型用途 |
|---|---|---|
| `hooks/ci.sh` | CI（lint/test 后） | 定制检查、类型检查、契约测试 |
| `hooks/pre-build.sh` | 镜像构建前（app/assets） | 生成版本文件、拉私有依赖、注入构建参数 |
| `hooks/post-build.sh` | 镜像推送后 | 漏洞扫描(trivy)、推送 SBOM、通知 |
| `hooks/pre-deploy.sh` | Cloudflare 部署前 | 备份、预检 |
| `hooks/post-deploy.sh` | Cloudflare 部署后 | 刷 CDN 缓存、健康检查、通知 |

钩子可读取工作流注入的环境变量：`PROJECT_TYPE` / `IS_BACKEND` / `IS_FRONTEND` / `IMAGE_TAGS` / `DEPLOY_URL` / `CLOUDFLARE_PROJECT` 等（详见 `hooks/README.md`）。返回非 0 会**阻断**该阶段，便于接入质量门禁。

### 16.5 作业编排与产物复用（避免重复构建）

```text
setup ─┬─ ci              测试/检查（PR 与 push 都跑，质量门禁）
       ├─ build-static    前端只编译一次 HTML → 上传 artifact(dist)
       │      ├─ docker-assets   下载 dist → 打 scratch 镜像（不重编）
       │      └─ cloudflare      下载 dist → 部署 Pages（不重编）
       ├─ docker-app      应用镜像（与前端构建并行，互不依赖）
       └─ release         v* tag 自动发版
```

- **只编译一次**：HTML 构建集中在 `build-static`，产物经 `actions/upload-artifact` 传递；下游 `docker-assets`/`cloudflare` 用 `download-artifact` 直接复用，**不再各自 `npm ci && npm run build`**。
- **并行省时**：`docker-app` 与 `build-static` 无依赖、同时跑；`ci` 与构建解耦（CI 只做门禁，构建产出 artifact）。
- **按需跳过**：`ENABLE_DOCKER_ASSETS` 与 `ENABLE_STATIC_CLOUDFLARE` 全关时，`build-static` 直接跳过，前端完全不编译。
- **取消旧运行**：`concurrency` 对 PR 取消被覆盖的旧任务，避免排队浪费。

> ⚠️ 模块化的 `docker-assets.yml` 与 `static.yml` 若**同时启用**，会各自编译一次前端（跨工作流无法共享 artifact）。需要「编译一次复用」时，请使用统一 `ci-cd.yml`。

> 一句话：**能复用产物就不重跑，能并行就不串行，能跳过就不编译。**

---

## 17. 项目需要修改的变量（项目专属）

📋 新项目只改这些（均为 GitHub Variables；`auto` 类无需改即可用）：

| 变量 | 示例值 | 说明 |
|---|---|---|
| `PROJECT_TYPE` | `auto` / `backend` / `frontend` / `fullstack` | `auto`=按文件探测（默认） |
| `ENABLE_DOCKER_APP` | `auto` / `true` / `false` | 应用镜像；`auto`=有 `Dockerfile` 即启用 |
| `ENABLE_DOCKER_ASSETS` | `auto` / `true` / `false` | 静态资源独立镜像；`auto`=前端即启用 |
| `ENABLE_STATIC_CLOUDFLARE` | `true` / `false` | Cloudflare Pages 部署（默认 false，需配 Secret） |
| `REGISTRY` | `registry.cn-hangzhou.aliyuncs.com`（ACR）或 `""`（Docker Hub） | 与 Secret 对应 |
| `DOCKER_IMAGE` | `liaozhiming/vue_tuiwen` | `<namespace>/<project>` |
| `DOCKERFILE_PATH` | `Dockerfile` 或 `docker/latest/Dockerfile.nginx` | 多镜像时分别配置 |
| `CLOUDFLARE_PROJECT` | `tuiwen` | Cloudflare Pages 项目名 |
| `STATIC_BUILD_CMD` / `STATIC_DIST_DIR` | `npm run build` / `dist` | 编译 HTML 的命令与产物目录 |
| `ASSETS_DOCKERFILE` | `docker-assets/Dockerfile.assets` | 静态资源独立镜像的 Dockerfile 路径 |
| `PYTHON_VERSION` / `NODE_VERSION` | `3.14` / `22` | 语言运行时版本 |

> ⚠️ **版本号不再需要 `PROJECT_VERSION` 变量**：由 git `v*` tag 自动去 `v` 提取（见 §9、§13），避免人工维护不一致（修复 D7）。若有 `hooks/ci.sh` 等自定义脚本，按 `hooks/README.md` 放置即可。
| `PORT` / `DOMAIN` | `8000` / `tuiwen.example.com` | 运行时专用 |

---

## 18. 新项目接入 Checklist

```text
□ 1. 创建 GitHub 仓库（main+develop，分支保护）
□ 2. 复制标准目录骨架（§3）
□ 3. 编写 Dockerfile（A/B/C 范式选一；Python 用 A）
□ 4. 补全 .dockerignore / .gitattributes（如需 LFS）
□ 5. 在目标 registry 建仓库（ACR 命名空间 liaozhiming / Docker Hub 同名）
□ 6. 配置 Variables: REGISTRY / DOCKER_IMAGE / PROJECT_VERSION / CLOUDFLARE_PROJECT(按需)
□ 7. 配置 Secrets: DOCKER_USERNAME / DOCKER_PASSWORD / CLOUDFLARE_API_TOKEN+ACCOUNT_ID(按需)
□ 8. 复制 .github/workflows/{ci,docker,static(按需),release}
□ 9. 改 §17 项目变量 + project.config.yaml
□10. 提交 .env.example / .env.production（密钥走 *_FILE，绝不写明文）
□11. git push → 观察 Actions 触发/通过
□12. 验证 registry 出现 sha/version/latest 三 tag
□13. （前端）验证 Cloudflare Pages 部署
□14. git tag v0.1.0 && git push --tags → 验证 Release + 镜像推送
□15. 生产 compose pull && up，验证
```

---

## 19. 故障排查

### GitHub Actions
- **没触发**：`on:` 分支/tag 不匹配；`v*` tag 须 `git push --tags`。
- **Secret 取不到**：名拼错；私有仓库需显式授权组织 secret。
- **Permission denied**：缺 `permissions:`（Release 需 `contents:write`；Pages 需 `pages:write,id-token:write`）。
- **cache 失败**：未用 `cache-from/to: type=gha`。
- **test 失败**：依赖未锁/`setup-python` 版本不符。

### Docker
- **Login 失败**：`DOCKER_PASSWORD` 过期/权限错；`REGISTRY` 地址与凭证不匹配（ACR vs Docker Hub）。
- **Build 失败**：`docker build -f <file> .` 本地复现。
- **Push 失败**：仓库不存在；tag 含非法字符。
- **架构问题**：未启用 buildx / `platforms` 未设 `linux/amd64,linux/arm64`。
- **找不到镜像**：compose `image:` 与推送 registry 不一致（⚠️ fastapi compose 曾写 `fastapi_tuiwen:26.9.17` 无 registry 且版本错）。

### Cloudflare
- **Token 无权限**：需 `Pages:Edit`。
- **Account ID 错**：与控制台不一致。
- **Project 不存在**：`wrangler pages project list` 核对 `--project-name`。
- **上传路径错**：`STATIC_DIST_DIR` 与实际 `dist` 不符。
- **CDN 缓存**：产物文件名加哈希；必要时清缓存。

### 发布
- **Tag 错误**：缺 `v` 前缀导致 docker/release 不触发。
- **版本不一致**：手动只改其一；CI 统一从 tag 读。
- **Docker 与 Git 版本不一致**：见 §13 单一来源。

---

## 20. 安全规范

✅ **禁止提交**（已核实遵守）：明文 `.env`、私钥 `*.pem/*.key`、密码/Token/密钥。
✅ **真实良好实践**（fastapi）：生产密钥经 `*_FILE` + Docker secrets 挂载（`/d/Git/secrets/*.txt`），仓库仅存引用。
📋 **公共要求**：
- 最小权限：Cloudflare Token 仅 `Pages:Edit`；ACR/Docker Hub 用独立凭证。
- 日志脱敏：GitHub 自动对 Secret 打码，勿把 token 写进 `run:` 可见参数/artifact。
- Token 轮换：定期更换；人员离职即吊销。
- ⚠️ **反面案例（rhapsody README）**：`DOCKER_PASS=password` 明文密码——禁止沿用，统一 Secret + `docker login --password-stdin`。

---

## 21. 公共规范 vs 项目专属配置（核心拆分）

### A. 公共规范（复用模板，不变）
- **统一模板 `ci-cd.yml`**（后端/前端自适应、HTML 按需编译、钩子扩展）与模块化 `ci/docker/docker-assets/static/release`（§16）
- **钩子扩展机制**（hooks/ 下 ci/pre-build/post-build/pre-deploy/post-deploy），预留用户自定义步骤（§16.4）
- Git 分支/commit/tag/release 约定（§4/5/13）
- Docker 多阶段范式 A/B/C、国内源、时区、非 root（§7）
- **静态资源独立镜像（scratch assets image）约定** 与 `Dockerfile.assets` / docker-assets.yml（§7B）
- Registry 推送流程 + `DOCKER_*` Secret 命名（§8/12）
- 镜像 Tag 策略：sha / version / latest / 前端多后缀（§9），及「latest 仅 main、版本号从 tag 提取」规则
- Cloudflare Pages 部署命令（§10）
- Secrets/Variables 命名与分层、安全规范（§12/20）
- GitHub Actions 作业拆解（§6）、故障排查（§19）、回滚（§15）

### B. 项目专属（改 §17 变量）
- `PROJECT_TYPE` / `ENABLE_DOCKER_APP` / `ENABLE_DOCKER_ASSETS` / `ENABLE_STATIC_CLOUDFLARE`（均为 `auto` 即零配置）
- `DOCKER_IMAGE` / `REGISTRY` / `DOCKERFILE_PATH` / `ASSETS_DOCKERFILE`
- `CLOUDFLARE_PROJECT` / `STATIC_BUILD_CMD` / `STATIC_DIST_DIR`
- `PYTHON_VERSION` / `NODE_VERSION` / `PORT` / `DOMAIN`
- 是否启用 LFS（rhapsody）、是否多镜像变体（vue）
- `hooks/` 下按需放置自定义脚本（不放置则跳过）

```text
公共规范(模板) + 项目配置(变量) = 完整项目 CI/CD
```

> **不过度抽象**：单项目独有的（rhapsody 的 `ca_alsoapp.pfx`/JDBC `lib/`、vue 的 golang `md` 二进制、各项目端口映射）保留在项目内，不抽进公共规范。

---

## 22. FAQ

**Q：Secret 到底叫什么？**
A：真实仓库统一用 `DOCKER_USERNAME` / `DOCKER_PASSWORD`（ACR 与 Docker Hub 共用这对名），Cloudflare 用 `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID`。不要用 `REGISTRY_*`。

**Q：用 Docker Hub 还是阿里云 ACR？**
A：两者都在用（vue→Hub，fastapi→ACR）。公共规范用 `REGISTRY` 变量切换，Secret 名不变。

**Q：Cloudflare 怎么部署？**
A：vue 已验证：`cloudflare/wrangler-action@v4` + `pages deploy dist --project-name=<项目> --branch main`。

**Q：镜像 Tag 用什么？**
A：统一三类标签——`语义化版本`（从 git tag 自动去 v）+ 不可变 `sha-<commit>` + `latest`。规则：推送 `vX.Y.Z` 打「版本号+sha」，推送 `main` 打「latest+sha」，生产锁定 `sha` 或版本号，绝不用 latest。前端静态资源镜像加 `-assets` 后缀。弃用纯 `latest`。

**Q：静态文件为什么要单独打成镜像？**
A：把 `dist/` 装进 `FROM scratch` 的「静态资源独立镜像」（`-assets` 标签），可与运行时（nginx/standalone）解耦，单独构建/推送/拉取/分发；多架构只构建一次，下游镜像通过 `COPY --from=<repo>:<ver>-assets` 取资源。详见 §7B 与 docker-assets.yml。

**Q：新项目改什么？**
A：只改 §17 变量 + 复制模板，详见 §18 Checklist。

---

## 23. 附录：已识别问题与迁移建议（重要）

| # | 问题 | 位置 | 建议 |
|---|---|---|---|
| D1 | registry 不统一（ACR vs Docker Hub） | fastapi / vue | 用 `REGISTRY` 变量统一；Secret 名保持 `DOCKER_*` |
| D2 | compose 镜像名错：`fastapi_tuiwen:26.9.17`（无 registry 且版本是 vue 的） | fastapi docker-compose.yml | 改为 `registry.cn-hangzhou.aliyuncs.com/liaozhiming/fastapi_tuiwen:<正确版本>` |
| D3 | docker-build.yaml 弱点：setup-python@v2 老旧、python 3.x 宽松、无多架构/缓存/lint/test | fastapi | 采用 📋 docker.yml 模板（buildx、gha 缓存、sha+latest、lint/test） |
| D4 | vue Docker 镜像（含 `-assets` 静态资源镜像）仅打 `latest`（无版本/sha，难追溯回滚） | vue docker/latest/.env `VER_APP=latest` | 改用版本号 + sha 标签；静态资源镜像同样需 `<ver>-assets` + `sha-xxxx-assets`（见 docker-assets.yml） |
| D5 | build.yml 多余上传 GitHub Pages artifact（实际部署 Cloudflare） | vue build.yml | 删 `upload-pages-artifact`，仅 Cloudflare |
| D6 | docker.yml 硬编码 `if: github.repository == 'liaozhiming/vue_tuiwen'` | vue docker.yml | 泛化或删除该守卫 |
| D7 | 版本来源不一致（fastapi: VERSION 0.3.6 / tag v0.3.1 / pyproject 0.1.0） | fastapi | 以 git tag 为权威，pyproject 同步 |
| D8 | .dockerignore 误忽略 `Dockerfile` 自身 | fastapi .dockerignore | 移除 `Dockerfile` 行 |

---

## 24. 附录：真实配置索引（核查依据）

| 文件 | 仓库 | 用途 | 标记 |
|---|---|---|---|
| `.github/workflows/docker-build.yaml` | fastapi | ✅ 推 ACR（v* 触发） | ✅ |
| `Dockerfile` | fastapi | ✅ Python/uv 多阶段 | ✅ |
| `docker-compose.yml` | fastapi | ✅ app+pg+redis，secrets file | ✅（含 D2 缺陷） |
| `VERSION` | fastapi | 版本文件 | ✅ |
| `.env.production` | fastapi/vue | 生产配置（密钥走 *_FILE / VITE_APP_*） | ✅ |
| `.github/workflows/build.yml` | vue | ✅ Cloudflare Pages 部署 | ✅ |
| `.github/workflows/docker.yml` | vue | ✅ 推 Docker Hub（main 触发） | ✅（含 D6 缺陷） |
| `docker/latest/Dockerfile.{base,nginx,static,standalone}` | vue | ✅ 前端多镜像变体 | ✅ |
| `scripts/build-*.sh` / `push-images.sh` | vue | ✅ 构建/推送脚本 | ✅ |
| `Dockerfile` / `Dockerfile-dashboard` | rhapsody | ✅ ubuntu 多阶段 | ✅ |
| `deploy.py` | rhapsody | ✅ 推 ACR（明文密码反例） | ✅→已修订为 scripts/ |
| `.github/workflows/ci-cd.yml` | 本交付 | 📋 统一 drop-in 模板（后端/前端自适应、HTML 按需编译、钩子扩展） | 📋 |
| `.github/workflows/ci.yml` | 本交付 | 📋 仅 CI（语言自适应） | 📋 |
| `.github/workflows/docker.yml` | 本交付 | 📋 应用镜像（sha/version/latest） | 📋 |
| `.github/workflows/docker-assets.yml` | 本交付 | 📋 静态资源独立镜像（-assets 后缀） | 📋 |
| `.github/workflows/static.yml` | 本交付 | 📋 Cloudflare Pages 部署 | 📋 |
| `.github/workflows/release.yml` | 本交付 | 📋 自动 Release | 📋 |
| `hooks/*.sh` | 本交付 | 📋 用户自定义步骤扩展点 | 📋 |
| `docker-assets/Dockerfile.assets` | 本交付 | 📋 静态资源 scratch 镜像 | 📋 |
| `project.config.yaml` | 本交付 | 📋 项目专属配置清单 | 📋 |
| `wrangler.toml` | 无 | Cloudflare 配置 | 未用（action 内联命令） |
| GitHub Releases / tags | fastapi/vue | ✅ 已存在 | ✅ |
