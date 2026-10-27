# 多阶段构建：最终镜像为 scratch（空根），只携带 H5 静态产物，便于分发/提取
# 用法（仓库根目录执行）：
#   docker build -t zaima-h5 .
#   # 提取静态文件到本地：
#   docker create --name tmp zaima-h5 && docker cp tmp:/app/assets ./h5 && docker rm tmp

# ---------- 构建阶段 ----------
FROM node:22-alpine AS builder
WORKDIR /app

# 先拷贝依赖清单以利用 Docker 层缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# 拷贝前端源码并构建 H5
COPY frontend/ ./
RUN npm run build:h5

# ---------- 产物阶段 ----------
# scratch 是最精简的空镜像，仅用于承载静态资源
FROM scratch
LABEL MAINTAINER="andy<contact@liaozhimingandy>"
COPY --from=builder /app/dist/build/h5 /app/assets
