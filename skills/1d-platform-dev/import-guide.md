# 外部项目导入适配（从其他 AI 平台迁移）

> 适用场景：在 Bolt / v0 / Cursor / Claude Code 等平台生成的项目，导入 OneDay 后持续显示「加载中...」或白屏。

## 根因速查：五层问题

| 层级 | 症状 | 根因 | 致命度 |
|------|------|------|--------|
| L1 | 文件体积 > 1MB | Base64 内嵌二进制依赖（React/ReactDOM 等）直接写入 HTML `<script>` | 🔴 致命 |
| L2 | 加载卡死 / WebContainer 内存溢出 | `<script type="text/babel">` + Babel Standalone 运行时编译 JSX | 🔴 致命 |
| L3 | 加载成功但功能全无 | 无构建工具（webpack/vite），所有组件写在单个 `<script>` | 🟡 严重 |
| L4 | API / 数据加载失败 | `fetch('./data.json')` 等相对路径被平台 `/_p/{PORT}/` 前缀破坏 | 🟡 严重 |
| L5 | JS 正常但页面空白 | 缺少 HtmlWebpackPlugin，bundle.js 未注入 HTML | 🟢 中等 |

## 导入前自检（有任一项即需迁移）

```bash
# 检查 Babel Standalone（L2）
grep -r "text/babel\|babel\.min\.js\|babel\.standalone" .

# 检查 Base64 内嵌脚本（L1）
grep -r "data:text/javascript;base64\|src=\"data:" . | head -5

# 检查文件体积（L1）
find . -name "*.html" -size +500k

# 检查构建体系（L3）
ls package.json webpack.config.js 2>/dev/null || echo "⚠️ 无构建体系"

# 检查相对路径 fetch（L4）
grep -r "fetch(['\"]\./" src/ --include="*.js" --include="*.ts"
```

## 迁移路径

### 情况 A：单文件 HTML（最常见）

外部 AI 平台最常输出「单文件 HTML + Babel Standalone + Base64 依赖」。

1. **新建标准 webpack 项目**（参照 `webcontainer.md`），不要在原文件上修改
2. 把 `<script type="text/babel">` 内的 JSX 代码拆分为独立 `.tsx` 模块（每个组件单文件，≤ 260 行）
3. 用 `require('../data.json')` 替换所有 `fetch('./xxx.json')` 静态数据加载（打包内联，绕过路径问题）
4. 动态数据改用 `/api/xxx` 代理路径，配置 webpack proxy 转发到 Express

### 情况 B：已有 npm 项目但用了 Vite/esbuild

直接迁移到 webpack（参照 `webcontainer.md`）；Rollup WASM 在 WebContainer 内不兼容。

### 情况 C：React 组件正确但路径失效

只需修复 fetch 路径：

```js
// ❌ 相对路径，被 /_p/3019/ 前缀破坏
fetch('./data.json')

// ✅ 方式1：require 内联到 bundle（适合静态数据）
const data = require('../data.json');

// ✅ 方式2：代理路径（适合动态 API）
fetch('/api/data')  // webpack proxy → Express :3020
```

## 文件规模约定

| 指标 | 建议上限 | 超出时处理 |
|------|---------|-----------|
| 单个组件文件 | 260 行 | 按职责拆分子组件 |
| 入口 HTML 文件 | 30 行（模板） | 所有逻辑移入 JS 模块 |
| 静态 JSON 数据 | 500KB | 超出改用 Express API 或 OneDay Cloud |
| bundle 产物 | 3MB | 启用 code splitting / 动态 import |

## 迁移效果参考

| 指标 | 迁移前（单文件 HTML）| 迁移后（webpack）|
|------|--------------------|--------------------|
| 文件数量 | 1 个 | 10–20 个模块化文件 |
| 入口文件体积 | 4–8MB | < 50KB（模板） |
| bundle 体积 | 无（运行时编译）| 1–3MB（构建时编译）|
| WebContainer 加载 | 超时 / 失败 | < 3 秒 |
| 可维护性 | 单文件 1000+ 行 | 每文件 < 260 行 |

## 常见问题

| 症状 | 根因 | 解决 |
|------|------|------|
| 迁移后白屏，bundle.js 404 | 缺少 HtmlWebpackPlugin | 添加插件，自动注入 `<script>` |
| 样式全失效 | 忘记安装 css-loader / style-loader | `anpm install css-loader style-loader -D` |
| `require is not defined`（浏览器运行时） | 把 Node.js 的 `require()` 写在了前端代码里 | 改用 `import` 或 webpack alias |
| 图片/字体 404 | asset 没配 webpack `asset/resource` | module.rules 添加 `type: 'asset/resource'` |
| 数据为空但无报错 | fetch 路径被前缀破坏，服务端返回 HTML 被当成 JSON | 用 `require()` 内联或改为 `/api/` 代理路径 |

## 根本原因总结

如果项目**一开始就在 OneDay 里用 webpack 模板创建**，以上所有问题都不会发生。问题的根源是其他 AI 平台生成了「Babel Standalone + Base64 内嵌 + 单文件巨型 HTML」这种不适合 WebContainer 运行环境的代码结构。
