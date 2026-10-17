#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从正/侧/后三视图提取轮廓剖面，供程序化建模数据驱动使用"""
from PIL import Image
import numpy as np, json, os

VIEWS = '/workspace/character-3d/views'
OUT = '/root/.codebuddy/artifact/whalegirl/profile.json'
N = 120  # 采样层数


def load(fn):
    im = Image.open(os.path.join(VIEWS, fn)).convert('RGB')
    a = np.array(im).astype(np.float32)
    gray = a.mean(axis=2)
    mask = gray < 244          # 非白像素
    return a, mask


def bbox(mask):
    ys, xs = np.where(mask)
    return int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())


def intervals(row, gap=12, minw=16):
    idx = np.where(row)[0]
    if len(idx) == 0:
        return []
    out = []
    s = p = int(idx[0])
    for i in idx[1:]:
        i = int(i)
        if i - p > gap:
            out.append((s, p))
            s = i
        p = i
    out.append((s, p))
    return [(a, b) for a, b in out if b - a >= minw]


def sample_profile(mask, ytop, ybot, N):
    """v=0 脚底 -> v=1 头顶，返回每层的外轮廓与分段"""
    H = ybot - ytop
    res = []
    for k in range(N):
        v = k / (N - 1)
        y = int(round(ybot - v * H))
        y = max(ytop, min(ybot, y))
        # 取该行附近 3 行做稳健统计
        sl = mask[max(ytop, y - 1):min(ybot, y + 2)]
        row = sl.any(axis=0) if sl.size else mask[y]
        parts = intervals(row)
        if parts:
            l = min(p[0] for p in parts)
            r = max(p[1] for p in parts)
            cx = (l + r) / 2.0
            hw = (r - l) / 2.0
        else:
            cx, hw, parts = 0.0, 0.0, []
        res.append({'v': round(v, 4), 'cx': round(cx, 2), 'hw': round(hw, 2),
                    'np': len(parts), 'parts': [[int(a), int(b)] for a, b in parts]})
    return res


def main():
    data = {}
    boxes = {}
    for name, fn in [('front', 'front.png'), ('side', 'side.png'), ('back', 'back.png')]:
        a, mask = load(fn)
        yt, yb, xl, xr = bbox(mask)
        boxes[name] = dict(ytop=yt, ybot=yb, xleft=xl, xright=xr,
                           w=xr - xl + 1, h=yb - yt + 1)
        print(f'{name:6s} bbox y[{yt},{yb}] x[{xl},{xr}]  size {xr-xl+1} x {yb-yt+1}')

    # 统一垂直范围，保证三视图纵向对齐
    ytop_c = min(b['ytop'] for b in boxes.values())
    ybot_c = max(b['ybot'] for b in boxes.values())
    print(f'common vertical range: {ytop_c} .. {ybot_c}  (h={ybot_c-ytop_c+1})')

    for name, fn in [('front', 'front.png'), ('side', 'side.png'), ('back', 'back.png')]:
        a, mask = load(fn)
        data[name] = sample_profile(mask, ytop_c, ybot_c, N)

    json.dump({'boxes': boxes, 'common': {'ytop': ytop_c, 'ybot': ybot_c,
                                          'h': ybot_c - ytop_c + 1}, 'N': N,
               'profile': data}, open(OUT, 'w'))
    print('saved', OUT)

    # 打印抽样剖面，便于人工判读
    print('\n v     | front: hw  np | side: hw  np | back: hw  np')
    for k in range(0, N, 4):
        f, s, b = data['front'][k], data['side'][k], data['back'][k]
        print(f"{f['v']:.3f} | {f['hw']:7.1f} {f['np']:2d} | "
              f"{s['hw']:7.1f} {s['np']:2d} | {b['hw']:7.1f} {b['np']:2d}")


if __name__ == '__main__':
    main()
