# CI/CD 用户自定义钩子（扩展点）

本目录下的脚本为**可选扩展点**：公共工作流（`ci-cd.yml` 及模块化工作流）会在对应阶段自动调用它们，
**仅当文件存在时才执行**，因此不会破坏任何项目的既有流程。新项目只需按需创建对应文件并填入命令即可。

| 钩子文件 | 触发阶段 | 典型用途 |
|---|---|---|
| `ci.sh` | CI（lint/test 之后） | 项目专属静态检查、类型检查、契约测试 |
| `pre-build.sh` | 镜像构建**前**（docker-app / docker-assets） | 生成版本文件、拉取私有依赖、注入构建参数 |
| `post-build.sh` | 镜像构建推送**后** | 镜像漏洞扫描(trivy)、推送 SBOM、通知 |
| `pre-deploy.sh` | 部署**前**（Cloudflare） | 备份、预检、占位 |
| `post-deploy.sh` | 部署**后**（Cloudflare） | 刷新 CDN 缓存、健康检查、钉钉/邮件通知 |

## 约定

- 脚本首行建议 `#!/usr/bin/env bash` 并以 `set -euo pipefail` 开头；返回非 0 会**阻断**该阶段。
- 可用环境变量（由工作流注入）：
  - `PROJECT_TYPE`： `backend` / `frontend` / `fullstack` / `unknown`
  - `IS_BACKEND` / `IS_FRONTEND`： `true`/`false`
  - `IMAGE_TAGS`：本次构建的镜像标签列表（构建类钩子）
  - `DEPLOY_URL`：Cloudflare 部署后的预览/生产地址（部署类钩子）
- 工作流通过 `bash hooks/<name>.sh` 调用，因此脚本需有读权限（无需可执行位）。

> 这些钩子是「预留的用户自定义步骤」：公共模板本身不实现任何业务命令，全部留给项目填充。
