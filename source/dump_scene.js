// 导出场景几何供 Python 离线渲染检查：每个 mesh 的图层、材质键、几何、世界矩阵
const fs = require('fs');
const html = fs.readFileSync('/root/.codebuddy/artifact/whalegirl/template.html', 'utf8');
const parts = html.split('<script>/*__THREE_JS__*/</script>');
let appSrc = parts[1];
appSrc = appSrc.replace(/^\s*<script>/, '').replace(/<\/script>\s*[\s\S]*$/, '');

global.requestAnimationFrame = () => 0;

const ctx2d = new Proxy({}, {
  get(t, p) {
    if (p === 'createLinearGradient' || p === 'createRadialGradient') return () => ({ addColorStop() {} });
    if (p === 'canvas') return {};
    if (p === 'measureText') return () => ({ width: 10 });
    if (p in t) return t[p];
    return () => {};
  },
  set(t, p, v) { t[p] = v; return true; }
});
function fakeCanvas() {
  return { width: 300, height: 150, style: {}, addEventListener() {}, removeEventListener() {},
    getContext: () => ctx2d, setPointerCapture() {}, toDataURL: () => 'data:,' };
}
function fakeElem() {
  return { style: {}, addEventListener() {}, removeEventListener() {}, setPointerCapture() {},
    textContent: '', innerHTML: '', src: '', checked: true, value: '1', getContext: () => ctx2d,
    width: 0, height: 0 };
}
global.document = {
  createElement: (tag) => (tag === 'canvas' ? fakeCanvas() : fakeElem()),
  createElementNS: (ns, tag) => (tag === 'canvas' ? fakeCanvas() : fakeElem()),
  getElementById: () => fakeElem(),
  querySelectorAll: () => [],
  addEventListener() {}, body: fakeElem()
};
global.window = { innerWidth: 1400, innerHeight: 900, devicePixelRatio: 1, addEventListener() {} };
global.performance = require('perf_hooks').performance;
global.Image = function () {
  const im = { width: 1024, height: 1536, onload: null, _src: '' };
  Object.defineProperty(im, 'src', { get() { return im._src; }, set(v) { im._src = v; } });
  return im;
};

const THREE = require('/root/.codebuddy/artifact/whalegirl/three.min.js');
global.THREE = THREE;
function FakeRenderer() {
  return {
    domElement: fakeCanvas(), shadowMap: {}, info: { render: { triangles: 0 } },
    setPixelRatio() {}, setSize() {}, setClearColor() {}, render() {}, dispose() {},
    toneMapping: 0, toneMappingExposure: 1, outputColorSpace: '',
    capabilities: { getMaxAnisotropy: () => 1, isWebGL2: true }
  };
}
THREE.WebGLRenderer = FakeRenderer;
THREE.PMREMGenerator = function () { return { fromEquirectangular: () => ({ texture: {} }), dispose() {} }; };
THREE.CanvasTexture = function () { const t = new THREE.DataTexture(new Uint8Array([128, 128, 128, 255]), 1, 1); t.needsUpdate = true; return t; };

eval(appSrc);
for (let i = 0; i < 3; i++) { /* 推进动画无关紧要 */ }

const scene = global.window.__SCENE__;
const MATS = global.window.__MATS__;
const layerMesh = global.window.__LAYER_MESH__;
scene.updateMatrixWorld(true);

const matKeyOf = new Map();
Object.keys(MATS).forEach(k => { MATS[k] && matKeyOf.set(MATS[k].uuid, k); });
const layerOf = new Map();
Object.keys(layerMesh).forEach(k => (layerMesh[k] || []).forEach(o => layerOf.set(o.uuid, k)));

const meshes = [];
scene.traverse((o) => {
  if (!o.isMesh || !o.geometry || !o.geometry.attributes || !o.geometry.attributes.position) return;
  if (!layerOf.has(o.uuid)) return; // 只导出角色五层部件，排除展台/billboard/阴影
  const g = o.geometry;
  const pos = g.attributes.position.array;
  const idx = g.index ? g.index.array : null;
  // 材质键
  let mk = 'unknown';
  const mats = Array.isArray(o.material) ? o.material : [o.material];
  if (mats[0]) mk = matKeyOf.get(mats[0].uuid) || (mats[0].map ? 'eyetex' : 'custom');
  // 顶点色均值（hair ribbon 用 vertexColors）
  let vc = null;
  if (g.attributes.color) {
    const c = g.attributes.color.array;
    let r = 0, gg = 0, b = 0, n = 0;
    for (let i = 0; i < c.length; i += 3 * 997) { r += c[i]; gg += c[i + 1]; b += c[i + 2]; n++; }
    if (n) vc = [r / n, gg / n, b / n];
  }
  meshes.push({
    layer: layerOf.get(o.uuid) || 'none',
    mat: mk,
    vc,
    m: Array.from(o.matrixWorld.elements),
    pos: Array.from(pos, v => Math.round(v * 1000) / 1000),
    idx: idx ? Array.from(idx) : null
  });
});

const out = { nMeshes: meshes.length, meshes };
fs.writeFileSync('/root/.codebuddy/artifact/whalegirl/scene_dump.json', JSON.stringify(out));
const tris = meshes.reduce((s, m) => s + (m.idx ? m.idx.length / 3 : m.pos.length / 9), 0);
console.log('DUMP OK meshes:', meshes.length, 'tris:', tris, 'size:', (fs.statSync('/root/.codebuddy/artifact/whalegirl/scene_dump.json').size / 1e6).toFixed(1) + 'MB');
