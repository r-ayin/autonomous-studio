---
name: aone-pages-skill
version: 0.1.0
description: Aone Pages 使用工作流，用于创建、部署、配置和排查托管在 Aone Pages 上的静态站点。Use when users publish static sites with Aone Pages, configure Aone CI deploy-pages, choose or adapt APG/Docusaurus templates, bind custom domains, troubleshoot preview/production releases, or answer questions about pages.alibaba-inc.com.
x-source: aone-open
repository: https://code.alibaba-inc.com/qunbu/aone-pages-skill
---

# Aone Pages

## 概览

使用本 skill 帮助用户将任意静态站点发布到 Aone Pages。APG 是推荐的 Docusaurus 站点模板和快速起点，但 Aone Pages 不绑定 APG；只要能产出静态文件，Jekyll、Hugo、Docusaurus 或其他生成器都可以部署。

## 信息来源顺序

1. 先阅读用户目标仓库中的相关文件。
2. 只按需加载本 skill 中相关的参考文件：
   - `references/deployment.md`：站点设置、Aone CI、deploy-pages、预览/正式发布、访问 URL。
   - `references/apg-docusaurus.md`：APG 建议模板和生成的 Docusaurus 站点结构。
   - `references/custom-domains.md`：自定义域名配置。
   - `references/troubleshooting.md`：常见故障和 FAQ 行为。

## 工作流

1. 确认站点来源：
   - 已有静态站点：确认构建命令和静态产物目录，例如 `build/`、`dist/` 或 `public/`。
   - 新建文档/产品站点：可建议 APG 作为 Docusaurus 模板；如果用户已有技术栈，沿用其静态站点生成器。
2. 确认发布目标：
   - 站点名称：用于默认访问域名 `https://<site-name>.io.alibaba-inc.com`。
   - 正式分支：配置为 `deploy-pages` 的 `production-branch`。
   - 自定义域名：如需要，先完成统一接入，再在仓库 Pages 设置中配置。
3. 配置部署：
   - 用户表达“部署/更新/发布 pages”时，优先按 Aone CI 官方模板 `部署Aone Pages` 处理。
   - 使用 a1 CLI 创建流水线时，读取 `references/deployment.md` 中的模板 ID、查重、本地代码检查、构建命令推导和创建命令。
   - APG 项目可能已包含 `.aoneci/deploy-pages.yaml`；仅在用户要维护已有 YAML 或不使用模板创建时编辑 YAML。
   - 如果 CI 中构建站点，确保 `deploy-dir` 指向构建产物目录；如果产物已提交，可跳过构建。
4. 判断发布结果：
   - 推送分支匹配 `production-branch` 时生成正式版本。
   - 其他分支生成预览版本。
5. 排查问题：
   - 只能生成预览版本：检查触发分支和 `production-branch`。
   - 页面路径 404：检查静态产物是否包含对应的 `index.html`。
   - 自定义域名异常：检查统一接入和 Pages 自定义域名配置。
   - 需要获取部署后的访问地址：从部署 job summary 中读取 `[网站地址](<url>)`，不要从 run get 或日志里猜 URL。

## 编写指导

- 编写部署自动化示例时，优先展示 `a1 ci pipeline create --template-id 10014197`；只有维护已有 CI 文件时再展示包含 `deploy-pages` 的 YAML。
- 说明 `production-branch` 控制正式发布；其他分支会创建预览版本。
- 当仓库 Pages 设置页可能尚未配置站点时，包含 `site-name`。
- 使用 `https://<site-name>.io.alibaba-inc.com` 作为默认站点 URL 格式。
- 说明 Aone Pages 支持常见静态站点生成器，并不绑定 APG；APG 只是建议模板和快速起点。
- 编写 APG 文档时，保留 Docusaurus 约定：`docs/` 存放文档，`static/img/` 存放 logo 和静态资源，`docusaurus.config.ts` 配置全局信息和页脚，英文文档镜像位于 `i18n/en/docusaurus-plugin-content-docs/current`。

## 约束

- 不要声称支持回滚；Aone Pages 不支持回滚。
- 不要承诺预览 URL 永久可用；预览版本保留 90 天。
- 排查 `/path` 404 时，检查静态生成器是否产出 `/path/index.html`。
- 不要编造未文档化的 API。给出 API 级实现建议前，先检查后端仓库或部署组件。
