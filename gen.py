#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen.py —— character-3d 项目的核心生成器（自己从零实现，不依赖任何 3D API / GPU）。

方法学（来自公开资料研究）：
  1. 从正/侧/背三张正交参考图，逐行提取轮廓半宽 (silhouette profile)。
  2. 用「正面半宽 -> X 半径，侧面半宽 -> Z 半径」放样 (loft) 出网格，
     使模型的正视剪影与侧视剪影严格等于原图（这是"像原图"的关键）。
  3. 自定义着色器做三向平面投影 (tri-planar / planar projection)：
     正面图画在 +Z 朝外表面、背面图画在 -Z、侧面图画在 ±X，
     按表面法线加权混合。颜色/五官/金饰/裙褶全部来自原图，不做程序化近似。

输入：views/front.png, views/side.png, views/back.png（干净正交图）
输出：index.html（自包含：内联 three.js；贴图引用 views/*.png）
"""
import json, os, math
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
H3D = 1.8          # 模型总高（单位任意，比例由轮廓决定）
N = 96             # 高度层数
M = 80             # 周向分段
SCALE = 0.985      # 网格略小于轮廓，避免白色描边露出

def load_profile(path):
    """返回每行 (半宽hw, 中心cx) 像素，及内容包围盒 (top,bot) 与 (H,W)。"""
    im = np.array(Image.open(path).convert('RGB')).astype(np.float32)
    H, W, _ = im.shape
    lum = im.mean(axis=2)
    sat = im.max(axis=2) - im.min(axis=2)
    fg = (lum < 235) | (sat > 28)          # 内容（白底上的线稿/上色）
    rows = []
    for r in range(H):
        col = np.where(fg[r])[0]
        if col.size < 5:
            rows.append((0.0, W / 2.0))
        else:
            rows.append(((col.max() - col.min()) / 2.0, (col.min() + col.max()) / 2.0))
    rows = np.array(rows)
    content = np.where(rows[:, 0] > 1.0)[0]
    top, bot = int(content.min()), int(content.max())
    return rows, (top, bot), (H, W)

def resample(rows, top, bot, n):
    ys = np.linspace(top, bot, n)
    hw = np.interp(ys, np.arange(len(rows)), rows[:, 0])
    cx = np.interp(ys, np.arange(len(rows)), rows[:, 1])
    return ys, hw, cx

def main():
    fp, (ftop, fbot), (fH, fW) = load_profile(os.path.join(HERE, 'views/front.png'))
    sp, (stop, sbot), (sH, sW) = load_profile(os.path.join(HERE, 'views/side.png'))
    bp, (btop, bbot), (bH, bW) = load_profile(os.path.join(HERE, 'views/back.png'))

    fys, fhw, fcx = resample(fp, ftop, fbot, N)
    sys_, shw, scx = resample(sp, stop, sbot, N)

    charH = (fbot - ftop) or 1
    charHs = (sbot - stop) or 1
    # 着色器里 vUf=(aCxF + position.x*Kf)/Wf，需让 3D 最宽点映射到原图像素最宽列：
    # Kf = 原图像素半宽 / 3D 最宽半径 = (charH/H3D)/SCALE
    Kf = (charH / H3D) / SCALE   # 正面 3D->像素 横向比例
    Ks = (charHs / H3D) / SCALE  # 侧面

    verts, aRow, aCxF, aCxS = [], [], [], []
    y3d = np.linspace(0, H3D, N)
    for i in range(N):
        xr = fhw[i] * (H3D / charH) * SCALE
        zr = shw[i] * (H3D / charHs) * SCALE
        for j in range(M):
            th = 2 * math.pi * j / M
            x = xr * math.cos(th)
            z = zr * math.sin(th)
            verts.append([x, y3d[i], z])
            aRow.append(float(fys[i])); aCxF.append(float(fcx[i])); aCxS.append(float(scx[i]))
    # 顶/底封口
    top_c = len(verts); verts.append([0, H3D, 0]); aRow.append(float(ftop)); aCxF.append(fW/2); aCxS.append(sW/2)
    bot_c = len(verts); verts.append([0, 0, 0]);    aRow.append(float(fbot)); aCxF.append(fW/2); aCxS.append(sW/2)

    faces = []
    for i in range(N - 1):
        for j in range(M):
            j2 = (j + 1) % M
            a = i * M + j; b = i * M + j2; c = (i + 1) * M + j2; d = (i + 1) * M + j
            faces.append([a, b, c]); faces.append([a, c, d])
    for j in range(M):
        j2 = (j + 1) % M
        faces.append([top_c, j, j2])                     # 顶扇
        faces.append([bot_c, (N - 1) * M + j2, (N - 1) * M + j])  # 底扇

    geo = {
        'v': verts, 'f': faces,
        'aRow': aRow, 'aCxF': aCxF, 'aCxS': aCxS,
        'Wf': fW, 'Hf': fH, 'Ws': sW, 'Hs': sH, 'Kf': Kf, 'Ks': Ks,
        'H3D': H3D,
    }
    geo_json = json.dumps(geo, separators=(',', ':'))

    # 把三视图内联成 base64，避免 GitHub Pages/内嵌浏览器路径或 CORS 问题
    import base64
    def b64_png(path):
        return 'data:image/png;base64,' + base64.b64encode(open(path, 'rb').read()).decode()
    inline = {'front': b64_png(os.path.join(HERE, 'views/front.png')),
              'side':  b64_png(os.path.join(HERE, 'views/side.png')),
              'back':  b64_png(os.path.join(HERE, 'views/back.png'))}
    inline_json = json.dumps(inline, separators=(',', ':'))

    three = open(os.path.join(HERE, 'vendor/three.min.js'), encoding='utf-8').read()
    three = three.replace('</script', '<\\/script')

    html = TEMPLATE.replace('/*__THREE_JS__*/', three)\
                   .replace('/*__GEO__*/', geo_json)\
                   .replace('/*__TEX__*/', inline_json)
    out = os.path.join(HERE, 'index.html')
    open(out, 'w', encoding='utf-8').write(html)
    print('wrote', out, os.path.getsize(out), 'bytes; verts', len(verts), 'tris', len(faces))

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>character-3d · 三视图投影重建</title>
<style>html,body{margin:0;height:100%;background:#11131a;overflow:hidden;font-family:system-ui,sans-serif}
#c{width:100%;height:100%;display:block}
#hud{position:fixed;left:12px;top:12px;color:#cfd6e4;font-size:13px;line-height:1.7;background:rgba(0,0,0,.35);padding:8px 12px;border-radius:8px}
#ref{position:fixed;right:12px;top:12px;display:flex;gap:6px}
#ref img{height:120px;border:1px solid #2a2f3a;border-radius:4px;background:#fff}
button{background:#222838;color:#cfd6e4;border:1px solid #333b4d;border-radius:6px;padding:4px 10px;cursor:pointer;margin-right:6px}
</style></head>
<body>
<canvas id="c"></canvas>
<div id="hud">
  <div><b>三视图投影重建</b>（轮廓放样 + 三向平面投影）</div>
  <div><button id="rot">⏸ 旋转</button><button id="wf">网格</button><button id="reset">重置视角</button></div>
  <div id="tip">拖拽旋转 · 滚轮缩放</div>
</div>
<div id="ref"><img id="rfront"><img id="rside"><img id="rback"></div>
<script>/*__THREE_JS__*/</script>
<script>
const GEO = /*__GEO__*/;
const TEX = /*__TEX__*/;
const H3D = GEO.H3D;
const canvas = document.getElementById('c');

const renderer = new THREE.WebGLRenderer({canvas, antialias:true, alpha:false});
renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x11131a);
const camera = new THREE.PerspectiveCamera(40, canvas.clientWidth/canvas.clientHeight||1, 0.05, 100);
const camTarget = new THREE.Vector3(0, H3D*0.45, 0);
camera.position.set(0, H3D*0.55, 3.2);

// 简单错误兜底：如果 H3D 无效就用默认值
if(!isFinite(H3D)){ alert('渲染数据异常，请重试'); throw new Error('H3D missing'); }

const geo = new THREE.BufferGeometry();
geo.setAttribute('position', new THREE.Float32BufferAttribute(GEO.v.flat(), 3));
geo.setAttribute('aRow', new THREE.Float32BufferAttribute(GEO.aRow, 1));
geo.setAttribute('aCxF', new THREE.Float32BufferAttribute(GEO.aCxF, 1));
geo.setAttribute('aCxS', new THREE.Float32BufferAttribute(GEO.aCxS, 1));
geo.setIndex(GEO.f.flat());
geo.computeVertexNormals();

function mkTex(url){
  const t = new THREE.Texture();
  const img = new Image();
  img.onload = ()=>{ t.image = img; t.flipY = false; t.needsUpdate = true; };
  img.onerror = ()=>{ console.error('tex load failed', url.slice(0,60)); };
  img.src = url;
  return t;
}
const frontTex = mkTex(TEX.front);
const sideTex  = mkTex(TEX.side);
const backTex  = mkTex(TEX.back);

// 把右上角参考图也填上 base64
for(const [id, url] of [['rfront',TEX.front],['rside',TEX.side],['rback',TEX.back]]){
  const el=document.getElementById(id); if(el) el.src=url;
}

const mat = new THREE.ShaderMaterial({
  uniforms:{
    frontTex:{value:frontTex}, sideTex:{value:sideTex}, backTex:{value:backTex},
    Wf:{value:GEO.Wf}, Hf:{value:GEO.Hf}, Ws:{value:GEO.Ws}, Hs:{value:GEO.Hs},
    Kf:{value:GEO.Kf}, Ks:{value:GEO.Ks}
  },
  vertexShader:`
    attribute float aRow; attribute float aCxF; attribute float aCxS;
    uniform float Wf,Hf,Ws,Hs,Kf,Ks;
    varying vec2 vUf; varying vec2 vUb; varying vec2 vUs; varying vec3 vN;
    void main(){
      vUf = vec2((aCxF + position.x*Kf)/Wf, aRow/Hf);
      vUb = vec2((aCxF - position.x*Kf)/Wf, aRow/Hf);
      vUs = vec2((aCxS + position.z*Ks)/Ws, aRow/Hs);
      vN = normalize(normalMatrix * normal);
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
    }`,
  fragmentShader:`
    precision highp float;
    uniform sampler2D frontTex, sideTex, backTex;
    varying vec2 vUf; varying vec2 vUb; varying vec2 vUs; varying vec3 vN;
    void main(){
      vec3 cf = texture2D(frontTex, vUf).rgb;
      vec3 cb = texture2D(backTex, vUb).rgb;
      vec3 cs = texture2D(sideTex, vUs).rgb;
      float wf = max(0.0, vN.z);
      float wb = max(0.0, -vN.z);
      float ws = max(0.0, abs(vN.x));
      float s = wf + wb + ws + 1e-4;
      vec3 col = (cf*wf + cb*wb + cs*ws)/s;
      gl_FragColor = vec4(col, 1.0);
    }`
});
const mesh = new THREE.Mesh(geo, mat);
scene.add(mesh);

// 简单轨道控制
let rot = true, dragging=false, px=0, py=0, az=0, pol=1.1, dist=3.2;
const cv = canvas;
cv.addEventListener('pointerdown', e=>{dragging=true;px=e.clientX;py=e.clientY;});
cv.addEventListener('pointerup', ()=>dragging=false);
cv.addEventListener('pointermove', e=>{
  if(!dragging) return;
  az -= (e.clientX-px)*0.01; pol -= (e.clientY-py)*0.01;
  pol = Math.max(0.25, Math.min(2.9, pol)); px=e.clientX; py=e.clientY;
});
cv.addEventListener('wheel', e=>{dist *= (1+Math.sign(e.deltaY)*0.08); dist=Math.max(1.4,Math.min(6,dist)); e.preventDefault();}, {passive:false});
document.getElementById('rot').onclick = e=>{rot=!rot; e.target.textContent = rot?'⏸ 旋转':'▶ 旋转';};
document.getElementById('wf').onclick = e=>{mat.wireframe=!mat.wireframe;};
document.getElementById('reset').onclick = ()=>{az=0;pol=1.1;dist=3.2;};

function resize(){ const w=cv.clientWidth,h=cv.clientHeight; if(cv.width!==Math.floor(w*devicePixelRatio)||cv.height!==Math.floor(h*devicePixelRatio)){cv.width=Math.floor(w*devicePixelRatio);cv.height=Math.floor(h*devicePixelRatio);} renderer.setSize(w,h,false); camera.aspect=w/h; camera.updateProjectionMatrix(); }
function loop(){
  resize();
  if(rot && !dragging) az += 0.006;
  const x = dist*Math.sin(pol)*Math.sin(az);
  const y = H3D*0.5 + dist*Math.cos(pol);
  const z = dist*Math.sin(pol)*Math.cos(az);
  camera.position.set(x,y,z); camera.lookAt(camTarget);
  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}
loop();
</script>
</body></html>
"""

if __name__ == '__main__':
    main()
