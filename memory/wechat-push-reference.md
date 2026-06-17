---
name: wechat-push-reference
description: 微信推送可复用方案 → 已提升为 [[wechat-push]] Skill，本文件保留作为实现细节参考
metadata:
  type: reference
---

# 微信推送 — 已提升为 Skill

> **主要入口现在是 `wechat-push` skill。** 说"发微信"即可自动触发。
> 本文件保留作为底层实现参考（`wechat_push.py` 源码细节）。

## Skill 位置

`.claude/skills/wechat-push/SKILL.md`

## 实现文件

`E:\x-tool\pachong-master\pipeline\wechat_push.py`

## 前置条件（简要）

- Hermes/OpenClaw gateway 在 WSL 中运行，已扫码登录微信 Bot
- `hermes config` 已配置 WEIXIN_HOME_CHANNEL 和 WEIXIN_TOKEN
- `wechat_push.py` 自动处理 Windows↔WSL 桥接 + 限流重试
