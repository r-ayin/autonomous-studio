---
name: zujianfuyon-skill
version: 1.0.1
description: 组件复用技能 — 管理通用可复用组件仓库（zujianfuyon）。触发词："复用这个组件"、"从组件仓库拉取"、"写入组件仓库"。支持双向操作：从业务项目抽离组件到仓库，或从仓库拉取组件到当前项目。当某段代码反复修 bug ≥3 次后稳定时，应主动建议收录。
metadata:
  author: xiqxhq
  triggers:
    - 复用这个组件
    - 组件仓库
    - 写入复用仓库
    - 从仓库拉取
    - 抽离组件
repository: https://code.alibaba-inc.com/qunbu/zujianfuyon-skill
---

# 组件复用技能（zujianfuyon-skill）

管理通用可复用组件仓库 `gitlab.alibaba-inc.com/xiqxhq/zujianfuyon.git`，支持组件的抽离、收录、拉取和更新。

## When to Use

### 主动触发

- 用户说"复用这个组件"、"写入组件仓库"、"抽离到复用仓库"
- 用户说"从组件仓库拉取 xxx"、"看看仓库里有没有 xxx"
- 用户说"更新组件仓库的 xxx"

### 自动建议（AI 应主动提示）

当检测到以下情况时，AI 应询问用户是否收录到组件仓库：

1. **同一段逻辑在 ≥2 个项目中出现**
2. **某个功能模块反复修 bug ≥3 次后终于稳定** — 固化为组件避免回退
3. **用户手动复制粘贴代码到另一个项目**
4. **数据解析/格式处理逻辑经过多轮调优** — CSV 解析边界 case 处理等

建议话术：`"这个 [xxx] 经过多次调优已经稳定了，要不要抽离到组件仓库复用？"`

## 仓库信息

- **地址**：`https://gitlab.alibaba-inc.com/xiqxhq/zujianfuyon.git`
- **本地克隆路径**：`/tmp/zujianfuyon`（如不存在则克隆）
- **分支**：`master`

## Steps — 写入组件到仓库（抽离）

### Step 1: 克隆/更新仓库

```bash
if [ -d /tmp/zujianfuyon/.git ]; then
  cd /tmp/zujianfuyon && git pull origin master
else
  git clone https://gitlab.alibaba-inc.com/xiqxhq/zujianfuyon.git /tmp/zujianfuyon
fi
```

### Step 2: 读取仓库 CLAUDE.md 获取编码原则

```bash
cat /tmp/zujianfuyon/CLAUDE.md
```

遵循其中的"编码原则"和"从业务项目抽离组件的检查清单"。

### Step 3: 创建组件文件夹

在 `/tmp/zujianfuyon/<component-name>/` 下创建：

1. **实现文件**（`.ts` / `.tsx`）— 从业务项目中复制代码，按检查清单剥离业务逻辑
2. **`index.ts`** — 统一导出所有公开 API 和类型
3. **`README.md`** — 包含：用途、依赖、使用示例、API 说明

### Step 4: 更新根目录索引

编辑 `/tmp/zujianfuyon/README.md`，在组件目录表格中添加新条目。

### Step 5: 提交推送

```bash
cd /tmp/zujianfuyon
git add <component-name>/
git add README.md
git commit -m "feat: <组件名>（<一句话说明>）"
git push origin master
```

## Steps — 从仓库拉取组件（引用）

### Step 1: 克隆/更新仓库

同上。

### Step 2: 查看可用组件

```bash
cat /tmp/zujianfuyon/README.md
```

根据用户需求匹配合适的组件。

### Step 3: 复制组件到当前项目

```bash
cp -r /tmp/zujianfuyon/<component-name>/ <目标路径>/
```

### Step 4: 适配业务

- 根据当前项目的路径别名（如 `@/`）调整 import
- 注入业务配置（URL、Key 等）
- 如需定制，在业务层 wrap，不修改组件源码

## Steps — 更新已有组件

### Step 1: 克隆/更新仓库

同上。

### Step 2: 修改组件代码

按 CLAUDE.md 中"更新组件流程"操作。

### Step 3: 同步到引用该组件的项目

如果当前项目中有该组件的副本，同步最新代码。

### Step 4: 提交推送

```bash
cd /tmp/zujianfuyon
git add <component-name>/
git commit -m "fix: <组件名> <修复内容>"  # 或 feat:
git push origin master
```

## 组件分类

| 类别 | 保留 | 剥离 |
|------|------|------|
| UI 组件 | 渲染逻辑、交互、响应式、空状态 | 数据获取、路由、全局状态 |
| 接入客户端 | 协议封装、请求构建、响应解析 | 硬编码 endpoint、Token |
| 数据解析 | 格式检测、结构转换、容错、编码处理 | 业务列名映射、校验规则 |

## 剥离检查清单

抽离前逐项确认：

- [ ] 移除所有业务项目的 import 路径
- [ ] 移除写死的 URL/Token/用户名
- [ ] 移除全局状态依赖
- [ ] 移除业务专属 type（改为泛型或组件内定义）
- [ ] 确认空项目中 import 无报错
- [ ] README 示例可独立运行

## Notes

- 组件命名使用 kebab-case（如 `dingtalk-mcp-client`、`echarts-bar`）
- 每个组件必须有 `index.ts` 和 `README.md`
- 允许提供 DEFAULT 常量但必须支持覆盖
- 优先使用浏览器原生 API，最小化外部依赖
