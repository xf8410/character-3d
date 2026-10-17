#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen.py —— character-3d 项目核心生成器（自己从零实现，不依赖 3D API/GPU）。

思路：从正/侧/背三视图提取轮廓，放样出分段椭圆柱（头/躯干/裙摆/腿），
      再用标准三向平面投影把参考图像素贴到对应朝向的表面。
"""
import json, os, math, base64
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
H3D = 1.8
N = 64          # 高度层数（手机性能友好）
M = 48          # 周向分段
SCALE = 0.985   # 网格略小于轮廓
TEX_W, TEX_H = 512, 768  # 贴图分辨率（手机友好）

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
    top, bot = int(content.min()), int(content.max())
    return rows, (top, bot), (H, W)

def resample(rows, top, bot, n):
    ys = np.linspace(top, bot, n)
    hw = np.interp(ys, np.arange(len(rows)), rows[:,0])
    cx = np.interp(ys, np.arange(len(rows)), rows[:,1])
    return ys, hw, cx

def build_elliptical_mesh(fprof, sprof, bprof, segs=None):
    """分段放样椭圆柱。segs 是 [(y0,y1, 是否闭合)] 列表；None 则整体一段。"""
    if segs is None:
        segs = [(0, N, False)]
    verts, aRow, aCxF, aCxS, aCxB = [], [], [], [], []
    y3d = np.linspace(0, H3D, N)
    fp, (ftop, fbot), (fH, fW) = fprof
    sp, (stop, sbot), (sH, sW) = sprof
    bp, (btop, bbot), (bH, bW) = bprof
    charH = (fbot - ftop) or 1
    charHs = (sbot - stop) or 1

    fys, fhw, fcx = resample(fp, ftop, fbot, N)
    sys_, shw, scx = resample(sp, stop, sbot, N)
    bys, bhw, bcx = resample(bp, btop, bbot, N)

    for i in range(N):
        xr = fhw[i] * (H3D / charH) * SCALE
        zr = shw[i] * (H3D / charHs) * SCALE
        for j in range(M):
            th = 2*math.pi*j/M
            x = xr * math.cos(th)
            z = zr * math.sin(th)
            verts.append([x, y3d[i], z])
            aRow.append(float(fys[i]))
            aCxF.append(float(fcx[i]))
            aCxS.append(float(scx[i]))
            aCxB.append(float(bcx[i]))

    # 封口（简单扇形，仅顶部）
    top_c = len(verts); verts.append([0, H3D, 0])
    aRow.append(float(ftop)); aCxF.append(fW/2); aCxS.append(sW/2); aCxB.append(bW/2)
    bot_c = len(verts); verts.append([0, 0, 0])
    aRow.append(float(fbot)); aCxF.append(fW/2); aCxS.append(sW/2); aCxB.append(bW/2)

    faces = []
    for i in range(N-1):
        for j in range(M):
            j2 = (j+1) % M
            a = i*M + j; b = i*M + j2; c = (i+1)*M + j2; d = (i+1)*M + j
            faces.append([a,b,c]); faces.append([a,c,d])
    for j in range(M):
        j2 = (j+1) % M
        faces.append([top_c, j, j2])
        faces.append([bot_c, (N-1)*M + j2, (N-1)*M + j])
    return verts, faces, aRow, aCxF, aCxS, aCxB, fH, fW, sH, sW, bH, bW, charH, charHs

def resize_tex(path):
    """缩放到 TEX_W x TEX_H 并 JPEG base64。"""
    im = Image.open(path).convert('RGB').resize((TEX_W, TEX_H), Image.LANCZOS)
    buf = im.tobytes()
    # 用 BytesIO 保存 JPEG
    import io
    out = io.BytesIO()
    im.save(out, 'JPEG', quality=82, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode()

def main():
    fprof = load_profile(os.path.join(HERE, 'views/front.png'))
    sprof = load_profile(os.path.join(HERE, 'views/side.png'))
    bprof = load_profile(os.path.join(HERE, 'views/back.png'))
    verts, faces, aRow, aCxF, aCxS, aCxB, fH, fW, sH, sW, bH, bW, charH, charHs = build_elliptical_mesh(fprof, sprof, bprof)

    Kf = (charH / H3D) / SCALE
    Ks = (charHs / H3D) / SCALE

    tex = {
        'front': resize_tex(os.path.join(HERE, 'views/front.png')),
        'side':  resize_tex(os.path.join(HERE, 'views/side.png')),
        'back':  resize_tex(os.path.join(HERE, 'views/back.png')),
    }
    geo = {
        'v': verts, 'f': faces,
        'aRow': aRow, 'aCxF': aCxF, 'aCxS': aCxS, 'aCxB': aCxB,
        'Wf': fW, 'Hf': fH, 'Ws': sW, 'Hs': sH, 'Wb': bW, 'Hb': bH,
        'Kf': Kf, 'Ks': Ks,
        'H3D': H3D,
    }

    three = open(os.path.join(HERE, 'vendor/three.min.js'), encoding='utf-8').read()
    three = three.replace('</script', '<\\/script')

    html = TEMPLATE\
        .replace('/*__THREE_JS__*/', three)\
        .replace('/*__GEO__*/', json.dumps(geo, separators=(',',':')))\
        .replace('/*__TEX__*/', json.dumps(tex, separators=(',',':')))
    out = os.path.join(HERE, 'index.html')
    open(out, 'w', encoding='utf-8').write(html)
    print('wrote', out, os.path.getsize(out), 'bytes; verts', len(verts), 'tris', len(faces))

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>character-3d</title>
<style>
html,body{margin:0;height:100%;background:#11131a;overflow:hidden;font-family:system-ui,-apple-system,sans-serif;touch-action:none}
#c{width:100%;height:100%;display:block}
#hud{position:fixed;left:8px;top:8px;color:#cfd6e4;font-size:12px;background:rgba(0,0,0,.45);padding:8px 10px;border-radius:8px;max-width:calc(100% - 16px);box-sizing:border-box;pointer-events:auto}
#hud b{font-size:13px}
#btns{margin-top:6px;display:flex;gap:6px;flex-wrap:wrap}
button{background:#222838;color:#cfd6e4;border:1px solid #333b4d;border-radius:6px;padding:5px 10px;font-size:12px;touch-action:manipulation}
#tip{font-size:11px;color:#8e99ae;margin-top:4px}
#ref{position:fixed;left:8px;right:8px;bottom:8px;display:flex;gap:6px;justify-content:center;pointer-events:none}
#ref img{height:76px;border:1px solid #2a2f3a;border-radius:4px;background:#fff;object-fit:contain;pointer-events:auto}
</style></head>
<body>
<canvas id="c"></canvas>
<div id="hud">
  <div><b>character-3d</b> · 三视图投影</div>
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

const renderer = new THREE.WebGLRenderer({canvas:cv, antialias:true, alpha:false, powerPreference:'low-power'});
renderer.setPixelRatio(Math.min(window.devicePixelRatio||1, 1.5));
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x11131a);
const camera = new THREE.PerspectiveCamera(42, cv.clientWidth/Math.max(cv.clientHeight,1), 0.05, 100);
camera.position.set(0, H3D*0.55, 3.2);

const geo = new THREE.BufferGeometry();
geo.setAttribute('position', new THREE.Float32BufferAttribute(GEO.v.flat(), 3));
geo.setAttribute('aRow', new THREE.Float32BufferAttribute(GEO.aRow, 1));
geo.setAttribute('aCxF', new THREE.Float32BufferAttribute(GEO.aCxF, 1));
geo.setAttribute('aCxS', new THREE.Float32BufferAttribute(GEO.aCxS, 1));
geo.setAttribute('aCxB', new THREE.Float32BufferAttribute(GEO.aCxB, 1));
geo.setIndex(GEO.f.flat());
geo.computeVertexNormals();

function mkTex(url){
  const t = new THREE.Texture();
  const img = new Image();
  img.onload = ()=>{ t.image = img; t.flipY = false; t.needsUpdate = true; };
  img.src = url;
  return t;
}
const frontTex = mkTex(TEX.front);
const sideTex  = mkTex(TEX.side);
const backTex  = mkTex(TEX.back);

const mat = new THREE.ShaderMaterial({
  uniforms:{
    frontTex:{value:frontTex}, sideTex:{value:sideTex}, backTex:{value:backTex},
    Wf:{value:GEO.Wf}, Hf:{value:GEO.Hf}, Ws:{value:GEO.Ws}, Hs:{value:GEO.Hs}, Wb:{value:GEO.Wb}, Hb:{value:GEO.Hb},
    Kf:{value:GEO.Kf}, Ks:{value:GEO.Ks}
  },
  vertexShader:`
    attribute float aRow; attribute float aCxF; attribute float aCxS; attribute float aCxB;
    uniform float Wf,Hf,Ws,Hs,Wb,Hb,Kf,Ks;
    varying vec2 vUf; varying vec2 vUs; varying vec2 vUb; varying vec3 vN;
    void main(){
      vUf = vec2((aCxF + position.x*Kf)/Wf, aRow/Hf);
      vUb = vec2((aCxB - position.x*Kf)/Wb, aRow/Hb);
      vUs = vec2((aCxS + position.z*Ks)/Ws, aRow/Hs);
      vN = normalize(normalMatrix * normal);
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
    }`,
  fragmentShader:`
    precision highp float;
    uniform sampler2D frontTex, sideTex, backTex;
    varying vec2 vUf; varying vec2 vUs; varying vec2 vUb; varying vec3 vN;
    void main(){
      vec3 cf = texture2D(frontTex, vUf).rgb;
      vec3 cb = texture2D(backTex, vUb).rgb;
      vec3 cs = texture2D(sideTex, vUs).rgb;
      float nz = vN.z, nx = abs(vN.x);
      // 三向硬切 + 小过渡，避免图腾柱混叠
      float wf = smoothstep(0.55, 0.75, nz);
      float wb = smoothstep(0.55, 0.75, -nz);
      float ws = smoothstep(0.60, 0.80, nx);
      float s = wf + wb + ws + 1e-4;
      vec3 col = (cf*wf + cb*wb + cs*ws) / s;
      // gamma 微调让贴图不要太暗
      col = pow(col, vec3(0.9));
      gl_FragColor = vec4(col, 1.0);
    }`
});
const mesh = new THREE.Mesh(geo, mat);
scene.add(mesh);

for(const [id,url] of [['rfront',TEX.front],['rside',TEX.side],['rback',TEX.back]]){
  const el=document.getElementById(id); if(el) el.src=url;
}

let rot=true, dragging=false, px=0, py=0, az=0, pol=1.15, dist=3.2;
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
document.getElementById('reset').onclick = ()=>{az=0;pol=1.15;dist=3.2;};

function resize(){
  const w=window.innerWidth, h=window.innerHeight;
  const rw=Math.floor(w*(window.devicePixelRatio||1));
  const rh=Math.floor(h*(window.devicePixelRatio||1));
  if(cv.width!==rw||cv.height!==rh){cv.width=rw;cv.height=rh;}
  renderer.setSize(w,h,false);
  camera.aspect=w/h; camera.updateProjectionMatrix();
}
function loop(){
  resize();
  if(rot && !dragging) az += 0.006;
  const x = dist*Math.sin(pol)*Math.sin(az);
  const y = H3D*0.45 + dist*Math.cos(pol);
  const z = dist*Math.sin(pol)*Math.cos(az);
  camera.position.set(x,y,z); camera.lookAt(0,H3D*0.45,0);
  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}
loop();
</script>
</body></html>
"""

if __name__ == '__main__':
    main()
