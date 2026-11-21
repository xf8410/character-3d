// 3D 引擎入口:由 esbuild 打包压缩成 viewer3d.js,按需加载。
import * as THREE from './vendor/three.module.js';
import { OrbitControls } from './vendor/jsm/controls/OrbitControls.js';
import { GLTFLoader } from './vendor/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from './vendor/jsm/libs/meshopt_decoder.module.js';

function dispose(o) {
  o.traverse(n => {
    if (n.geometry) n.geometry.dispose();
    if (n.material) (Array.isArray(n.material) ? n.material : [n.material])
      .forEach(m => m && m.dispose());
  });
}

export function createViewer(canvas, opts = {}) {
  const renderer = new THREE.WebGLRenderer({
    canvas, antialias: true, alpha: true, powerPreference: 'high-performance',
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, innerWidth / innerHeight, 0.01, 100);
  camera.position.set(0, 0.6, 2.6);

  // 柔和明亮的打光,避免模型显得惨白/阴森
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd9dcec, 1.7));
  const key = new THREE.DirectionalLight(0xffffff, 2.1);
  key.position.set(3, 5, 4); scene.add(key);
  const fill = new THREE.DirectionalLight(0xfff1e2, 0.9);
  fill.position.set(-3, 2, -2); scene.add(fill);
  const rim = new THREE.DirectionalLight(0xffffff, 0.5);
  rim.position.set(0, 2, -4); scene.add(rim);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 0.3;
  controls.maxDistance = 20;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 1.0;
  controls.target.set(0, 0.5, 0);

  let model = null;
  let autoRotate = true;

  function onResize() {
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight, false);
  }
  addEventListener('resize', onResize);
  onResize();
  renderer.setAnimationLoop(() => {
    controls.autoRotate = autoRotate;
    controls.update();
    renderer.render(scene, camera);
  });

  function frame(r) {
    camera.position.set(0, r * 0.55, r * 2.4);
    controls.target.set(0, r * 0.5, 0);
    controls.update();
  }

  function load(url) {
    return new Promise((resolve, reject) => {
      const loader = new GLTFLoader();
      loader.setMeshoptDecoder(MeshoptDecoder);
      loader.load(url, (gltf) => {
        if (model) { scene.remove(model); dispose(model); }
        model = gltf.scene;
        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z) || 1;
        const scale = 1.3 / maxDim;
        model.position.sub(center);
        model.scale.setScalar(scale);
        const box2 = new THREE.Box3().setFromObject(model);
        model.position.y -= box2.min.y;
        scene.add(model);
        frame(maxDim * scale);
        resolve();
      }, (xhr) => {
        if (opts.onProgress && xhr.total) opts.onProgress(xhr.loaded / xhr.total);
      }, (err) => {
        if (opts.onError) opts.onError(err);
        reject(err);
      });
    });
  }

  return {
    load,
    reset() {
      if (!model) return;
      const b = new THREE.Box3().setFromObject(model);
      frame(Math.max(b.max.x - b.min.x, b.max.y - b.min.y, b.max.z - b.min.z));
    },
    setRotate(v) { autoRotate = v; },
    toggleWire() {
      let on = false;
      if (model) model.traverse(n => {
        if (n.material) (Array.isArray(n.material) ? n.material : [n.material])
          .forEach(m => { if (m.wireframe !== undefined) { m.wireframe = !m.wireframe; on = m.wireframe; } });
      });
      return on;
    },
  };
}
