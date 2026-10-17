#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多部件模型自检：从 index.html 提取 PARTS，校验件数、包围盒、颜色有效性。"""
import re, json, sys

html = open('index.html', encoding='utf-8').read()
m = re.search(r'const PARTS = (\[.*?\]);', html, re.S)
if not m:
    print('❌ 未找到 PARTS'); sys.exit(1)
parts = json.loads(m.group(1))
print('部件数:', len(parts))

bb = [[1e9,1e9,1e9],[-1e9,-1e9,-1e9]]
def ext(p):
    t=p['type']; a=p['args']
    if t=='sphere': return [a[0]]*3
    if t=='box': return [a[0]/2,a[1]/2,a[2]/2]
    if t=='cyl': return [max(a[0],a[1]),a[2]/2,max(a[0],a[1])]
    if t=='cone': return [a[0],a[1]/2,a[0]]
    if t=='capsule': return [a[0],a[1]/2+a[0],a[0]]
    if t=='torus': return [a[0]+a[1],a[0]+a[1],a[1]]
    return [0,0,0]
for p in parts:
    d=ext(p)
    for i,k in enumerate(('x','y','z')):
        bb[0][i]=min(bb[0][i], p[k]-d[i])
        bb[1][i]=max(bb[1][i], p[k]+d[i])
    if not re.match(r'^#[0-9a-fA-F]{6}$', p['color']):
        print('❌ 颜色格式错误', p['color']); sys.exit(1)

h = bb[1][1]-bb[0][1]; w = bb[1][0]-bb[0][0]
print(f'包围盒 X[{bb[0][0]:.2f},{bb[1][0]:.2f}] Y[{bb[0][1]:.2f},{bb[1][1]:.2f}] Z[{bb[0][2]:.2f},{bb[1][2]:.2f}]')
print(f'高度={h:.2f} 宽={w:.2f}')
if len(parts) < 15:
    print('❌ 部件过少'); sys.exit(1)
if not (1.2 <= h <= 3.0):
    print('❌ 高度超范围'); sys.exit(1)
if w > 1.6:
    print('❌ 太宽'); sys.exit(1)
print('✅ 自检通过')
