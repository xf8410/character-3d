# character-3d

用**仓库 CI** 从零构建的 3D 角色项目：从正交参考图（正/侧/背）重建可旋转的 3D 模型，不依赖任何商业 3D API、不需要 GPU。

## 思路（来自公开资料研究）

1. **轮廓放样 (silhouette loft)**：从三张正交参考图逐行提取轮廓半宽，用「正面半宽→X 半径、侧面半宽→Z 半径」放样出网格，使模型的正视/侧视剪影严格等于原图。
2. **三向平面投影 (tri-planar / planar projection)**：自定义着色器把正/侧/背三张原图分别投影到朝外表面（+Z 正面、−Z 背面、±X 侧面），按法线加权混合。颜色、五官、金饰、裙褶全部来自原图，不做程序化近似——这是"像原图"的关键。

> 参考：[img2threejs](https://github.com/img2threejs/img2threejs) 的 projection-first fidelity 方法论；Three.js 纹理投影（Codrops）、三平面映射（triplanar）等公开资料。

## 本地构建

```bash
pip install pillow numpy
python3 gen.py              # 生成 index.html（内联 three.js，贴图引用 views/*.png）
python3 check_silhouette.py # 验证网格剪影 IoU≈0.98 贴合原图
```

## 通过 CI 构建（推荐）

仓库已配置 GitHub Actions（`build.yml`）：

- 在仓库 **Actions → build3d → Run workflow** 手动触发；或 push 到 `gen.py`/`views/`/`vendor/` 自动触发。
- CI 跑 `gen.py` 生成 `index.html`，自检剪影，并把成果 `commit` 回 `main`。
- **GitHub Pages** 自动部署：https://xf8410.github.io/character-3d/

## 目录

| 路径 | 说明 |
|---|---|
| `gen.py` | 核心生成器：轮廓提取 + 放样 + 投影着色器，输出自包含 `index.html` |
| `check_silhouette.py` | 量化验证网格剪影贴合原图（IoU） |
| `views/` | 干净正交参考图（正/侧/背） |
| `vendor/three.min.js` | 内联的 Three.js r152 |
| `.github/workflows/build.yml` | CI 构建工作流 |
| `index.html` | 最新成果（CI 生成，可直接打开 / Pages 部署） |
