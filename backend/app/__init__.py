"""在吗（ZaiMa）后端应用包。"""

from __future__ import annotations

import os

# 版本号：优先取构建时注入的 APP_VERSION（如 1.0.0），回退到源码默认值。
__version__ = (os.getenv("APP_VERSION") or "1.0.0").strip()

# 构建号：优先 APP_BUILD（CI 可传版本构建号），其次 GIT_SHA（提交哈希），
# 便于线上排查「这个进程到底是哪次构建的」。统一截断为 7 位短号。
__build__ = (os.getenv("APP_BUILD") or os.getenv("GIT_SHA") or "dev").strip()[:7]

# 对外展示用：如 "1.0.0 (build abcd123)"，日志/接口均可直接使用。
__version_full__ = f"{__version__} (build {__build__})"
