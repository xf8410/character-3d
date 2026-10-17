#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tripo V3 图生 3D 工具
=====================
把一张参考图(你的 Q 版立绘)上传到 Tripo,云端 AI 生成真实 3D 网格,
下载为 model.glb,配合 viewer.html 即可在手机/电脑浏览器里旋转查看。

为什么用这个而不是之前的手工建模:
  平台是真·AI 生成网格,不是程序化拼几何体,所以不会出现
  "胶囊小人 / 衣架子 / 陶瓷花瓶" 那种问题。

依赖:仅 Python 3 标准库,无需 pip install。

用法:
  # 1) 先配置 API Key(任选其一)
  export TRIPO_API_KEY="tsk_xxxx"          # 方式 A:环境变量
  # 或把 Key 写进当前目录的 .tripo_key 文件  # 方式 B:文件

  # 2) 生成(默认用 inputs/ref_chibi.png)
  python3 gen_tripo.py --image inputs/ref_chibi.png --output model.glb

  # 国内网络若连不上,加 --china 用中国节点
  python3 gen_tripo.py --image inputs/ref_chibi.png --output model.glb --china

  # 想要游戏/手机友好的低面数模型,改用 P1 版本:
  python3 gen_tripo.py --image inputs/ref_chibi.png --output model.glb \
      --model-version P1-20260311 --face-limit 8000

重要:
  - 生成结果链接约 5 分钟内过期,脚本会"生成完立刻下载",无需你手动抢。
  - orientation=align_image 会自动把模型转正对齐原图(解决之前"倒吊"的问题)。
  - texture_alignment=original_image 让贴图优先贴合你的原图配色。
"""

import os
import sys
import time
import json
import ssl
import argparse
import urllib.request
import urllib.error

# V3 接口地址(注意:已不是 v2 的 api.tripo3d.ai/v2/openapi)
BASE_GLOBAL = "https://openapi.tripo3d.ai/v3"
BASE_CHINA = "https://openapi.tripo3d.com/v3"

DEFAULT_MODEL_VERSION = "v3.1-20260211"   # 最高质量;手机低面数用 P1-20260311


def _ssl_ctx():
    return ssl.create_default_context()


def _http_json(req, timeout=120):
    """发送请求并解析 JSON;Tripo 返回 {"code":0,"data":{...}}。"""
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        raise RuntimeError("HTTP %s: %s" % (e.code, body))
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError("非 JSON 响应: %s" % raw[:200])
    if obj.get("code", 0) != 0:
        raise RuntimeError("API 报错: %s" % json.dumps(obj, ensure_ascii=False))
    return obj


def _post_json(url, payload, api_key, timeout=120):
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer %s" % api_key,
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    return _http_json(req, timeout)


def _multipart(boundary, fields):
    """构造 multipart/form-data 请求体。fields: {name:(filename,bytes,ctype)}。"""
    body = b""
    for name, (filename, blob, ctype) in fields.items():
        body += ("--%s\r\n" % boundary).encode()
        body += ('Content-Disposition: form-data; name="%s"; filename="%s"\r\n'
                 % (name, filename)).encode()
        body += ("Content-Type: %s\r\n\r\n" % ctype).encode()
        body += blob
        body += b"\r\n"
    body += ("--%s--\r\n" % boundary).encode()
    headers = {"Content-Type": "multipart/form-data; boundary=%s" % boundary}
    return body, headers


def upload_file(path, api_key, base):
    """POST /files 上传图片,返回 file_token。"""
    with open(path, "rb") as f:
        blob = f.read()
    ext = os.path.splitext(path)[1].lower()
    ctype = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    boundary = "----TripoBoundary%d" % int(time.time() * 1000)
    body, headers = _multipart(boundary, {
        "file": (os.path.basename(path), blob, ctype),
    })
    headers["Authorization"] = "Bearer %s" % api_key
    req = urllib.request.Request(base + "/files", data=body,
                                 headers=headers, method="POST")
    obj = _http_json(req, timeout=300)
    return obj["data"]["file_token"]


def image_to_model(file_token, api_key, base, model_version,
                   texture_quality="standard", face_limit=None,
                   enable_autofix=False, orientation="align_image"):
    """POST /generation/image-to-model,返回 task_id。

    V3 用统一的 input 字段传 file_token(取代 V2 的 type+file.file_token)。
    """
    payload = {
        "input": file_token,
        "model_version": model_version,
        "texture": True,
        "pbr": True,
        "texture_alignment": "original_image",  # 贴图优先贴合原图
        "orientation": orientation,             # 自动转正,避免倒吊
        "texture_quality": texture_quality,
        "enable_image_autofix": enable_autofix,
    }
    if face_limit:
        payload["face_limit"] = face_limit
    obj = _post_json(base + "/generation/image-to-model", payload, api_key,
                     timeout=120)
    return obj["data"]["task_id"]


def get_task(task_id, api_key, base):
    req = urllib.request.Request(
        base + "/tasks/" + task_id,
        headers={"Authorization": "Bearer %s" % api_key},
        method="GET",
    )
    return _http_json(req, timeout=60)["data"]


def wait_task(task_id, api_key, base, timeout=900, interval=10):
    """轮询直到 success / failed,或超时。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = get_task(task_id, api_key, base)
        status = data.get("status")
        if status == "success":
            return data
        if status == "failed":
            raise RuntimeError("生成失败: %s"
                               % (data.get("reason") or data.get("output") or data))
        remain = int(deadline - time.time())
        print("  · 状态=%s,继续等待(%ds 后超时)..." % (status, remain))
        time.sleep(interval)
    raise TimeoutError("等待超时(%.0f 分钟),可稍后重试" % (timeout / 60))


def download_model(data, output):
    """从结果里取模型 URL 下载(无需 API Key,链接 5 分钟过期要尽快)。"""
    outputs = data.get("output") or {}
    url = outputs.get("pbr_model") or outputs.get("model")
    if not url:
        raise RuntimeError("结果里没有模型链接: %s" % json.dumps(outputs, ensure_ascii=False))
    print("  · 下载模型: %s" % url.split("?")[0])
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=300) as r:
        blob = r.read()
    with open(output, "wb") as f:
        f.write(blob)
    return output, len(blob)


def load_api_key(explicit=None):
    if explicit:
        return explicit
    env = os.environ.get("TRIPO_API_KEY")
    if env:
        return env.strip()
    keyfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tripo_key")
    if os.path.exists(keyfile):
        with open(keyfile, "r", encoding="utf-8") as f:
            return f.read().strip()
    raise RuntimeError(
        "未找到 API Key。请执行: export TRIPO_API_KEY=\"tsk_xxxx\"\n"
        "或在脚本同目录创建 .tripo_key 文件写入 Key。")


def main():
    ap = argparse.ArgumentParser(description="Tripo V3 图生 3D 工具")
    ap.add_argument("--image", default="inputs/ref_chibi.png", help="参考图路径")
    ap.add_argument("--output", default="model.glb", help="输出 glb 路径")
    ap.add_argument("--api-key", default=None, help="Tripo API Key(或用环境变量/文件)")
    ap.add_argument("--china", action="store_true", help="使用中国节点 openapi.tripo3d.com")
    ap.add_argument("--model-version", default=DEFAULT_MODEL_VERSION,
                    help="模型版本,默认 v3.1-20260211;低面数用 P1-20260311")
    ap.add_argument("--texture-quality", default="standard",
                    choices=["standard", "detailed", "extreme"], help="贴图质量")
    ap.add_argument("--face-limit", type=int, default=None,
                    help="面数上限(低面数模型用,如 8000)")
    ap.add_argument("--autofix", action="store_true", help="开启输入图自动优化")
    ap.add_argument("--timeout", type=int, default=900, help="生成等待超时(秒)")
    args = ap.parse_args()

    if not os.path.exists(args.image):
        ap.error("参考图不存在: %s" % args.image)

    api_key = load_api_key(args.api_key)
    base = BASE_CHINA if args.china else BASE_GLOBAL

    print("[1/4] 上传参考图: %s" % args.image)
    file_token = upload_file(args.image, api_key, base)
    print("      file_token = %s" % file_token)

    print("[2/4] 提交生成任务 (model=%s)..." % args.model_version)
    task_id = image_to_model(
        file_token, api_key, base, args.model_version,
        texture_quality=args.texture_quality,
        face_limit=args.face_limit,
        enable_autofix=args.autofix,
    )
    print("      task_id = %s" % task_id)

    print("[3/4] 等待云端生成(通常 30s~3min)...")
    data = wait_task(task_id, api_key, base, timeout=args.timeout)

    print("[4/4] 下载模型 -> %s" % args.output)
    path, size = download_model(data, args.output)
    print("\n✅ 完成! 模型已保存: %s (%.1f KB)" % (path, size / 1024))
    print("   把它和 viewer.html 放一起,用浏览器(或手机)打开 viewer.html 即可查看。")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print("\n❌ %s" % e, file=sys.stderr)
        sys.exit(1)
    except TimeoutError as e:
        print("\n⏱ %s" % e, file=sys.stderr)
        sys.exit(2)
