#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen.py —— character-3d 轮廓放样生成器（自研，无 GPU / 无 3D API）。

方法：从正/侧/背三视图提取真实轮廓（半宽 + 该行中心），放样成闭合实体网格。
关键点：
  1. 环序：索引 0 = 头顶(y=H3D)，N-1 = 脚底(y=0)
  2. 绕序：[a,b,c]/[a,c,d] 得朝外法线（顶穹顶用反向）
  3. 每层轮廓的实际中心偏移烘进几何 => 可表达不对称剪影（马尾后伸等）
  4. UV 在 Python 逐顶点算好（正/侧/背各一套），着色器不再拼 Kf/Ks
  5. 穹顶封口（多环 + 收尖）：闭合、非空心、无长条扇形三角
"""
import json, os, math, base64, io
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
H3D = 1.8
N = 96
M = 64
KDOME = 7
DOME_H = 0.09
SCALE = 0.985
TEX_W, TEX_H = 512, 768

def load_profile(path):
    im = np.array(Image.open(path).convert('RGB')).astype(np.float32)
    H, W, _ = im.shape
    lum = im.mean(axis=2); sat = im.max(axis=2)-im.min(axis=2)
    fg = (lum < 235) | (sat > 28)
    rows = []
    for r in range(H):
        col = np.where(fg[r])[0]
        if col.size < 5:
            rows.append((0.0, W/2.0))
        else:
            rows.append(((col.max()-col.min())/2.0, (col.min()+col.max())/2.0))
    rows = np.array(rows)
    content = np.where(rows[:,0] > 1.0)[0]
    return rows, (int(content.min()), int(content.max())), (H, W)

def resample(rows, top, bot, n):
    ys = np.linspace(top, bot, n)
    hw = np.interp(ys, np.arange(len(rows)), rows[:,0])
    cx = np.interp(ys, np.arange(len(rows)), rows[:,1])
    return ys, hw, cx

def smooth(a, w=5):
    k = np.ones(w)/w
    return np.convolve(np.pad(a,(w//2,w-1-w//2),mode='edge'), k, mode='valid')

def main():
    fp,(ftop,fbot),(fH,fW) = load_profile(os.path.join(HERE,'views/front.png'))
    sp,(stop,sbot),(sH,sW) = load_profile(os.path.join(HERE,'views/side.png'))
    bp,(btop,bbot),(bH,bW) = load_profile(os.path.join(HERE,'views/back.png'))
    charH  = (fbot-ftop)  or 1
    charHs = (sbot-stop)  or 1
    charHb = (bbot-btop)  or 1
    # world -> 像素
    Kf = charH /(H3D*SCALE)
    Ks = charHs/(H3D*SCALE)
    Kb = charHb/(H3D*SCALE)
    # 像素 -> world
    If, Is, Ib = 1.0/Kf, 1.0/Ks, 1.0/Kb

    fys,fhw,fcx = resample(fp,ftop,fbot,N)
    sys_,shw,scx = resample(sp,stop,sbot,N)
    bys,bhw,bcx = resample(bp,btop,bbot,N)
    fhw = np.maximum(smooth(fhw),0.5)
    shw = np.maximum(smooth(shw),0.5)
    bhw = np.maximum(smooth(bhw),0.5)

    y3d = np.linspace(H3D, 0.0, N)     # 0=头顶
    # 每层：半径(世界) 与 中心偏移(世界)
    rf = fhw*If; rs = shw*Is
    xc = (fcx - fW/2)*If
    zc = (scx - sW/2)*Is

    verts, uf, us, ub = [], [], [], []
    def ring(rf_, rs_, xc_, zc_, colf, colb, cols, rowf, rowb, rows_, yy):
        for j in range(M):
            th = 2*math.pi*j/M
            xl = rf_*math.cos(th); zl = rs_*math.sin(th)
            verts.append([xc_+xl, yy, zc_+zl])
            uf.append([(colf + xl*Kf)/fW, rowf/fH])
            ub.append([(colb - xl*Kb)/bW, rowb/bH])
            us.append([(cols + zl*Ks)/sW, rows_/sH])

    for i in range(N):
        ring(rf[i], rs[i], xc[i], zc[i], fcx[i], bcx[i], scx[i],
             fys[i], bys[i], sys_[i], y3d[i])

    # ---- 顶穹顶 ----
    dome, prev = [], 0
    for k in range(1, KDOME):
        phi = (k/KDOME)*(math.pi/2)
        st = len(verts)
        ring(rf[0]*math.cos(phi), rs[0]*math.cos(phi), xc[0], zc[0],
             fcx[0], bcx[0], scx[0], ftop, btop, stop, H3D + DOME_H*math.sin(phi))
        dome.append(st)
    top_tip = len(verts)
    verts.append([xc[0], H3D+DOME_H, zc[0]])
    uf.append([fcx[0]/fW, ftop/fH]); ub.append([bcx[0]/bW, btop/bH]); us.append([scx[0]/sW, stop/sH])

    # ---- 底穹顶 ----
    botr = []
    for k in range(1, KDOME):
        phi = (k/KDOME)*(math.pi/2)
        st = len(verts)
        ring(rf[N-1]*math.cos(phi), rs[N-1]*math.cos(phi), xc[N-1], zc[N-1],
             fcx[N-1], bcx[N-1], scx[N-1], fbot, bbot, sbot, -DOME_H*math.sin(phi))
        botr.append(st)
    bot_tip = len(verts)
    verts.append([xc[N-1], -DOME_H, zc[N-1]])
    uf.append([fcx[N-1]/fW, fbot/fH]); ub.append([bcx[N-1]/bW, bbot/bH]); us.append([scx[N-1]/sW, sbot/sH])

    faces = []
    def quad(A, B, rev=False):
        for j in range(M):
            j2 = (j+1)%M
            a,b,c,d = A+j, A+j2, B+j2, B+j
            if rev: faces.append([a,c,b]); faces.append([a,d,c])
            else:   faces.append([a,b,c]); faces.append([a,c,d])
    for i in range(N-1): quad(i*M, (i+1)*M)
    prev = 0
    for st in dome: quad(prev, st, rev=True); prev = st
    for j in range(M):
        faces.append([prev+j, top_tip, prev+(j+1)%M])
    prev = (N-1)*M
    for st in botr: quad(prev, st); prev = st
    for j in range(M):
        faces.append([prev+j, prev+(j+1)%M, bot_tip])

    # 整体平移到 x/z 居中，便于相机取景（UV 已在局部算好，不受影响）
    V = np.array(verts)
    V[:,0] -= (V[:,0].min()+V[:,0].max())/2
    V[:,2] -= (V[:,2].min()+V[:,2].max())/2
    verts = V.tolist()

    # 压缩体积：坐标/UV 保留 4 位小数（手机端"资源过多"主要来自长浮点数）
    def rnd(a, n=4):
        return [[round(float(x), n) for x in p] for p in a]
    verts = rnd(verts); uf = rnd(uf); us = rnd(us); ub = rnd(ub)

    def resize_tex(p):
        im = Image.open(p).convert('RGB').resize((TEX_W,TEX_H), Image.LANCZOS)
        o = io.BytesIO(); im.save(o,'JPEG',quality=82,optimize=True)
        return 'data:image/jpeg;base64,'+base64.b64encode(o.getvalue()).decode()
    tex = {k: resize_tex(os.path.join(HERE,f'views/{k}.png')) for k in ('front','side','back')}

    geo = {'v':verts,'f':faces,'uf':uf,'us':us,'ub':ub,'H3D':H3D}
    three = open(os.path.join(HERE,'vendor/three.min.js'),encoding='utf-8').read().replace('</script','<\\/script')
    html = TEMPLATE.replace('/*__THREE_JS__*/',three)\
                   .replace('/*__GEO__*/',json.dumps(geo,separators=(',',':')))\
                   .replace('/*__TEX__*/',json.dumps(tex,separators=(',',':')))
    out = os.path.join(HERE,'index.html')
    open(out,'w',encoding='utf-8').write(html)
    print('wrote',out,os.path.getsize(out),'bytes; verts',len(verts),'tris',len(faces))
    print('y %.3f..%.3f  x半宽 %.3f  z半宽 %.3f'%(V[:,1].min(),V[:,1].max(),
          np.abs(V[:,0]).max(),np.abs(V[:,2]).max()))

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
  <div><b>character-3d</b> · 轮廓放样 + 三向投影</div>
  <div id="btns"><button id="rot">⏸ 旋转</button><button id="wf">网格</button><button id="reset">重置</button></div>
  <div id="tip">拖拽旋转 · 滚轮缩放</div>
</div>
<div id="ref"><img id="rfront"><img id="rside"><img id="rback"></div>
<script>/*__THREE_JS__*/</script>
<script>
const GEO = /*__GEO__*/;
const TEX = /*__TEX__*/;
const H3D = GEO.H3D || 1.8;
const cv = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({canvas:cv, antialias:true, alpha:false});
renderer.setPixelRatio(Math.min(window.devicePixelRatio||1, 1.5));
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x11131a);
const camera = new THREE.PerspectiveCamera(42, 1, 0.05, 100);
camera.position.set(0, H3D*0.5, 3.2);

const geo = new THREE.BufferGeometry();
geo.setAttribute('position', new THREE.Float32BufferAttribute(GEO.v.flat(), 3));
geo.setAttribute('aUVf', new THREE.Float32BufferAttribute(GEO.uf.flat(), 2));
geo.setAttribute('aUVs', new THREE.Float32BufferAttribute(GEO.us.flat(), 2));
geo.setAttribute('aUVb', new THREE.Float32BufferAttribute(GEO.ub.flat(), 2));
geo.setIndex(GEO.f.flat());
geo.computeVertexNormals();

function mkTex(url){
  const t = new THREE.Texture();
  const img = new Image();
  img.onload = ()=>{
    t.image = img;
    t.flipY = false;
    t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
    t.minFilter = t.magFilter = THREE.LinearFilter;
    t.generateMipmaps = false;
    t.needsUpdate = true;
  };
  img.src = url; return t;
}
const frontTex = mkTex(TEX.front), sideTex = mkTex(TEX.side), backTex = mkTex(TEX.back);

const mat = new THREE.ShaderMaterial({
  uniforms:{ frontTex:{value:frontTex}, sideTex:{value:sideTex}, backTex:{value:backTex} },
  vertexShader:`
    attribute vec2 aUVf; attribute vec2 aUVs; attribute vec2 aUVb;
    varying vec2 vUf; varying vec2 vUs; varying vec2 vUb; varying vec3 vN;
    void main(){
      vUf = aUVf; vUs = aUVs; vUb = aUVb;
      vN = normalize(normalMatrix * normal);
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
    }`,
  fragmentShader:`
    precision highp float;
    uniform sampler2D frontTex, sideTex, backTex;
    varying vec2 vUf; varying vec2 vUs; varying vec2 vUb; varying vec3 vN;
    void main(){
      vec3 cf = texture2D(frontTex, vUf).rgb;
      vec3 cb = texture2D(backTex,  vUb).rgb;
      vec3 cs = texture2D(sideTex,  vUs).rgb;
      vec3 w = vec3(max(vN.z,0.0), max(-vN.z,0.0), abs(vN.x));
      w = pow(w, vec3(0.75));
      w += 0.06;
      float s = w.x + w.y + w.z;
      vec3 col = (cf*w.x + cb*w.y + cs*w.z) / s;
      float lam = clamp(dot(normalize(vN), normalize(vec3(0.4,0.75,0.55))), 0.0, 1.0);
      col *= (0.72 + 0.42*lam);
      col = pow(col, vec3(0.92));
      gl_FragColor = vec4(col, 1.0);
    }`
});
const mesh = new THREE.Mesh(geo, mat);
scene.add(mesh);

for(const [id,url] of [['rfront',TEX.front],['rside',TEX.side],['rback',TEX.back]]){
  const el=document.getElementById(id); if(el) el.src=url;
}

let rot=true, dragging=false, px=0, py=0, az=0, pol=1.35, dist=3.2;
cv.addEventListener('pointerdown', e=>{dragging=true;px=e.clientX;py=e.clientY;});
cv.addEventListener('pointerup', ()=>dragging=false);
cv.addEventListener('pointermove', e=>{
  if(!dragging) return;
  az -= (e.clientX-px)*0.01; pol -= (e.clientY-py)*0.01;
  pol = Math.max(0.15, Math.min(2.95, pol)); px=e.clientX; py=e.clientY;
});
cv.addEventListener('wheel', e=>{dist *= (1+Math.sign(e.deltaY)*0.08); dist=Math.max(1.4,Math.min(6,dist)); e.preventDefault();}, {passive:false});
document.getElementById('rot').onclick = e=>{rot=!rot; e.target.textContent = rot?'⏸ 旋转':'▶ 旋转';};
document.getElementById('wf').onclick = e=>{mat.wireframe=!mat.wireframe;};
document.getElementById('reset').onclick = ()=>{az=0;pol=1.35;dist=3.2;};

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
  camera.position.set(dist*Math.sin(pol)*Math.sin(az), H3D*0.5+dist*Math.cos(pol), dist*Math.sin(pol)*Math.cos(az));
  camera.lookAt(0,H3D*0.5,0);
  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}
loop();
</script>
</body></html>
"""

if __name__ == '__main__':
    main()
