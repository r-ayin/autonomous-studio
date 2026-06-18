# WebContainer 项目配置详解

OneDay 项目运行在**浏览器沙箱（WebContainer）**中，不可用原生 Node 模块(.node)、部分 WebAssembly；可用纯 JavaScript 模块和内存虚拟文件系统。

## 代理注册机制（最重要）

平台**只拦截 `webpack serve`**，不拦截 `node server.js`。

- `npm run dev` 必须等于 `webpack serve`
- 直接 `node server.js` → 预览永远空白 / 卡在 90%

## webpack-dev-server 版本

**必须使用 4.x**（`"webpack-dev-server": "^4.15.2"`）。5.x 在 WebContainer 中存在兼容性问题，导致页面空白。

## Express 后台启动（最易踩坑）

**绝对禁止**在 webpack 钩子（`onListening`、`setupMiddlewares`）中用 `require()` 或 `child_process` 拉起 Express。

**症状**：页面显示 `Cannot GET /index.html`（Express 默认 404 格式）

**正确方式** — 使用 npm `predev` 钩子：

```json
{
  "scripts": {
    "predev": "node server/index.js &",
    "dev": "webpack serve --mode development",
    "dev:full": "concurrently -n server,webpack \"node server/index.js\" \"webpack serve --mode development\""
  }
}
```

**为什么 `predev`+`&` 可行而 `onListening` 不行**：
- `predev` 在独立 shell 中执行，Express 作为独立后台进程（平台不感知）
- `onListening` 在 webpack 进程中同步 `require()`，Express 监听 3020 被平台检测到，代理优先路由到 Express 而非 webpack-dev-server

## 标准双层架构

```
平台代理 (1d.alibaba-inc.com)
    ↓
webpack-dev-server :3019  ← 平台拦截，注册代理
    ├── 静态页面: 直接响应
    ├── API代理: /api → proxy → Express :3020
    └── SPA fallback: historyApiFallback

Express :3020  ← 平台不感知，仅内部使用
```

## webpack.config.js 关键配置

```js
module.exports = {
  mode: process.env.NODE_ENV === 'production' ? 'production' : 'development', // ⚠️ 必须动态
  output: {
    publicPath: 'auto', // ⚠️ 不能用 '/'，否则 JS/CSS 404
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.js',
  },
  devServer: {
    port: 3019,                                    // ⚠️ 固定，平台会注入 --port 3000 但必须忽略
    allowedHosts: ['all', '.alibaba-inc.com'],     // ⚠️ 缺少则请求被拒
    historyApiFallback: {
      index: '/index.html',
      rewrites: [{ from: /^\/_p\/\d+\//, to: '/index.html' }],
    },
    proxy: [{
      context: ['/api', '/health', '/ping'],
      target: 'http://localhost:3020',
      changeOrigin: true,
    }],
  },
  externals: {
    // ⚠️ 必须用 var 前缀，不能用 commonjs（发布后 iframe 无 require）
    '@ali/oneday-frontend-sdk': 'var (typeof oneday !== "undefined" ? oneday : { createClient: function() { return null; } })',
    '@supabase/supabase-js': '{}',
  },
};
```

三个缺一不可：`allowedHosts`、`historyApiFallback`、`port: 3019`。

## mode 必须动态切换

```js
// ✅ 正确
mode: process.env.NODE_ENV === 'production' ? 'production' : 'development',

// ❌ 硬编码 development → 发布后白屏（HMR/WebSocket 代码打入 bundle，发布环境无 dev server）
mode: 'development',
```

## 路由：必须 HashRouter

```tsx
import { HashRouter, Routes, Route } from 'react-router-dom';
// ❌ 禁止 BrowserRouter — 代理层无法配置服务端 fallback → 页面刷新 404
```

## Express 配置要点

- 必须用 `app.listen(PORT, "0.0.0.0")`，禁止 `http.createServer()`
- `app.listen()` 返回 `undefined` 是正常的（WebContainer 拦截）
- 设置 `app.set("trust proxy", true)` + CORS 允许所有来源

## externals 配置详解（Cloud 连接必需）

```js
// ✅ 正确 — var 前缀 + 安全降级
'@ali/oneday-frontend-sdk': 'var (typeof oneday !== "undefined" ? oneday : { createClient: function() { return null; } })',

// ❌ 错误1 — 缺少 var 前缀，webpack 解析行为不确定
'@ali/oneday-frontend-sdk': '(typeof oneday !== "undefined" && oneday ? oneday : ...)',

// ❌ 错误2 — commonjs 在发布后的 iframe 中无 require()，必然失败
'@ali/oneday-frontend-sdk': 'commonjs @ali/oneday-frontend-sdk',
```

**TerserPlugin**：`drop_console: true` 会删除所有 `console.log`，Cloud 连接诊断日志丢失，建议设为 `false`。

## 平台特有机制

| 机制 | 说明 |
|------|------|
| anpm | 阿里 npm 封装，依赖安装用 `anpm install`（不是 npm/pnpm/yarn） |
| 子路径代理 | `/_p/{PORT}/` 前缀，fetch 相对路径会被破坏（用 `/api/` 或 `require()` 内联） |
| 平台注入 --port | 平台会注入 `--port 3000`，代码必须固定 3019，忽略注入值 |
| 预览子域名 | `preview-{id}.pre-fn.alibaba-inc.com` |
| 1D.md | 文件语义元数据，含 `ONEDAY_FILE_SEMANTIC` JSON 区块 |

## 项目初始化步骤

1. `anpm install`（不是 npm/pnpm/yarn）
2. `npm run dev` = `webpack serve`
3. 端口固定 3019（webpack-dev-server）和 3020（Express）

## 导入已有项目至 1D

前置条件：开启 Studio 模式 → 使用「OneDay前端项目启动助手」Skill → 安装「OneDay辅助编程插件」

- `package.json` 必须包含 `dev` 命令
- 确保运行环境为 sandbox（远程沙盒）
- 默认启动命令：`npm run dev -- --port=3015 --host 0.0.0.0`
- 不支持 `--port` 方式时手动改 package.json（如 Umi Max：`PORT=3015 npm run dev`）

## 构建产物结构

| 构建工具 | 产物 | CSS 处理 |
|----------|------|---------|
| webpack | `dist/bundle.js` | MiniCssExtractPlugin + HTMLInlineCSSWebpackPlugin 内联至 HTML |
| Vite | `dist/assets/*.js` + `dist/assets/*.css` | 独立 CSS 文件 |

`bundle.html` 必须输出到**项目根目录**（`path.join(__dirname, '..', 'bundle.html')`），发布系统在根目录寻找。

## 发布环境 CSS 处理（关键）

**发布后预览**的加载流程：平台下载 ZIP → 解析 index.html → 将 JS 转为 blob URL 加载。
这意味着：
1. `style-loader` **不可用** — 它在运行时往 `document.head` 插入 `<style>`，但 blob URL 上下文中注入位置可能不对
2. 外部字体文件（`.woff2`）**路径会断** — blob URL 无法解析 `publicPath` 相对路径
3. 外部 CDN（unpkg、cdn.jsdelivr.net 等）**会被拦截** — 集团安全网关将 HTTPS 降级为 HTTP，浏览器因 Mixed Content 策略全部阻断

**正确方案：CSS 全部内联到 HTML `<style>` 标签中**

```js
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const HTMLInlineCSSWebpackPlugin = require('html-inline-css-webpack-plugin').default;

module.exports = {
  output: {
    publicPath: './',  // ⚠️ 必须相对路径，不能用 '/'
  },
  module: {
    rules: [
      {
        test: /\.css$/,
        use: [MiniCssExtractPlugin.loader, 'css-loader', 'postcss-loader']  // ⚠️ 不用 style-loader
      },
      {
        test: /\.(woff|woff2|eot|ttf|otf)$/,
        type: 'asset/inline'  // ⚠️ 字体转 data URI，不依赖外部文件
      }
    ]
  },
  plugins: [
    new MiniCssExtractPlugin(),
    new HtmlWebpackPlugin({ template: './index.html', inject: 'body' }),
    new HTMLInlineCSSWebpackPlugin()  // ⚠️ 提取的 CSS 内联回 HTML
  ]
};
```

**依赖包**：`mini-css-extract-plugin`、`html-inline-css-webpack-plugin`

## 外部依赖禁止使用 CDN

所有第三方库（React、ECharts、Tailwind CSS、Font Awesome 等）**必须本地打包**，不能通过 `<script src="https://cdn.xxx">` 加载。

原因：集团安全网关 `oneagent-filter.alibaba-inc.com` 会将外部 HTTPS 请求降级为 HTTP，浏览器的 Mixed Content 策略会阻断所有请求，导致页面白屏。

```js
// ❌ 错误 — CDN 外链会被安全网关拦截
<script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>

// ✅ 正确 — npm install 后打包到 bundle.js
import React from 'react';
import * as echarts from 'echarts';
```

## 常见问题速查

| 症状 | 根因 | 解决 |
|------|------|------|
| 预览空白 / 卡 90% | 不是 webpack serve | scripts 改为 webpack serve |
| 预览空白（webpack 编译成功） | webpack-dev-server 5.x 不兼容 | 降级到 ^4.15.2 |
| Cannot GET /index.html | Express 在 webpack 钩子中启动 | 改用 predev 钩子后台启动 |
| 发布后白屏 | mode 硬编码 development | 改为 NODE_ENV 动态切换 |
| 发布 forEach 报错 | bundle.html 路径错误或 output.path 写错 | 输出到根目录 + path.resolve(__dirname,'dist') |
| Vite 无响应 | rollup wasm 不兼容 | 迁移到 webpack |
| 页面刷新 404 | BrowserRouter 或未配 fallback | HashRouter + historyApiFallback |
| API 失败 | proxy 缺失 / 端口错 | 检查 webpack proxy |
| JS/CSS 加载 404 | publicPath 配置错误 | 使用 publicPath: './'（发布）或 'auto'（开发） |
| 发布后样式全丢 | style-loader 在 blob URL 上下文不生效 | 改用 MiniCssExtractPlugin + HTMLInlineCSSWebpackPlugin 内联到 HTML |
| 发布后白屏（CDN 依赖） | 外部 CDN 被安全网关 Mixed Content 拦截 | 所有依赖 npm install 后本地打包，去掉 CDN `<script>` |
| 发布后图标不显示 | 字体文件路径在预览环境无法解析 | webpack 字体规则改为 `type: 'asset/inline'`（data URI 嵌入） |
| webpack 配置语法错误 | babel presets 数组缺少逗号 | 检查数组分隔符 |
| 强制同步 ENOTEMPTY | 文件系统异步删除 bug | 刷新重试，停止 dev server 后重试 |
| 卡在 90% 不动 | 浏览器缓存 | 清除缓存或无痕模式 |
| Cloud 开发可用、发布后失效 | externals 用了 commonjs | 改为 var 前缀格式（见 externals 配置详解） |
