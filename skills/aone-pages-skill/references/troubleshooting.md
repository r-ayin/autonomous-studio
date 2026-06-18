# 故障排查参考

处理 Aone Pages 常见问题和 Aone CI 部署问题时使用本参考。

## FAQ 事实

- 不支持回滚。发生错误后，需要修复问题并重新发布。
- 预览版本会在 90 天后过期。
- 只有推送分支匹配 `production-branch` 时才会创建正式版本。
- 其他分支或 CR 会创建预览版本。

## 只能生成预览版本

检查 `production-branch` 和触发分支是否一致。模板方式创建的流水线，查看流水线配置：

```bash
a1 ci pipeline get <pipeline-id>
```

已有 YAML 项目检查 `deploy-pages` 步骤：

```yaml
- uses: deploy-pages
  inputs:
    deploy-dir: build/
    production-branch: master
```

如果仓库默认分支不是 `master`，创建模板流水线时应传：

```bash
--param production-branch=<默认分支>
```

## 找不到部署后的访问地址

访问地址只在部署 job 的 summary 中，不在 `a1 ci run get`、`a1 ci run log` 或 `a1 ci job log` 日志中。run 成功后执行：

```bash
a1 ci job list --run <run-id>
a1 ci job summary <job-id> --run <run-id>
```

从 summary 中提取 `[网站地址](<url>)`。不要凭 run-id 拼 URL。

## `/path` 返回 404

Aone Pages 会将 `/path` 解析为 `/path/index.html`。如果部署后的静态产物中不存在该文件，则该路径会返回 404。

检查：

1. 静态生成器的路由或 base path 配置。
2. 构建产物中是否包含 `path/index.html`。
3. `deploy-dir` 是否指向真实的静态产物目录。

## 部署的不是本地最新内容

CI 只部署远端 commit。检查本地是否有未提交或未推送内容：

```bash
git status --porcelain
git rev-list --count @{u}..HEAD 2>/dev/null || echo NA
```

- 第一条非空：有未提交或未跟踪内容。
- 第二条大于 0：有已提交但未 push 内容。
- 第二条为 `NA`：没有 upstream，按未 push 处理。

## 构建产物目录错误

如果页面缺文件、404 或部署了源码文件，检查 `deploy-dir`：

- Docusaurus 默认 `build`。
- Vite / Astro 默认 `dist`。
- Next.js 静态导出默认 `out`。
- Hugo 默认 `public`。
- Jekyll 默认 `_site`。
- MkDocs 默认 `site`。

不要将 `deploy-dir` 设置为 `.`，除非仓库根目录就是干净、可直接公开的静态产物目录。更常见的做法是构建或复制到干净目录后发布。

## CI 运行失败

查看 run 和 job：

```bash
a1 ci run get <run-id>
a1 ci job list --run <run-id>
a1 ci job log <job-id> --run <run-id>
```

如果只想重跑失败 job：

```bash
a1 ci run rerun-failed-jobs <run-id> --watch
```

如果是 YAML 配置问题，先 lint：

```bash
a1 ci yaml lint .aoneci/deploy-pages.yaml --repo <group/project> --ref <branch>
```
