#!/usr/bin/env python3
# 离线渲染检查图：全部模型 6 角度 + 每图层 4 角度（软件光栅化，painter's algorithm）
import json, math
import numpy as np
from PIL import Image, ImageDraw

DUMP = '/root/.codebuddy/artifact/whalegirl/scene_dump.json'
OUT = '/workspace/character-3d/inspect'
import os
os.makedirs(OUT, exist_ok=True)

data = json.load(open(DUMP))

MAT_COLORS = {
    'skin': (1.00, 0.87, 0.78), 'hairS': (0.42, 0.27, 0.19), 'hair': (0.42, 0.27, 0.19),
    'black': (0.14, 0.14, 0.17), 'blackD': (0.10, 0.10, 0.12), 'gold': (0.91, 0.77, 0.41),
    'red': (0.76, 0.17, 0.17), 'white': (0.97, 0.97, 0.95), 'boot': (0.16, 0.16, 0.19),
    'glove': (0.09, 0.09, 0.10), 'gem': (0.60, 0.37, 0.82), 'blush': (1.0, 0.62, 0.68),
    'earIn': (0.85, 0.66, 0.62), 'eye': (0.55, 0.37, 0.75), 'eyetex': (0.55, 0.37, 0.75),
    'dark': (0.18, 0.12, 0.09), 'mouth': (0.81, 0.42, 0.48), 'ped': (0.87, 0.89, 0.94),
    'custom': (0.70, 0.70, 0.70), 'unknown': (0.70, 0.70, 0.70),
}
LAYER_TINT = {
    'skeleton': (0.55, 0.62, 0.75), 'skin': (1.00, 0.87, 0.78), 'clothes': (0.30, 0.34, 0.44),
    'hair': (0.45, 0.30, 0.20), 'decor': (0.93, 0.78, 0.35), 'none': (0.60, 0.60, 0.60),
}

# 预变换所有 mesh 顶点到世界坐标
# 注意：three.js Matrix4.elements 为列主序，np.reshape(4,4) 后是数学矩阵的转置
# 世界变换（行向量约定）：W = P @ R + t，其中 R = Mtx[:3,:3]，t = Mtx[3,:3]
meshes = []
for m in data['meshes']:
    P = np.asarray(m['pos'], dtype=np.float64).reshape(-1, 3)
    Mtx = np.asarray(m['m'], dtype=np.float64).reshape(4, 4)
    W = P @ Mtx[:3, :3] + Mtx[3, :3]
    if m['idx'] is not None:
        T = np.asarray(m['idx'], dtype=np.int64).reshape(-1, 3)
    else:
        n3 = (len(W) // 3) * 3
        T = np.arange(n3, dtype=np.int64).reshape(-1, 3)
    if m['vc'] is not None or m['mat'] == 'hair':
        col = np.asarray(m['vc'] if m['vc'] else MAT_COLORS['hairS'])
    else:
        col = np.asarray(MAT_COLORS.get(m['mat'], (0.7, 0.7, 0.7)))
    meshes.append({'layer': m['layer'], 'mat': m['mat'], 'W': W, 'T': T, 'col': col})

ALL = np.vstack([mm['W'] for mm in meshes])
center = (ALL.min(0) + ALL.max(0)) / 2.0

def view_dirs():
    def norm(v):
        v = np.asarray(v, float); return v / np.linalg.norm(v)
    return {
        'FRONT':  (norm([0, 0, 1]),  norm([1, 0, 0]),  norm([0, 1, 0])),
        'BACK':   (norm([0, 0, -1]), norm([-1, 0, 0]), norm([0, 1, 0])),
        'SIDE-L': (norm([1, 0, 0]),  norm([0, 0, -1]), norm([0, 1, 0])),
        'SIDE-R': (norm([-1, 0, 0]), norm([0, 0, 1]),  norm([0, 1, 0])),
        'TOP':    (norm([0, 1, 0.001]), norm([1, 0, 0]), norm([0, 0, -1])),
        '3-4':    (norm([1, 0.45, 1]), norm([1, 0, -1]), norm([0, 1, 0])),
        '3-4B':   (norm([-1, 0.45, -1]), norm([-1, 0, 1]), norm([0, 1, 0])),
    }

def render(mesh_list, view, size=(520, 660), pad=28, bg=(255, 255, 255)):
    fwd, right, up = view
    img = Image.new('RGB', size, bg)
    dr = ImageDraw.Draw(img)
    if not mesh_list:
        dr.text((12, 10), 'EMPTY', fill=(150, 60, 60))
        return img
    P = np.vstack([mm['W'] for mm in mesh_list]) - center
    u, v, d = P @ right, P @ up, P @ fwd
    umin, umax, vmin, vmax = u.min(), u.max(), v.min(), v.max()
    span = max(umax - umin, vmax - vmin) * 1.12 or 1.0
    sw, sh = size[0] - 2 * pad, size[1] - 2 * pad
    scale = min(sw / span, sh / span)
    ox = pad + (sw - (umax - umin) * scale) / 2 - umin * scale
    oy = pad + (sh - (vmax - vmin) * scale) / 2 + vmax * scale
    tris = []
    L = fwd * 0.55 + np.asarray([0, 1, 0.45]) * 0.85
    L = L / np.linalg.norm(L)
    for mm in mesh_list:
        W = mm['W'] - center
        uu, vv, dd = W @ right, W @ up, W @ fwd
        px = uu * scale + ox
        py = -vv * scale + oy
        t = mm['T']
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        zc = (dd[a] + dd[b] + dd[c]) / 3.0
        e1 = W[b] - W[a]; e2 = W[c] - W[a]
        n = np.cross(e1, e2)
        nl = np.linalg.norm(n, axis=1, keepdims=True); nl[nl == 0] = 1
        n = n / nl
        # 背面剔除：法线背离相机（与视线同向）的面跳过，消除壳体排序错乱
        vis = (n @ fwd) < 0.05
        if not vis.any():
            continue
        a, b, c, zc = a[vis], b[vis], c[vis], zc[vis]
        n, e1 = n[vis], e1[vis]
        lam = 0.40 + 0.60 * np.clip(n @ L, 0, None)
        rim = 0.10 * np.clip(-(n @ fwd), 0, None)
        sh = np.clip(lam + rim, 0, 1.25)[:, None]
        col = np.clip(mm['col'] * sh, 0, 1)
        cols = (col * 255).astype(np.uint8)
        for i in range(len(a)):
            tris.append((zc[i], px[a[i]], py[a[i]], px[b[i]], py[b[i]], px[c[i]], py[c[i]],
                         int(cols[i, 0]), int(cols[i, 1]), int(cols[i, 2])))
    # painter's algorithm：远的先画（d 小 = 远），近的后画覆盖
    tris.sort(key=lambda t: t[0])
    for t in tris:
        _, x1, y1, x2, y2, x3, y3, r, g, bl = t
        if abs(x1 - x2) + abs(x1 - x3) + abs(y1 - y2) + abs(y1 - y3) < 0.7:
            continue
        dr.polygon([(x1, y1), (x2, y2), (x3, y3)], fill=(r, g, bl))
    return img

def grid(cells, cols, cw, ch, title=None):
    rows = math.ceil(len(cells) / cols)
    top = 46 if title else 0
    sheet = Image.new('RGB', (cols * cw, top + rows * ch), (243, 246, 251))
    dr = ImageDraw.Draw(sheet)
    if title:
        dr.text((14, 12), title, fill=(38, 49, 74))
    for i, (label, im) in enumerate(cells):
        x, y = (i % cols) * cw, top + (i // cols) * ch
        sheet.paste(im, (x, y))
        dr.rectangle([x, y, x + cw - 1, y + ch - 1], outline=(180, 190, 210))
        dr.rectangle([x + 4, y + 4, x + 120, y + 24], fill=(60, 90, 170))
        dr.text((x + 10, y + 8), label, fill=(255, 255, 255))
    return sheet

VD = view_dirs()

# 1) 全模型多角度
views_all = ['FRONT', 'BACK', 'SIDE-L', 'SIDE-R', 'TOP', '3-4', '3-4B']
cells = [(k, render(meshes, VD[k])) for k in views_all]
grid(cells, 4, 520, 660, 'ALL LAYERS - 7 VIEWS (reasonable? silhouette / proportion / connection)').save(f'{OUT}/all_views.png')
print('all_views.png')

# 2) 每层 4 角度
for layer in ['skeleton', 'skin', 'clothes', 'hair', 'decor']:
    sel = [mm for mm in meshes if mm['layer'] == layer]
    ks = ['FRONT', 'SIDE-L', 'BACK', '3-4']
    cells = [(k, render(sel, VD[k])) for k in ks]
    n = len(sel); tn = sum(len(mm['T']) for mm in sel)
    grid(cells, 2, 520, 660, f'LAYER: {layer}  ({n} parts, {tn} tris)').save(f'{OUT}/layer_{layer}.png')
    print(f'layer_{layer}.png  parts={n} tris={tn}')

# 3) 汇总信息
from collections import Counter
c = Counter(mm['layer'] for mm in meshes)
print('layer parts:', dict(c))
print('total tris:', sum(len(mm['T']) for mm in meshes))
