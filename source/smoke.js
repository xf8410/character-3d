// 冒烟测试：用桩替换 GL 相关类，在 Node 中执行页面应用脚本，验证无运行时错误
const fs = require('fs');
const html = fs.readFileSync('/root/.codebuddy/artifact/whalegirl/template.html', 'utf8');
const parts = html.split('<script>/*__THREE_JS__*/</script>');
let appSrc = parts[1];
appSrc = appSrc.replace(/^\s*<script>/, '').replace(/<\/script>\s*[\s\S]*$/, '');
console.log('app script length:', appSrc.length);

const rafQ = [];
global.requestAnimationFrame = (fn) => { rafQ.push(fn); return rafQ.length; };

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

function FakeRenderer(params) {
  return {
    domElement: fakeCanvas(), shadowMap: {}, info: { render: { triangles: 99999 } },
    setPixelRatio() {}, setSize() {}, setClearColor() {}, render() {}, dispose() {},
    toneMapping: 0, toneMappingExposure: 1, outputColorSpace: '',
    capabilities: { getMaxAnisotropy: () => 1, isWebGL2: true }
  };
}
THREE.WebGLRenderer = FakeRenderer;
THREE.PMREMGenerator = function () { return { fromEquirectangular: () => ({ texture: {} }), dispose() {} }; };
THREE.CanvasTexture = function () { const t = new THREE.DataTexture(new Uint8Array([128, 128, 128, 255]), 1, 1); t.needsUpdate = true; return t; };
THREE.TextureLoader = function () { return { load: () => { const t = new THREE.DataTexture(new Uint8Array([200, 200, 200, 255]), 1, 1); t.needsUpdate = true; return t; } }; };

try {
  eval(appSrc);
  console.log('APP INIT: OK');
  for (let i = 0; i < 8; i++) { const q = rafQ.splice(0); q.forEach(f => f()); }
  console.log('FRAMES: OK (8 frames), queued:', rafQ.length);
  console.log('SMOKE TEST PASSED');
} catch (e) {
  console.log('APP ERROR:', e.stack.split('\n').slice(0, 8).join('\n'));
  process.exit(1);
}
