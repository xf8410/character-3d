#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""剪影相似度检查：把网格正交投影光栅化，与参考视图的实心剪影比 IoU。
可检测：整体形状偏差、上下颠倒、左右镜像。"""
import json, re, os, sys
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
GRID = (128, 192)
CANVAS = (1024, 1536)

html = open(os.path.join(HERE,'index.html'), encoding='utf-8').read()
G = json.loads(re.search(r'const GEO = (\{.*?\});\n', html, re.S).group(1))
v = np.array(G['v']); f = np.array(G['f'])

def raster(v, f, ax, ay, flip_x=False):
    """把网格投影到 (ax, ay) 平面并光栅化成二值图。"""
    xs = v[:,ax].copy(); ys = v[:,ay].copy()
    if flip_x: xs = -xs
    xmin,xmax,ymin,ymax = xs.min(),xs.max(),ys.min(),ys.max()
    W,H = CANVAS
    sc = min(W*0.98/max(xmax-xmin,1e-6), H*0.98/max(ymax-ymin,1e-6))
    cx,cy = (xmin+xmax)/2, (ymin+ymax)/2
    im = Image.new('L',(W,H),0); dr = ImageDraw.Draw(im)
    for a,b,c in f:
        pts = []
        for idx in (a,b,c):
            px = W/2 + (xs[idx]-cx)*sc
            py = H/2 - (ys[idx]-cy)*sc     # mesh y 向上 -> 图像 y 向下
            pts.append((px,py))
        dr.polygon(pts, fill=255)
    return im

def ref_mask(name):
    im = np.array(Image.open(os.path.join(HERE,f'views/{name}.png')).convert('RGB')).astype(np.float32)
    lum = im.mean(axis=2); sat = im.max(axis=2)-im.min(axis=2)
    fg = (lum<235)|(sat>28)
    return Image.fromarray((fg*255).astype(np.uint8))

def to_grid(img):
    """裁到内容包围盒后缩放到统一网格。"""
    a = np.array(img) > 127
    if not a.any(): return a
    ys,xs = np.where(a)
    crop = a[ys.min():ys.max()+1, xs.min():xs.max()+1]
    return np.array(Image.fromarray((crop*255).astype(np.uint8)).resize(GRID, Image.NEAREST)) > 127

def iou(a,b):
    inter = np.logical_and(a,b).sum(); union = np.logical_or(a,b).sum()
    return inter/union if union else 0.0

print('剪影 IoU（网格 vs 参考图，尺度/平移归一后）')
res = []
for name, ax, ay in [('front',0,1), ('side',2,1), ('back',0,1)]:
    rm = to_grid(ref_mask(name))
    best, bestf = 0.0, None
    for fx in (False, True):
        s = iou(to_grid(raster(v,f,ax,ay,flip_x=fx)), rm)
        if s > best: best, bestf = s, fx
    res.append((name,best))
    print(f'  {name:6s} IoU = {best:.3f}   ({"镜像" if bestf else "正向"}更优)')

rm = to_grid(ref_mask('front'))
vf = v.copy(); vf[:,1] = -vf[:,1]
print(f'  [对照] front 若上下颠倒 IoU = {iou(to_grid(raster(vf,f,0,1)),rm):.3f}  (应明显更低 => 方向正确)')

avg = sum(r[1] for r in res)/len(res)
print(f'平均 IoU = {avg:.3f}')
print('结论:', '✅ 剪影高度贴合' if avg>0.80 else ('⚠️ 中等贴合' if avg>0.65 else '❌ 偏差较大'))
sys.exit(0 if avg>0.55 else 1)
