#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成投影贴图素材 + 归一化剪影剖面。

对齐策略：三视图源图各自取景不同（脚底/头顶位置不一致），
因此每个视图按「自身内容包围盒」归一化：脚底=v0，头顶=v1，水平居中。
这样三者在同一归一化坐标系下对齐，可直接用于投影贴图与剪影放样。
"""
from PIL import Image
import numpy as np, json, os

VIEWS = '/workspace/character-3d/views'
OUTDIR = '/workspace/character-3d/proj'
N = 160            # 剖面层数
TARGET_H = 1024    # 输出贴图统一高度

os.makedirs(OUTDIR, exist_ok=True)


def content_bbox(a):
    """稳健前景包围盒：非白像素（阈值 244），忽略孤立抗锯齿点"""
    gray = a.mean(axis=2)
    mask = gray < 244
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return None
    # 去掉极端离群：用分位数裁剪，避免单个抗锯齿像素撑大包围盒
    y0, y1 = np.percentile(ys, 0.1), np.percentile(ys, 99.9)
    x0, x1 = np.percentile(xs, 0.1), np.percentile(xs, 99.9)
    return int(y0), int(y1), int(x0), int(x1)


def intervals(row, gap=10, minw=14):
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


def build(name, fn):
    im = Image.open(os.path.join(VIEWS, fn)).convert('RGB')
    a = np.array(im).astype(np.float32)
    yt, yb, xl, xr = content_bbox(a)
    crop = im.crop((xl, yt, xr + 1, yb + 1))
    cw, ch = crop.size
    # 统一高度，保持宽高比
    nh = TARGET_H
    nw = max(1, int(round(cw * nh / ch)))
    crop = crop.resize((nw, nh), Image.LANCZOS)
    crop.save(os.path.join(OUTDIR, f'{name}.png'))
    print(f'{name:6s} 源bbox y[{yt},{yb}] x[{xl},{xr}] -> 裁剪 {cw}x{ch} -> 输出 {nw}x{nh}')

    # 在归一化后的图上计算剪影剖面
    arr = np.array(crop).astype(np.float32)
    mask = arr.mean(axis=2) < 244
    W, H = nw, nh
    prof = []
    for k in range(N):
        v = k / (N - 1)                     # v=0 脚底, v=1 头顶
        y = int(round((H - 1) * (1 - v)))   # 图像 y 向下，脚底在下
        y = max(0, min(H - 1, y))
        sl = mask[max(0, y - 1):min(H, y + 2)]
        row = sl.any(axis=0) if sl.size else mask[y]
        parts = intervals(row)
        if parts:
            l = min(p[0] for p in parts)
            r = max(p[1] for p in parts)
            cx = (l + r) / 2.0 / W          # 归一化中心 [0,1]
            hw = (r - l) / 2.0 / W          # 归一化半宽
        else:
            cx, hw = 0.5, 0.0
        prof.append({'v': round(v, 4), 'cx': round(cx, 4), 'hw': round(hw, 4),
                     'np': len(parts)})
    return {'src_bbox': [yt, yb, xl, xr], 'out_size': [nw, nh],
            'aspect': round(nw / nh, 4), 'profile': prof}


def main():
    meta = {}
    for name, fn in [('front', 'front.png'), ('side', 'side.png'), ('back', 'back.png')]:
        meta[name] = build(name, fn)
    json.dump({'N': N, 'target_h': TARGET_H, 'views': meta},
              open(os.path.join(OUTDIR, 'proj_meta.json'), 'w'))
    print('\n已保存:', os.path.join(OUTDIR, 'proj_meta.json'))

    print('\n v     | front hw | side hw | back hw | 说明')
    for k in range(0, N, 8):
        f = meta['front']['profile'][k]
        s = meta['side']['profile'][k]
        b = meta['back']['profile'][k]
        print(f"{f['v']:.3f} | {f['hw']:8.4f} | {s['hw']:7.4f} | {b['hw']:7.4f} |")


if __name__ == '__main__':
    main()
