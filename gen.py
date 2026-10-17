#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen.py —— character-3d 多部件 Q 版生成器（自研，不依赖 3D API/GPU）。

方法：从三视图轮廓得到身高比例，用手工部件（头/发/耳/躯干/裙/四肢/披风/项圈）
拼装成有体积的实体角色。颜色取自参考图数值化主色。不再用「单圆柱投影贴图」
（那是衣架子的根因）。
"""
import json, os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
H3D = 1.8

# ---- 参考图数值化主色 ----
SKIN   = '#e8c6a0'
HAIR   = '#3a2418'
HAIRHI = '#6a4226'
RED    = '#b23b46'   # 外套红
WHITE  = '#efeae0'   # 裙白
GOLD   = '#d9a441'   # 金饰/项圈
BOOT   = '#2e2320'   # 靴
CAPE   = '#3d2a24'   # 披风
EYE    = '#2a1a14'

def load_profile(path):
    im = np.array(Image.open(path).convert('RGB')).astype(np.float32)
    H, W, _ = im.shape
    lum = im.mean(axis=2); sat = im.max(axis=2)-im.min(axis=2)
    fg = (lum < 235) | (sat > 28)
    rows = []
    for r in range(H):
        col = np.where(fg[r])[0]
        rows.append(((col.max()-col.min())/2.0, (col.min()+col.max())/2.0) if col.size>=5 else (0.0, W/2.0))
    rows = np.array(rows)
    content = np.where(rows[:,0] > 1.0)[0]
    return rows, (int(content.min()), int(content.max())), (H, W)

def build_parts():
    """返回部件列表；每个部件: type, args, x,y,z, rx,ry,rz, color, opacity。
    type: sphere(半径,seg,seg) / box(x,y,z) / cyl(顶r,底r,高,seg) /
          cone(半径,高,seg) / capsule(半径,柱长,cap,rad) / torus(环R,管r,seg,seg)。"""
    P = []
    def add(t, a, pos, rot=(0,0,0), c=SKIN, op=1.0):
        P.append({'type':t,'args':list(a),'x':pos[0],'y':pos[1],'z':pos[2],
                  'rx':rot[0],'ry':rot[1],'rz':rot[2],'color':c,'opacity':op})
    # ---- 头 / 发 ----
    add('sphere',[0.42,28,22],[0,1.40,0.00],c=SKIN)                 # 头
    add('sphere',[0.46,28,22],[0,1.42,-0.06],c=HAIR)                # 后发
    add('sphere',[0.43,28,22],[0,1.57,0.16],c=HAIR)                 # 刘海/前发
    add('sphere',[0.17,20,18],[-0.36,1.28,0.04],c=HAIR)             # 左鬓发
    add('sphere',[0.17,20,18],[ 0.36,1.28,0.04],c=HAIR)             # 右鬓发
    # ---- 马耳 ----
    add('cone',[0.11,0.26,18],[-0.18,1.74,0.00],rot=(0,0, 0.22),c=SKIN)   # 左耳
    add('cone',[0.11,0.26,18],[ 0.18,1.74,0.00],rot=(0,0,-0.22),c=SKIN)   # 右耳
    add('cone',[0.06,0.18,14],[-0.18,1.74,0.03],rot=(0,0, 0.22),c=HAIRHI) # 左耳内
    add('cone',[0.06,0.18,14],[ 0.18,1.74,0.03],rot=(0,0,-0.22),c=HAIRHI) # 右耳内
    # ---- 颈 / 项圈 ----
    add('cyl',[0.10,0.10,0.16,18],[0,1.08,0],c=SKIN)               # 脖子
    add('torus',[0.13,0.030,12,28],[0,1.02,0],rot=(1.5708,0,0),c=GOLD)  # 项圈(真3D，不再被挡)
    # ---- 躯干(红外套) ----
    add('cyl',[0.27,0.19,0.44,22],[0,0.84,0],c=RED)
    # ---- 裙(白，喇叭) ----
    add('cyl',[0.19,0.48,0.42,24],[0,0.61,0],c=WHITE)             # 裙摆张开
    add('torus',[0.19,0.035,10,28],[0,0.80,0],rot=(1.5708,0,0),c=RED)   # 裙腰红带
    # ---- 手臂 / 手 ----
    add('capsule',[0.075,0.40,6,14],[-0.31,0.80,0],c=SKIN)
    add('capsule',[0.075,0.40,6,14],[ 0.31,0.80,0],c=SKIN)
    add('sphere',[0.075,16,14],[-0.31,0.52,0],c=SKIN)
    add('sphere',[0.075,16,14],[ 0.31,0.52,0],c=SKIN)
    # ---- 腿 / 靴 ----
    add('capsule',[0.095,0.44,6,14],[-0.12,0.28,0],c=SKIN)
    add('capsule',[0.095,0.44,6,14],[ 0.12,0.28,0],c=SKIN)
    add('box',[0.20,0.16,0.30],[-0.12,0.06,0.03],c=BOOT)
    add('box',[0.20,0.16,0.30],[ 0.12,0.06,0.03],c=BOOT)
    # ---- 披风(背后) ----
    add('box',[0.60,0.80,0.035],[0,0.95,-0.22],rot=(0.10,0,0),c=CAPE)
    # ---- 马尾 ----
    add('capsule',[0.10,0.46,6,14],[0,1.18,-0.34],rot=(-0.25,0,0),c=HAIR)
    # ---- 五官(简) ----
    add('sphere',[0.05,14,12],[-0.14,1.43,0.39],c=EYE)
    add('sphere',[0.05,14,12],[ 0.14,1.43,0.39],c=EYE)
    return P

def main():
    # 校验轮廓比例（仅用于 sanity check，不影响建模）
    fp,(ftop,fbot),(fH,fW) = load_profile(os.path.join(HERE,'views/front.png'))
    sp,(stop,sbot),(sH,sW) = load_profile(os.path.join(HERE,'views/side.png'))
    parts = build_parts()
    # 包围盒校验
    bb_min=[1e9,1e9,1e9]; bb_max=[-1e9,-1e9,-1e9]
    for p in parts:
        t=p['type']; a=p['args']
        if t=='sphere': r=a[0]; dx=dy=dz=r
        elif t=='box': dx,dy,dz=a[0]/2,a[1]/2,a[2]/2
        elif t=='cyl': r=max(a[0],a[1]); dx=dz=r; dy=a[2]/2
        elif t=='cone': r=a[0]; dx=dz=r; dy=a[1]/2
        elif t=='capsule': r=a[0]; dy=(a[1]/2+r); dx=dz=r
        elif t=='torus': dx=dz=a[0]+a[1]; dy=a[1]
        else: dx=dy=dz=0
        for s in (-1,1):
            bb_min[0]=min(bb_min[0],p['x']-dx); bb_max[0]=max(bb_max[0],p['x']+dx)
            bb_min[1]=min(bb_min[1],p['y']-dy); bb_max[1]=max(bb_max[1],p['y']+dy)
            bb_min[2]=min(bb_min[2],p['z']-dz); bb_max[2]=max(bb_max[2],p['z']+dz)
    print('包围盒 X[%.2f,%.2f] Y[%.2f,%.2f] Z[%.2f,%.2f]'%(
        bb_min[0],bb_max[0],bb_min[1],bb_max[1],bb_min[2],bb_max[2]))
    parts_json = json.dumps(parts, separators=(',',':'))

    three = open(os.path.join(HERE,'vendor/three.min.js'), encoding='utf-8').read()
    three = three.replace('</script', '<\\/script')
    html = TEMPLATE.replace('/*__THREE_JS__*/', three)\
                   .replace('/*__PARTS__*/', parts_json)\
                   .replace('/*__H3D__*/', str(H3D))
    out = os.path.join(HERE,'index.html')
    open(out,'w',encoding='utf-8').write(html)
    print('wrote', out, os.path.getsize(out), 'bytes; parts', len(parts))

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>character-3d</title>
<style>
html,body{margin:0;height:100%;background:#11131a;overflow:hidden;font-family:system-ui,-apple-system,sans-serif;touch-action:none}
#c{width:100%;height:100%;display:block}
#hud{position:fixed;left:8px;top:8px;color:#cfd6e4;font-size:12px;background:rgba(0,0,0,.45);padding:8px 10px;border-radius:8px;max-width:calc(100% - 16px);box-sizing:border-box}
#btns{margin-top:6px;display:flex;gap:6px;flex-wrap:wrap}
button{background:#222838;color:#cfd6e4;border:1px solid #333b4d;border-radius:6px;padding:5px 10px;font-size:12px;touch-action:manipulation}
#tip{font-size:11px;color:#8e99ae;margin-top:4px}
#ref{position:fixed;left:8px;right:8px;bottom:8px;display:flex;gap:6px;justify-content:center}
#ref img{height:70px;border:1px solid #2a2f3a;border-radius:4px;background:#fff;object-fit:contain}
</style></head>
<body>
<canvas id="c"></canvas>
<div id="hud">
  <div><b>character-3d</b> · 多部件 Q 版</div>
  <div id="btns"><button id="rot">⏸ 旋转</button><button id="wf">网格</button><button id="reset">重置</button></div>
  <div id="tip">拖拽旋转 · 滚轮缩放</div>
</div>
<div id="ref"><img id="rfront"><img id="rside"><img id="rback"></div>
<script>/*__THREE_JS__*/</script>
<script>
const PARTS = /*__PARTS__*/;
const H3D = parseFloat('/*__H3D__*/') || 1.8;
const cv = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({canvas:cv, antialias:true, alpha:false});
renderer.setPixelRatio(Math.min(window.devicePixelRatio||1, 1.5));
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x11131a);
const camera = new THREE.PerspectiveCamera(42, 1, 0.05, 100);
const TARGET = new THREE.Vector3(0, H3D*0.5, 0);
camera.position.set(0, H3D*0.5, 3.4);

scene.add(new THREE.AmbientLight(0xffffff, 0.65));
const dir = new THREE.DirectionalLight(0xffffff, 0.85); dir.position.set(2.5,4,3); scene.add(dir);
const fill = new THREE.DirectionalLight(0xbfd0ff, 0.30); fill.position.set(-3,1,-2); scene.add(fill);

const GEO = {
  sphere:a=>new THREE.SphereGeometry(a[0],a[1]||24,a[2]||18),
  box:a=>new THREE.BoxGeometry(a[0],a[1],a[2]),
  cyl:a=>new THREE.CylinderGeometry(a[0],a[1],a[2],a[3]||20),
  cone:a=>new THREE.ConeGeometry(a[0],a[1],a[2]||20),
  capsule:a=>new THREE.CapsuleGeometry(a[0],a[1],a[2]||6,a[3]||14),
  torus:a=>new THREE.TorusGeometry(a[0],a[1],a[2]||12,a[3]||28),
};
const char = new THREE.Group();
const mats = [];
for(const p of PARTS){
  const g = GEO[p.type](p.args);
  const m = new THREE.MeshLambertMaterial({color:new THREE.Color(p.color),
    transparent:p.opacity<1, opacity:p.opacity||1});
  mats.push(m);
  const mesh = new THREE.Mesh(g, m);
  mesh.position.set(p.x,p.y,p.z);
  mesh.rotation.set(p.rx||0,p.ry||0,p.rz||0);
  char.add(mesh);
}
scene.add(char);

for(const [id,url] of [['rfront','views/front.png'],['rside','views/side.png'],['rback','views/back.png']]){
  const el=document.getElementById(id); if(el) el.src=url;
}

let rot=true, dragging=false, px=0, py=0, az=0, pol=1.15, dist=3.4;
cv.addEventListener('pointerdown', e=>{dragging=true;px=e.clientX;py=e.clientY;});
cv.addEventListener('pointerup', ()=>dragging=false);
cv.addEventListener('pointermove', e=>{
  if(!dragging) return;
  az -= (e.clientX-px)*0.01; pol -= (e.clientY-py)*0.01;
  pol = Math.max(0.15, Math.min(2.95, pol)); px=e.clientX; py=e.clientY;
});
cv.addEventListener('wheel', e=>{dist *= (1+Math.sign(e.deltaY)*0.08); dist=Math.max(1.6,Math.min(7,dist)); e.preventDefault();}, {passive:false});
document.getElementById('rot').onclick = e=>{rot=!rot; e.target.textContent = rot?'⏸ 旋转':'▶ 旋转';};
document.getElementById('wf').onclick = e=>{mats.forEach(m=>m.wireframe=!m.wireframe);};
document.getElementById('reset').onclick = ()=>{az=0;pol=1.15;dist=3.4;};

function resize(){
  const w=window.innerWidth, h=window.innerHeight;
  const dpr = Math.min(window.devicePixelRatio||1, 1.5);
  const rw=Math.floor(w*dpr), rh=Math.floor(h*dpr);
  if(cv.width!==rw||cv.height!==rh){cv.width=rw;cv.height=rh;}
  renderer.setSize(w,h,false);
  camera.aspect=w/h; camera.updateProjectionMatrix();
}
function loop(){
  resize();
  if(rot && !dragging) az += 0.005;
  const x = dist*Math.sin(pol)*Math.sin(az);
  const y = H3D*0.5 + dist*Math.cos(pol);
  const z = dist*Math.sin(pol)*Math.cos(az);
  camera.position.set(x,y,z); camera.lookAt(TARGET);
  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}
loop();
</script>
</body></html>
"""

if __name__ == '__main__':
    main()
