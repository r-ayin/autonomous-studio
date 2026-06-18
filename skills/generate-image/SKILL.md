---
name: generate-image
description: >
  使用 GPT Image 模型生成图片。当用户要求创建、生成、绘制图片或插图时，使用此技能调用
  generate_image.py 脚本来生成图片并保存到本地。支持自定义图片尺寸、质量等参数。
version: 1.1.0
author: aone-copilot
tags:
  - image
  - generation
  - creative
x-source: aone-open
repository: https://code.alibaba-inc.com/qunbu/generate-image
---

# GPT Image Generation Skill

## 概述

本技能通过 Ducky 服务（内部模型调用网关）调用生图模型 (GPT、Nano banan) 生成图片。
当用户需要创建图片、插图、设计稿、图标等可视化内容时，应使用本技能。

Ducky API 是内部统一的 LLM 调用入口，Python 脚本的调用方式完全对齐API接口。

## 何时使用

当用户的请求中包含以下意图时，应激活本技能：

- 需要**生成**、**创建**、**绘制**、**画**一张图片
- 需要创建**图标**、**Logo**、**插图**、**封面**、**海报**等视觉素材
- 需要将文字描述**可视化**为图片
- 涉及**图片设计**、**UI 设计**等需要产出图片的任务

## 使用方法

### 前置条件

1. Token 认证：默认使用 `ANTHROPIC_AUTH_TOKEN` 环境变量（无需额外配置），也可通过 `DUCKY_PRIVATE_TOKEN` 或 `--token` 参数覆盖
2. Python 3.7+（仅使用标准库，无需安装第三方依赖）

### 脚本位置

脚本位于当前技能目录下：`generate_image.py`

### 命令格式

```bash
python generate_image.py --prompt "<图片描述>" [可选参数]
```

### 参数说明

| 参数           | 缩写 | 必填 | 默认值                                                            | 说明                                          |
| -------------- | ---- | ---- | ----------------------------------------------------------------- | --------------------------------------------- |
| `--prompt`     | `-p` | ✅   | -                                                                 | 图片描述文本，尽量详细描述期望的图片内容      |
| `--token`      | -    | ❌   | `$DUCKY_PRIVATE_TOKEN` → `$ANTHROPIC_AUTH_TOKEN`                  | Ducky 认证 Token，默认取 ANTHROPIC_AUTH_TOKEN |
| `--ducky-url`  | -    | ❌   | `$DUCKY_BASE_URL` 或 `https://ducky.code.alibaba-inc.com/v1/chat` | Ducky API 地址                                |
| `--model`      | `-m` | ❌   | `$GPT_IMAGE_MODEL` 或 `gpt-image-1`                               | 模型名称                                      |
| `--output-dir` | `-o` | ❌   | `$IMAGE_OUTPUT_DIR` 或 `.image_process`                           | 图片保存目录                                  |

### Ducky API 环境

| 环境 | 地址                                         |
| ---- | -------------------------------------------- |
| 生产 | `https://ducky.code.alibaba-inc.com/v1/chat` |

## 调用示例

### 基本用法

```bash
python generate_image.py --prompt "一只可爱的橘猫在阳光下打盹，水彩画风格"
```

### 指定所有参数

```bash
python generate_image.py \
  --prompt "赛博朋克风格的城市夜景，霓虹灯闪烁，高楼林立" \
  --token "your-ducky-token" \
  --ducky-url "https://ducky.code.alibaba-inc.com/v1/chat" \
  --output-dir "./my_images"
```

## 输出说明

- 脚本会将生成的图片保存为 PNG 格式
- 保存路径格式：`<output_dir>/gpt_<yyyymmddHHMMSS>_<序号>.png`
- **stdout** 输出图片的绝对路径（便于程序捕获）
- **stderr** 输出日志信息（进度、错误等）

## API 调用细节

脚本调用流程：

```
gpt_image ProcessImage()
  → ChatRequest{Prompt, Stream:false, ModelId:"gpt-image-1"}
  → DuckyProvider.Chat()
      POST https://ducky.code.alibaba-inc.com/v1/chat
      Headers:
        Authorization: Bearer base64(<token>)
        X-Model-Name: gpt-image-1
        X-Request-Id: <uuid>
      Body: {"prompt":"...","modelId":"gpt-image-1","stream":false}
  → ChatResponse.Context  (URL 或 base64 图片数据)
```

## 使用指南（面向 AI 模型）

当你需要调用此脚本生成图片时，请遵循以下步骤：

1. **理解用户需求**：从用户请求中提取图片描述
2. **构造 Prompt**：将用户的描述转化为详细、具体的 prompt。好的 prompt 应包含：
   - 主体内容描述
   - 画面风格（如水彩、油画、摄影、3D 渲染等）
   - 色调、光线、构图等细节
   - 期望的情绪或氛围
3. **执行脚本**：使用 `Shell` 工具执行 Python 脚本
4. **返回结果**：将生成的图片路径告知用户

### Prompt 编写建议

- ✅ **好的 Prompt**：`"A serene Japanese garden in autumn, with a wooden bridge over a koi pond, maple trees with red and orange leaves, soft golden hour lighting, photorealistic style"`
- ❌ **差的 Prompt**：`"花园"`

### 错误处理

| 退出码 | 含义         | 处理方式                                      |
| ------ | ------------ | --------------------------------------------- |
| 0      | 成功         | 从 stdout 获取图片路径                        |
| 1      | 参数错误     | 检查是否设置了 DUCKY_PRIVATE_TOKEN 和必填参数 |
| 2      | API 调用失败 | 检查网络连接、Token 有效性、Ducky 服务状态    |
| 3      | 其他错误     | 查看 stderr 中的详细错误信息                  |
