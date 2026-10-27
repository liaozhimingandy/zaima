#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_push_image.py -- 参数化镜像构建/推送脚本（公共模板）

 replaces rhapsody/deploy.py 的明文密码写法，改为:
   - 从环境变量/项目配置读取 registry、镜像名、版本
   - docker login 使用 --password-stdin（不回显密码）
   - 自动打 sha / version / latest 三个 tag（与 docker.yml 对齐）

用法:
  export REGISTRY=registry.cn-hangzhou.aliyuncs.com   # Docker Hub 留空 ""
  export DOCKER_USERNAME=liaozhiming                 # 与 GitHub Secrets 同名
  export DOCKER_PASSWORD=<从 GitHub Secrets / 本地安全存储获取>
  export DOCKER_IMAGE=liaozhiming/rhapsody
  export PROJECT_VERSION=7.4.0
  python scripts/build_push_image.py --dockerfile Dockerfile --context .

也可从 project.config.yaml 读取（脚本自动探测）。
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys

try:
    import yaml  # 可选依赖；无则仅用环境变量
except Exception:
    yaml = None


def load_config() -> dict:
    cfg: dict = {}
    # 1) 环境变量优先
    for k in ("REGISTRY", "DOCKER_USERNAME", "DOCKER_PASSWORD",
              "DOCKER_IMAGE", "PROJECT_VERSION", "DOCKERFILE_PATH"):
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    # 2) project.config.yaml 兜底
    p = "project.config.yaml"
    if yaml is not None and os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        d = data.get("docker", {})
        cfg.setdefault("REGISTRY", d.get("registry", ""))
        cfg.setdefault("DOCKER_IMAGE", d.get("image", ""))
        cfg.setdefault("PROJECT_VERSION", (data.get("project", {}) or {}).get("version", ""))
        cfg.setdefault("DOCKERFILE_PATH", d.get("dockerfile", "Dockerfile"))
    return cfg


def run(cmd, **kw):
    print("+ " + " ".join(cmd))
    subprocess.run(cmd, check=True, **kw)


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:
        return "local"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dockerfile", default=None)
    ap.add_argument("--context", default=".")
    args = ap.parse_args()

    cfg = load_config()
    registry = cfg.get("REGISTRY", "")
    image = cfg.get("DOCKER_IMAGE", "")
    version = cfg.get("PROJECT_VERSION", "")
    dockerfile = args.dockerfile or cfg.get("DOCKERFILE_PATH", "Dockerfile")

    if not image:
        print("ERROR: DOCKER_IMAGE 未配置（环境变量或 project.config.yaml）", file=sys.stderr)
        return 2

    full = f"{registry}/{image}".strip("/") if registry else image
    sha = git_sha()
    tags = [f"{full}:sha-{sha}"]
    if version:
        tags.append(f"{full}:{version}")
        tags.append(f"{full}:latest")  # latest 仅本地/默认分支使用

    # 构建（带全部 tag）
    build_cmd = ["docker", "build", "-f", dockerfile]
    for t in tags:
        build_cmd += ["-t", t]
    build_cmd.append(args.context)
    run(build_cmd)

    # 登录（--password-stdin，避免明文）
    user = cfg.get("DOCKER_USERNAME", "")
    token = cfg.get("DOCKER_PASSWORD", "")
    if registry and user and token:
        login = ["docker", "login", registry, "-u", user, "--password-stdin"]
        subprocess.run(login, input=token.encode(), check=True)
        for t in tags:
            run(["docker", "push", t])
        print(f"\npush success -> {full}  tags: {', '.join(tags)}")
    else:
        print(f"\n跳过 push（未配置 registry 凭证）。本地镜像: {', '.join(tags)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
