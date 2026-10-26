#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用纯标准库生成在吗 App 的 PNG logo：主题色圆角方底板 + 白色圆环 + 白色对勾。
与 src/static/logo.svg 的视觉保持一致（viewBox 1024）。不依赖任何第三方库。
"""
import math
import struct
import zlib

SIZE = 1024
THEME = (18, 184, 134)   # #12b886
WHITE = (255, 255, 255)
CORNER = 230.0           # 圆角半径（对应 svg rx=230）

# 圆环（对应 svg circle cx=512 cy=512 r=300 stroke=52）
RING_C = (SIZE / 2, SIZE / 2)
RING_R = 300.0
RING_HALF = 26.0         # stroke-width 52 的一半

# 对勾（对应 svg path M314 520 L454 662 L710 366）
CHECK = [(314, 520), (454, 662), (710, 366)]
CHECK_HALF = 37.0        # stroke-width 74 的一半

BLUR = 2.0               # 边缘抗锯齿过渡


def inside_rounded(x, y, w, h, r):
    cx = min(max(x, r), w - r)
    cy = min(max(y, r), h - r)
    dx, dy = x - cx, y - cy
    return (dx * dx + dy * dy) <= r * r


def dist_to_segment(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def clamp01(v):
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


def band_alpha(dist, center, half, blur):
    # 距离中心 center、半宽 half 的带状区域，带模糊边
    a = min(dist - (center - half), (center + half) - dist) / blur
    return clamp01(a)


def check_alpha(x, y):
    best = 0.0
    for i in range(len(CHECK) - 1):
        ax, ay = CHECK[i]
        bx, by = CHECK[i + 1]
        d = dist_to_segment(x, y, ax, ay, bx, by)
        a = (CHECK_HALF - d) / BLUR
        if a > best:
            best = a
    return clamp01(best)


def px(x, y):
    inside = inside_rounded(x, y, SIZE, SIZE, CORNER)
    # 白色叠加强度
    ring_a = band_alpha(math.hypot(x - RING_C[0], y - RING_C[1]), RING_R, RING_HALF, BLUR)
    check_a = check_alpha(x, y)
    white_a = max(ring_a, check_a)
    if not inside:
        if white_a <= 0:
            return (0, 0, 0, 0)
        # 不透明背景外（理论上不会发生），直接白
        return (WHITE[0], WHITE[1], WHITE[2], int(round(white_a * 255)))
    # 在底板内：底色调白色
    r = int(round(THEME[0] * (1 - white_a) + WHITE[0] * white_a))
    g = int(round(THEME[1] * (1 - white_a) + WHITE[1] * white_a))
    b = int(round(THEME[2] * (1 - white_a) + WHITE[2] * white_a))
    return (r, g, b, 255)


def write_png(path, size, rgba):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter type 0
        for x in range(size):
            i = (y * size + x) * 4
            raw += bytes((rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]))
    idat = zlib.compress(bytes(raw), 9)
    with open(path, "wb") as f:
        f.write(sig)
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", idat))
        f.write(chunk(b"IEND", b""))


def write_base64_module(png_bytes):
    import base64
    b64 = base64.b64encode(png_bytes).decode("ascii")
    uri = "data:image/png;base64," + b64
    header = (
        "// 自动生成，勿手改。\n"
        "// 在吗 logo（支付风格 PNG）的 base64 data URI，供小程序 <image> 内联使用，\n"
        "// 避免微信/支付宝小程序对本地绝对路径 /static/... 解析失败的坑（本地图片经常加载不出）。\n"
        "// 如需更新图形，重新运行：python3 scripts/gen_logo_png.py\n"
    )
    with open("src/utils/logo.ts", "w", encoding="utf-8") as f:
        f.write(header)
        f.write("export const LOGO_DATA_URI = ")
        # 拆行，避免单行过长
        chunk = 120
        f.write('"data:image/png;base64," +\n')
        for i in range(0, len(b64), chunk):
            f.write('  "%s" +\n' % b64[i:i + chunk])
        f.write('  "";\n')
    return uri


def main():
    rgba = bytearray(SIZE * SIZE * 4)
    for y in range(SIZE):
        for x in range(SIZE):
            r, g, b, a = px(x, y)
            i = (y * SIZE + x) * 4
            rgba[i] = r
            rgba[i + 1] = g
            rgba[i + 2] = b
            rgba[i + 3] = a

    write_png("src/static/logo.png", SIZE, rgba)
    with open("src/static/logo.png", "rb") as f:
        png_bytes = f.read()
    uri = write_base64_module(png_bytes)
    print("生成 src/static/logo.png (%dx%d) 完成" % (SIZE, SIZE))
    print("生成 src/utils/logo.ts 完成（data URI 长度 %d）" % len(uri))


if __name__ == "__main__":
    main()
