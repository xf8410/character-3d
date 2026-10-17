# character-3d

程序化 Three.js 角色模型 + 参考图投影重建（Q 版马耳少女 / ウマ娘风格）。

## 内容
- `index.html` —— 最新交互查看器（五层显隐：骨架/皮肤/衣服/头发/装饰，自动旋转，材质滑杆）
- `views/` —— 原始正交三视图（正/侧/背）
- `proj/` —— 对齐后的投影贴图 + 剪影剖面元数据（来自原图的轮廓驱动）
- `ref_character.png` / `three_view_sheet.png` / `ref_style_sheet.png` —— 参考图
- `inspect/` —— 离线逐层渲染检查图（7 视角 × 5 图层）
- `source/` —— 建模源模板与构建/检查脚本

## 说明
本沙箱无 GPU / 无 WebGL，模型为程序化几何 + 三视图投影贴图。
真·神经图生 3D（Hunyuan3D-2 / TRELLIS）需 GPU，未在本环境运行。
