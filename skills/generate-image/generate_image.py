#!/usr/bin/env python3
"""
GPT Image Generation Script (via Ducky API)

通过 Ducky 服务调用 GPT 图像生成模型，根据用户提供的 prompt 生成图片并保存到本地。

Ducky 是内部统一的模型调用网关，Go 代码中 gpt_image.go 通过 llm.NewDefaultProviderWrapper()
最终调用 DuckyProvider.Chat()，其 API 格式如下：

  POST https://ducky.code.alibaba-inc.com/v1/chat
  Headers:
    Authorization: Bearer base64(DUCKY_PRIVATE_TOKEN)
    X-Model-Name: <modelId>
    X-Request-Id: <uuid>
  Body (JSON):
    {"prompt": "<描述>", "modelId": "<模型名>", "stream": false}
  Response (JSON):
    {"context": "<图片URL或base64数据>", "id": ..., "usage": ...}

支持两种响应格式：
  1. context 为图片 URL —— 自动下载并保存
  2. context 为 base64 编码的图片数据 —— 自动解码并保存

依赖：
  - Python 3.7+
  - 无需安装第三方库（仅使用标准库）

环境变量：
  - DUCKY_PRIVATE_TOKEN   : (必需) Ducky 服务的认证 Token（请勿复用其他服务凭证，避免跨服务泄漏）
  - DUCKY_BASE_URL        : (可选) Ducky API 地址，默认 https://ducky.code.alibaba-inc.com/v1/chat
  - GPT_IMAGE_MODEL       : (可选) 模型名称，默认 gpt-image-1
  - IMAGE_OUTPUT_DIR      : (可选) 图片保存目录，默认为当前目录下的 .image_process 目录
"""

import argparse
import base64
import json
import os
import ssl
import sys
import time
import uuid
from datetime import datetime
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


# ──────────────────────────── 默认配置 ────────────────────────────

DEFAULT_MODEL = "web-agent/gpt-image-2-0421-global"
DEFAULT_DUCKY_URL = "https://ducky.code.alibaba-inc.com/v1/chat"
DEFAULT_OUTPUT_DIR = ".image_process"


# ──────────────────────────── 工具函数 ────────────────────────────

def _create_ssl_context() -> ssl.SSLContext:
    """创建一个不验证证书的 SSL 上下文（内部服务场景）。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def is_valid_image_url(raw_str: str) -> bool:
    """判断字符串是否为有效的 HTTP/HTTPS URL（与 Go 代码 isValidImageURL 对齐）。"""
    try:
        parsed = urlparse(raw_str)
        return parsed.scheme in ("http", "https")
    except Exception:
        return False


def generate_output_path(output_dir: str, prefix: str = "gpt") -> str:
    """
    生成统一的图片保存路径（与 Go 代码 GenerateProcessedImagePath 对齐）。
    格式：<output_dir>/<prefix>_<yyyymmddHHMMSS>_<毫秒后三位>.png
    """
    os.makedirs(output_dir, exist_ok=True)
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    ms_suffix = f"{int(time.time_ns()) % 1000:03d}"
    filename = f"{prefix}_{timestamp}_{ms_suffix}.png"
    return os.path.join(output_dir, filename)


def download_image(url: str, save_path: str, timeout: int = 120) -> str:
    """从 URL 下载图片并保存到指定路径（对应 Go 代码 DownloadURLToProcessedPath）。"""
    req = Request(url)
    ctx = _create_ssl_context()
    with urlopen(req, timeout=timeout, context=ctx) as resp:
        with open(save_path, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
    return save_path


def save_base64_image(raw_base64: str, save_path: str) -> str:
    """
    解码 base64 图片数据并保存（与 Go 代码 saveBase64Image 对齐）。
    支持带或不带 data URI 前缀（如 data:image/png;base64,...）。
    """
    base64_data = raw_base64
    marker = ";base64,"
    idx = raw_base64.find(marker)
    if idx != -1:
        base64_data = raw_base64[idx + len(marker):]
    decoded = base64.b64decode(base64_data)
    with open(save_path, "wb") as f:
        f.write(decoded)
    return save_path


# ──────────────────────────── 核心调用 ────────────────────────────

def call_ducky_api(
    prompt: str,
    token: str,
    ducky_url: str = DEFAULT_DUCKY_URL,
    model: str = DEFAULT_MODEL,
    timeout: int = 300,
) -> dict:
    """
    调用 Ducky 图像生成 API（与 Go 代码 DuckyProvider.Chat + convertRequest 对齐）。

    请求格式 (duckyRequest):
        {
            "prompt": "...",
            "modelId": "gpt-image-1",
            "stream": false,
            "needAppend": false,
            "chatMessage": null,
            "functions": null
        }

    认证方式：
        Authorization: Bearer base64(token)

    Args:
        prompt:    图片描述
        token:     Ducky 认证 Token (AoneAgentCodePrivateToken)
        ducky_url: Ducky API 地址
        model:     模型名称
        timeout:   请求超时时间(秒)

    Returns:
        API 响应的 JSON dict (ChatResponse)
    """
    # 与 Go 代码一致：对 token 做 base64 编码后放入 Bearer
    base64_token = token
    request_id = str(uuid.uuid4())

    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream, application/json",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Authorization": f"Bearer {base64_token}",
        "X-Model-Name": model,
        "X-Request-Id": request_id,
    }

    # duckyRequest 请求体（与 Go 代码 convertRequest 对齐）
    payload = {
        "prompt": prompt,
        "modelId": model,
        "stream": False,
        "needAppend": False,
        "chatMessage": None,
        "functions": None,
    }

    print(f"[INFO] 正在调用 Ducky 图像生成 API...", file=sys.stderr)
    print(f"[INFO] 端点: {ducky_url}", file=sys.stderr)
    print(f"[INFO] 模型: {model}", file=sys.stderr)
    print(f"[INFO] Request-Id: {request_id}", file=sys.stderr)
    print(f"[INFO] Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}", file=sys.stderr)

    data = json.dumps(payload).encode("utf-8")
    req = Request(ducky_url, data=data, headers=headers, method="POST")
    ctx = _create_ssl_context()

    with urlopen(req, timeout=timeout, context=ctx) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def generate_image(
    prompt: str,
    token: str | None = None,
    ducky_url: str | None = None,
    model: str | None = None,
    output_dir: str | None = None,
) -> str:
    """
    生成图片的主入口函数。

    与 Go 代码 gptImageProvider.ProcessImage 逻辑对齐：
      1. 构造 ChatRequest{Prompt, Stream: false, ModelId}
      2. 调用 provider.Chat(ctx, request)
      3. 从 resp.Context 取出图片数据
      4. 判断 URL 或 base64，分别处理并保存

    Args:
        prompt:     图片描述文本 (必填)
        token:      Ducky 认证 Token，不传则读取 DUCKY_PRIVATE_TOKEN 环境变量
        ducky_url:  Ducky API 地址，不传则读取 DUCKY_BASE_URL 环境变量
        model:      模型名称，不传则读取 GPT_IMAGE_MODEL 环境变量
        output_dir: 图片保存目录，不传则读取 IMAGE_OUTPUT_DIR 环境变量

    Returns:
        生成图片的本地绝对路径

    Raises:
        ValueError: 缺少必填参数
        HTTPError: API 调用失败
    """
    # 参数解析：仅接受 DUCKY_PRIVATE_TOKEN，禁止回退到其他服务凭证（防跨服务泄漏）
    token = token or os.environ.get("DUCKY_PRIVATE_TOKEN", "")
    if not token:
        raise ValueError(
            "Ducky Token 未提供。请设置 DUCKY_PRIVATE_TOKEN 环境变量，或通过 --token 参数传入。"
            "请勿复用 ANTHROPIC_AUTH_TOKEN 等其他服务凭证，避免跨服务误用与泄漏。"
        )

    ducky_url = ducky_url or os.environ.get("DUCKY_BASE_URL", DEFAULT_DUCKY_URL)
    model = model or os.environ.get("GPT_IMAGE_MODEL", DEFAULT_MODEL)
    output_dir = output_dir or os.environ.get("IMAGE_OUTPUT_DIR", DEFAULT_OUTPUT_DIR)

    # 调用 Ducky API
    result = call_ducky_api(
        prompt=prompt,
        token=token,
        ducky_url=ducky_url,
        model=model,
    )

    # 从 ChatResponse.Context 提取图片数据（与 Go 代码对齐）
    image_data = result.get("context", "")
    if not image_data:
        raise RuntimeError(
            f"gpt_image: empty image data in response context. "
            f"完整响应: {json.dumps(result, ensure_ascii=False)}"
        )

    save_path = generate_output_path(output_dir, prefix="gpt")

    # 判断返回内容是 URL 还是 base64 编码的图片数据（与 Go 代码逻辑一致）
    if is_valid_image_url(image_data):
        print(f"[INFO] 检测到图片 URL，正在下载...", file=sys.stderr)
        download_image(image_data, save_path)
    else:
        print(f"[INFO] 检测到 base64 编码图片，正在解码...", file=sys.stderr)
        save_base64_image(image_data, save_path)

    abs_path = os.path.abspath(save_path)
    file_size = os.path.getsize(abs_path)
    print(f"[INFO] 图片已保存: {abs_path} (size: {file_size} bytes)", file=sys.stderr)
    # 将路径输出到 stdout，便于其他程序捕获
    print(abs_path)
    return abs_path


# ──────────────────────────── CLI 入口 ────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="GPT Image Generation - 通过 Ducky 服务调用 GPT 图像生成模型",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基本用法（需要设置 DUCKY_PRIVATE_TOKEN 环境变量）
  python generate_image.py --prompt "一只可爱的橘猫在阳光下打盹"

  # 指定所有参数
  python generate_image.py \\
    --prompt "赛博朋克风格的城市夜景" \\
    --token "your-ducky-token" \\
    --ducky-url "https://ducky.code.alibaba-inc.com/v1/chat" \\
    --model "gpt-image-1" \\
    --output-dir "./my_images"

  # 使用预发环境
  python generate_image.py \\
    --prompt "简约风格的公司 Logo" \\
    --ducky-url "https://pre-ducky.code.alibaba-inc.com/v1/chat"
        """,
    )
    parser.add_argument(
        "--prompt", "-p",
        required=True,
        help="图片描述文本 (必填)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Ducky 认证 Token (也可通过 DUCKY_PRIVATE_TOKEN 环境变量设置；请勿复用其他服务凭证)",
    )
    parser.add_argument(
        "--ducky-url",
        default=None,
        help=f"Ducky API 地址 (默认: {DEFAULT_DUCKY_URL}，也可通过 DUCKY_BASE_URL 环境变量设置)",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help=f"模型名称 (默认: {DEFAULT_MODEL}，也可通过 GPT_IMAGE_MODEL 环境变量设置)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help=f"图片保存目录 (默认: {DEFAULT_OUTPUT_DIR}，也可通过 IMAGE_OUTPUT_DIR 环境变量设置)",
    )

    args = parser.parse_args()

    try:
        saved_path = generate_image(
            prompt=args.prompt,
            token=args.token,
            ducky_url=args.ducky_url,
            model=args.model,
            output_dir=args.output_dir,
        )
        print(f"[SUCCESS] 图片生成完成: {saved_path}", file=sys.stderr)
    except ValueError as e:
        print(f"[ERROR] 参数错误: {e}", file=sys.stderr)
        sys.exit(1)
    except HTTPError as e:
        print(f"[ERROR] API 调用失败: {e}", file=sys.stderr)
        body = e.read().decode("utf-8", errors="replace")
        if body:
            print(f"[ERROR] 响应内容: {body}", file=sys.stderr)
        sys.exit(2)
    except URLError as e:
        print(f"[ERROR] 网络连接失败: {e.reason}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"[ERROR] 未知错误: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
