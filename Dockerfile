# =============================================================================
# Dockerfile —— H5 静态资源镜像（scratch 空根，仅含构建产物）
#
# 这是「最精简的只装了页面」的镜像：最终层 = 空文件系统 + /usr/share/nginx/html，
# 体积几乎等于 H5 产物本身，适合单独分发 / 作为下游 nginx 镜像的数据源。
#
# 关键：本镜像 **不构建** H5，直接 COPY 预构建产物 h5-dist/（避免重复构建）。
#   - CI：先 npm run build:h5 并上传 artifact，镜像作业再下载到 h5-dist/ 后构建。
#   - 本地：npm run build:h5 后，把产物复制到仓库根 h5-dist/：
#       mkdir -p h5-dist && cp -r frontend/dist/build/h5/. h5-dist/
#
# 用法：
#   docker build -f Dockerfile -t zaima-h5-assets .
#   # 提取产物：
#   docker create --name t zaima-h5-assets && docker cp t:/usr/share/nginx/html ./h5 && docker rm t
# =============================================================================
FROM scratch

# 预构建的 H5 产物（由 CI/本地提供）
COPY h5-dist/ /usr/share/nginx/html/

# scratch 无 shell / 无 CMD，仅标注元数据便于检索
LABEL org.opencontainers.image.title="zaima-h5-assets" \
      org.opencontainers.image.description="H5 static assets only (scratch, prebuilt)"
