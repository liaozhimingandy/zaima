# CI 自动化规范（测试 + 构建）

> 目标：**流程统一，命令不统一**。所有项目遵循同一条 CI 生命周期，但每个项目自由决定 install / lint / test / build 的实现。

---

## 0. 现状扫描（事实依据）

本规范不是凭空设计，先看现有项目的实际情况：

| 项目 | 技术栈 | 已有测试/构建事实 | CI 现状 |
|---|---|---|---|
| `fastapi_tuiwen` | Python / FastAPI / uv | `pyproject.toml`、`uv.lock`、`pytest`、`Dockerfile`(python:3.14-slim + uv 多阶段)、`docker-compose.yml`、`VERSION` | ✅ `docker-build.yaml`：推 `v*` tag → 登录阿里云 ACR → build+push |
| `vue_tuiwen` | Vue3 / Vite / Node | `package.json`(vite build)、`docker/` 下 4 个 Dockerfile、`scripts/build-*.sh`、`push-images.sh` | ✅ `build.yml`：`v*` → Cloudflare Pages；`docker.yml`：main → Docker Hub |
| `rhapsody` | Java / Rhapsody 引擎 | `Dockerfile`(ubuntu 24.04 多阶段)、`docker-compose.yaml`、`deploy.py`(推 ACR)、Git LFS | ✅ 本地脚本部署，无 Actions |
| `AlphaQuant` | Python / uv | `pyproject.toml`、`uv.lock`、`scripts/`、`docs/` | ❌ 无 Docker / 无 CI |
| `RhapsodyRDK` | Java / Eclipse PDE | `build.properties`、Eclipse 插件工程 | ❌ 无 Docker / 无 CI |

**结论**：
- 真实存在的命令是 `uv sync` / `pytest` / `npm ci` / `npm run build` / `docker build`，但它们**分散、写法不一**。
- 现有的 workflow 把「测试/构建/推送」混在一起，且命令写死，无法复用到不同技术栈。
- 因此需要一个**公共生命周期 + 项目声明命令**的中间层。

---

## 1. 目标

1. 新项目不再重复设计 GitHub Actions。
2. 不同技术栈（Python / Node / Docker / 静态站）共用同一套流程骨架。
3. **测试通过才构建，构建通过才发布**。
4. 项目只需声明：类型、安装/检查/测试/构建命令、是否 Docker、是否静态发布。
5. 发布（Docker Hub / Cloudflare / Release）与 CI 分离，只在明确时机执行。

---

## 2. 核心设计思想

```text
                    公共 CI 生命周期（固定）
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
        Install           Lint/Test        Build
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                     项目自定义实现
                  （.ci/ci.sh / Makefile / 命令）
```

三条原则：

1. **公共 workflow 只编排，不写死 `pytest` 或 `npm test`。**
2. **项目通过统一入口声明实现**（`.ci/ci.sh <stage>`），内部爱用什么用什么。
3. **发布是独立阶段**，只在 `v*` tag（或显式开关）触发。

---

## 3. CI 生命周期

```text
prepare(install)
   ↓
lint
   ↓
typecheck
   ↓
test
   ↓
build
   ↓
package（可选）
   ↓
artifact（上传）
   ↓
publish（独立阶段：docker / static / release）
```

- 前 6 个阶段属于 **CI**，在 PR 与 push 都跑。
- `publish` 属于 **CD**，只在 tag 或手动触发，且必须 `needs` CI 成功。
- 阶段可缺省：项目没有 typecheck 就跳过，不强制补齐。

---

## 4. 项目与公共 CI 的职责边界

| 层 | 负责 | 不负责 |
|---|---|---|
| **公共 workflow**（`.github/workflows/ci-cd.yml`） | 触发、顺序、缓存、artifact、失败即停、发布编排 | 具体测试/构建命令 |
| **项目配置**（`.ci/project.config.yaml`） | 声明阶段命令、开关、镜像/静态参数 | 流程控制 |
| **项目入口**（`.ci/ci.sh`） | 解析阶段命令，调用项目实现 | 发布 |
| **项目实现**（`package.json` / `pyproject.toml` / `.ci/stages/*.sh` / `Makefile`） | 真正的 install/lint/test/build | 触发与编排 |

一句话：**公共流程负责“什么时候做什么”，项目负责“具体怎么做”。**

---

## 5. 项目配置规范

配置文件：`.ci/project.config.yaml`（CI 直接读取，不用再同步 GitHub Variables）。

```yaml
project:
  name: my-project
  type: auto                  # auto | backend | frontend | fullstack
  version: 0.1.0

ci:
  entry: auto                 # auto | builtin | script | make | commands
  install: ""                 # 留空=内置或 .ci/stages/install.sh
  lint: ""
  typecheck: ""
  test: ""
  build: ""
  package: ""

docker:
  registry: docker.io         # 或 registry.cn-hangzhou.aliyuncs.com
  image: namespace/my-project
  dockerfile: ""              # 留空=自动搜索
  context: ""                 # 留空=Dockerfile 所在目录
  platforms: linux/amd64      # 需要多架构再写两个
  app_strategy: auto          # auto | dockerfile | nginx-prebuilt | none

static:
  build_command: npm run build
  output_dir: dist
  assets_image:
    dockerfile: .ci/docker-assets/Dockerfile.assets

enable:
  docker_app: auto
  docker_assets: auto
  static_cloudflare: false

cloudflare:
  project: ""
```

### 命令解析优先级（每个阶段独立）

```text
ci.<stage> 命令
   ↓ 没有
.ci/stages/<stage>.sh
   ↓ 没有
Makefile 的 <stage> 目标（entry=auto/make）
   ↓ 没有
内置探测（npm / pnpm / yarn / uv / pytest / ruff / tsc）
```

> 这条顺序由 `.ci/ci.sh` 实现，见附录 B。

---

## 6. 安装依赖规范

| 技术栈 | 推荐命令 | 锁文件 |
|---|---|---|
| Python / uv | `uv sync --frozen`（CI 用 `--no-dev` 视项目而定） | `uv.lock` |
| Python / pip | `pip install -r requirements.txt` | `requirements.txt` |
| Node / npm | `npm ci`（有 lock）；无 lock 才 `npm install` | `package-lock.json` |
| Node / pnpm | `corepack enable && pnpm install --frozen-lockfile` | `pnpm-lock.yaml` |
| Node / yarn | `yarn install --frozen-lockfile` | `yarn.lock` |

规则：
- **必须优先使用锁文件**；没有锁文件时降级安装，但要在日志中提示。
- 安装失败立即停止，不进入 lint/test。
- 前端目录可能是子目录（`frontend/`、`web/`），由探测脚本定位。

---

## 7. Lint 规范

- 只在**项目声明了 linter** 时执行：
  - Python：`.ruff.toml` 或 `pyproject.toml` 含 `[tool.ruff]`
  - Node：`package.json` 含 `lint` 脚本
- Lint 失败 = 阶段失败，**阻断后续**。
- 若项目暂时不想阻断，可在 `ci.lint` 里显式写 `eslint . || true`（自行承担风险）。
- 不建议把 lint 和 test 混在一个脚本里，便于单独重跑。

---

## 8. Type Check 规范

- 可选阶段，只有项目存在类型检查配置才执行：
  - Node：`tsconfig.json` 或 `typecheck` 脚本
  - Python：`mypy.ini` 或 `[tool.mypy]`
- 类型检查失败默认**阻断**（类型错误通常意味着构建会失败）。
- 没有配置就跳过，不强行引入。

---

## 9. Test 规范

测试分层（项目按需实现）：

| 层级 | 何时跑 | 说明 |
|---|---|---|
| Unit | 每次 PR / push | 最快，必须通过 |
| Integration / API | PR / main | 依赖服务时可用 docker compose 起服务 |
| E2E | main / tag / 手动 | 慢，不阻塞每个 PR |
| Lint / Typecheck | PR / push | 质量门禁，见 §7/§8 |

推荐 CI 测试集合：

```text
ci
├── lint
├── typecheck
├── unit-test
└── build
```

- **Push**：lint + typecheck + unit + build。
- **Pull Request**：同上，且不发布。
- **Tag**：完整测试 + 完整构建 + 发布。

> 如果 E2E 很慢，用 `ci.test` 拆成 `test:unit` / `test:e2e`，只在 main/tag 调 e2e。

---

## 10. Build 规范

- **测试通过后才构建**（`build` 依赖 `ci` 成功）。
- 构建命令由项目声明（`ci.build` 或 `static.build_command` 或 `Makefile`）。
- 前端构建必须支持子目录（`working-directory` / 入口脚本内 `cd`）。
- 构建失败 = 阶段失败，不进入打包/发布。
- 构建产物统一归一到仓库根 `dist/`（前端），便于镜像与部署复用。

---

## 11. Artifact 规范

| 产物 | 路径 | 处理 |
|---|---|---|
| 前端静态文件 | 根 `dist/` | `actions/upload-artifact`，下游镜像/部署复用 |
| Python wheel/sdist | `dist/` | 可选上传 artifact |
| Docker 镜像 | 镜像仓库 | 不作为 artifact，直接 push |
| zip/tar 包 | 项目自定义 | 可选上传 |

规则：
- artifact 名稳定：`static-dist`、`python-dist`。
- 保留期短（1~7 天），避免占空间。
- **artifact 不得包含 `.env`、密钥、私钥**。
- 下游 job 用 `download-artifact` 复用，禁止重复构建。

---

## 12. Docker 构建规范

Docker 是**构建目标之一**，不是 CI 的全部。

- **自动搜索 Dockerfile**：`Dockerfile` / `Dockerfile.*` / `*.Dockerfile`，根或子目录取最浅。
- **构建上下文**：默认 Dockerfile 所在目录，可用 `docker.context` 覆盖。
- **默认单架构 `linux/amd64`**；`linux/arm64` 在 amd64 机器上走 QEMU，极慢，需要时显式开启。
- **应用镜像策略**：
  - `auto`：纯前端且无 Dockerfile → `nginx-prebuilt`；有 Dockerfile → `dockerfile`
  - `dockerfile`：用项目 Dockerfile
  - `nginx-prebuilt`：复用 `dist` + `nginx:alpine`，秒级
  - `none`：不构建
- **镜像标签**：`<ver>-b<build>`、`sha-xxxx`、`<ver>`（tag）、`latest`（main）。
- **Secret 不进 build ARG / 镜像层**。

---

## 13. 静态资源构建规范

- 前端构建一次，产物 `dist/` 供三处复用：
  1. `nginx-prebuilt` 应用镜像
  2. `-assets` 独立镜像（scratch）
  3. Cloudflare Pages
- 静态站点部署属于 **Publish**，只在 tag 或显式开启时执行。
- SPA 需要 `404.html` 回退（`cp index.html 404.html`）。

---

## 14. Publish 规范

Publish 与 CI 分离，包含：

| 目标 | 触发 | 说明 |
|---|---|---|
| Docker 镜像推送 | `v*` tag（推荐）/ main（快照） | 先 build & push，失败则整个发布失败 |
| Cloudflare Pages | `v*` tag / main | `wrangler pages deploy` |
| GitHub Release | `v*` tag | 自动生成变更说明 |

原则：
- **Publish 必须 `needs` CI 成功**。
- 发布失败不能标记为成功；不要 `continue-on-error`。
- Docker build 成功但 push 失败 → job 失败，Release 不创建。

---

## 15. Pull Request 流程

```text
checkout → install → lint → typecheck → test → build
          （不 push 镜像、不部署、不发 Release）
```

- 触发：`pull_request` 到 `main`。
- 不读取发布 Secret（fork PR 尤其注意）。
- `concurrency` 取消同一 PR 的旧运行。

---

## 16. Main 分支流程

```text
install → lint → typecheck → test → build
   ↓
（可选）构建快照镜像 :latest / :sha / :X.Y.Z-bN
   ↓
（可选）部署预览环境
```

- 推荐：main 只做 CI + 快照镜像，**不做正式发布**。
- 正式发布交给 tag，避免每次合并都上线。

---

## 17. Release 流程

```text
v* tag
  ↓
完整测试 + 完整构建
  ↓
Docker build & push
  ↓
Cloudflare deploy
  ↓
GitHub Release
```

- 版本号来自 tag（见 §21）。
- 发布顺序：镜像 → 静态 → Release；任一步失败即停。
- 可用 `environment: production` 加人工审批。

---

## 18. Secret 管理

- 只放 **GitHub Secrets**，禁止入库。
- 生产密钥通过 `*_FILE` + Docker secrets 挂载（fastapi 已验证）。
- 不在 `run:` 中 `echo` Secret；GitHub 会自动打码，但不要主动拼接。
- 不使用 `build-arg` 传密钥（会进镜像历史）。
- Artifact 上传前检查是否含 `.env` / `*.pem` / `*.key`。

---

## 19. Cache

| 缓存 | 是否统一 | 做法 |
|---|---|---|
| npm / pnpm / yarn | ✅ | `actions/setup-node` 的 `cache` + `cache-dependency-path` |
| uv / pip | ✅ | `astral-sh/setup-uv` 或 `uv cache`；pip cache |
| Docker layer | ✅ | `cache-from/to: type=gha` |
| 构建产物 | ❌ 不跨 job 缓存 | 用 artifact 传递 |
| 项目自定义缓存 | ❌ 项目自定 | 不要为了缓存而缓存 |

规则：缓存 key 必须包含锁文件哈希；无锁文件时不要开启 npm 缓存（会报错）。

---

## 20. Failure / Retry

| 场景 | 结果 | 处理 |
|---|---|---|
| install 失败 | 停止 | 修依赖/锁文件 |
| lint / typecheck 失败 | 停止 | 修代码；不要盲目 `continue-on-error` |
| test 失败 | 停止 | 不构建、不发布 |
| build 失败 | 停止 | 不发布 |
| docker build 成功、push 失败 | job 失败 | 重试 push / 检查凭证；Release 不创建 |
| 发布失败 | 不能标记成功 | 修复后重新打 tag 或手动重跑 |

重试原则：**只对网络/登录类瞬时失败重试**（push、login、下载），不要自动重试测试。

---

## 21. Version

单一事实来源：**Git tag `vX.Y.Z`**。

| 概念 | 来源 | 示例 |
|---|---|---|
| 语义版本 | git tag | `1.4.2` |
| 构建号 | `github.run_number` | `128` |
| 完整构建版本 | `<版本>-b<构建号>` | `1.4.2-b128` |
| 回滚锚点 | commit sha | `sha-a1b2c3d` |

- `package.json` / `pyproject.toml` 的 version 只作本地参考，发布前用脚本与 tag 对齐。
- 禁止出现 package=1.0.1 / Docker=1.0.2 / tag=v1.0.3。

---

## 22. 新项目接入 Checklist

```text
□ 1. 创建仓库
□ 2. 实现项目自己的 install / lint / test / build（npm/pytest/Makefile 任一）
□ 3. bash install.sh <项目>           # 复制公共模板到 .ci/ 与 ci-cd.yml
□ 4. 编辑 .ci/project.config.yaml     # 类型、命令、docker/static 开关
□ 5. 配置 GitHub Secrets（DOCKER_* / CLOUDFLARE_*）
□ 6. git push                         # PR 触发 CI
□ 7. 打 tag v0.1.0 && push --tags     # 触发构建 + 发布
```

目标：新项目 30 分钟内接入，不重新设计 workflow。

---

## 23. FAQ

**Q：所有项目共用一个 workflow 吗？**
A：共用**一套模板**，通过配置和项目入口适配差异；不是所有项目完全一样。

**Q：一定要写 Makefile 吗？**
A：不强制。推荐 `.ci/ci.sh`（零依赖、跨平台）；有 Makefile 的项目可设 `entry: make` 自动适配。

**Q：前端在子目录怎么办？**
A：探测脚本会自动定位 `frontend/`、`web/`、`client/`，并在该目录执行命令。

**Q：没有测试的项目能接入吗？**
A：能。没有测试就跳过 test 阶段，但仍建议至少加 lint 或构建校验。

**Q：Docker 构建太慢？**
A：默认单架构 + 前端用 `nginx-prebuilt` 复用 `dist`，通常从 10+ 分钟降到 1~2 分钟。

**Q：发布可以手动吗？**
A：可以。`workflow_dispatch` 手动触发，或只打 tag 触发。

---

# 附录 A：6 个关键架构问题（明确结论）

### 问题 1：每项目维护 workflow / 共享一个 / 公共 workflow + 配置？

**结论：公共 workflow + 项目配置 + 项目入口。**

- 每项目维护 workflow：重复、易漂移，否决。
- 所有项目完全一样：无法适配多技术栈，否决。
- 公共模板 + 配置 + `.ci/ci.sh`：维护一份，项目只声明差异，采用。

### 问题 2：统一提供 `make test/build/lint` 还是 `scripts/`？

**结论：优先 `.ci/ci.sh`；Makefile 作为可选适配。**

- `make` 依赖环境（Windows 默认没有），不作为唯一入口。
- `.ci/ci.sh` 随模板安装、零依赖、可直接本地运行。
- 已有 Makefile 的项目设 `ci.entry: make`，无需改造。

### 问题 3：Actions 只调用 `make ci` 还是直接 `pytest`/`npm test`？

**结论：只调用项目统一入口（`.ci/ci.sh <stage>`），不写死具体命令。**

- 写死命令无法跨技术栈复用。
- 统一入口把“怎么做”留给项目，Actions 只负责阶段编排。

### 问题 4：Docker Hub / Cloudflare 属于 CI 还是 CD？

**结论：属于 CD / Publish，不属于 CI。**

- CI = install/lint/typecheck/test/build。
- Publish = docker push / cloudflare deploy / release，只在 tag（或显式开关）执行，且 `needs` CI 成功。

### 问题 5：test → build → publish 还是 lint/test/build/publish？

**结论：`install → lint → typecheck → test → build → (package) → publish`。**

- 逻辑阶段分离；GitHub Actions 里默认合并为一个 `ci` job（共享依赖，快），`build` 独立 job 产出 artifact，`publish` 独立 job 且依赖成功。
- 大项目可把 lint/test 拆成并行 job，但不要牺牲“测试通过才构建”。

### 问题 6：如何既不改 workflow 又支持不同技术栈？

**最终架构**：

```text
.github/workflows/ci-cd.yml        公共编排（只调用 .ci/ci.sh）
        │
        ▼
.ci/ci.sh <stage>                  统一入口（解析顺序：配置→脚本→make→内置）
        │
        ├── project.config.yaml    项目声明（ci.* 命令、docker/static 开关）
        ├── .ci/stages/*.sh        项目自定义阶段（可选）
        ├── Makefile               项目统一入口（可选）
        └── package.json/pyproject 内置探测兜底
```

新项目只做：实现自己的 test/build → 填少量配置 → 复制模板 → push。

---

# 附录 B：命令解析顺序（`.ci/ci.sh` 实现）

```text
for stage in install lint typecheck test build:
    1. ci.<stage> 非空          → 直接执行该命令
    2. .ci/stages/<stage>.sh    → bash 执行
    3. Makefile 有 <stage>:     → make <stage>（entry=auto/make）
    4. 内置探测                  → npm/pnpm/yarn/uv/pytest/ruff/tsc
```

内置探测只在项目确实声明了对应工具时执行（例如有 `.ruff.toml` 才跑 ruff，有 `lint` 脚本才跑 npm lint），避免无配置项目被误判失败。

---

# 附录 C：三种项目接入示例

### C1. Python / FastAPI（uv + pytest + Docker）

```yaml
project: { type: backend }
ci:
  entry: auto
docker:
  registry: registry.cn-hangzhou.aliyuncs.com
  image: namespace/fastapi_tuiwen
  app_strategy: dockerfile
enable: { docker_app: true, docker_assets: false, static_cloudflare: false }
```

内置即可：`uv sync` / `pytest` / `uv build` / `docker build`。

### C2. Vue / Vite（静态 + Cloudflare + 可选 nginx 镜像）

```yaml
project: { type: frontend }
docker:
  registry: docker.io
  image: namespace/vue_tuiwen
  platforms: linux/amd64
  app_strategy: nginx-prebuilt
static:
  build_command: npm run build
  output_dir: dist
enable: { docker_app: true, docker_assets: false, static_cloudflare: true }
cloudflare: { project: tuiwen }
```

### C3. 只有构建、不发布（库/工具）

```yaml
project: { type: backend }
ci:
  entry: make
docker: { app_strategy: none }
enable: { docker_app: false, docker_assets: false, static_cloudflare: false }
```

`make lint / make test / make build` 由项目自己实现。
