# 部署参考

配置或解释 Aone Pages 部署时使用本参考。用户只要表达“部署 pages / 更新 pages / 发布 pages / deploy pages / 重新发一版 pages”等语义，都优先按 Aone CI 官方模板 `部署Aone Pages` 处理，不要因为用户没说“CI 任务”就改成手动部署或新写 YAML。

## 核心流程

1. 创建或准备静态站点。Aone Pages 不绑定固定生成器，只要能产出静态文件即可。
2. 将代码推送到 Code 仓库。CI 部署的是远端 commit，不会部署本地未提交或未推送的改动。
3. 确认站点名称、构建命令、静态产物目录和正式分支。
4. 使用 Aone CI 官方模板 `部署Aone Pages` 创建或复用流水线。
5. 通过 `https://<site-name>.io.alibaba-inc.com` 访问正式站点；预览地址从部署 job summary 获取。

APG 是推荐的 Docusaurus 快速模板，但 Jekyll、Hugo、MkDocs、Vite、Astro、Next.js 静态导出、VitePress、VuePress 或纯静态 HTML/CSS/JS 都可以部署。

## a1 CLI 前置检查

操作 Aone CI 前应确认仓库绑定状态：

```bash
a1 link status -f json
```

如果未绑定，使用 `a1 repo link` 绑定当前仓库，或在命令中显式传 `--repo <group/project>`。

## 创建前查重

部署 Aone Pages 的官方模板 ID 是 `10014197`。创建前先查是否已有正常流水线：

```bash
a1 ci pipeline list --repo <group/project> --template-id 10014197 --status NORMAL
```

- 如果已有 `NORMAL` 流水线，不要重复创建；反馈 id/name，让用户决定复用、更新还是禁用旧任务。
- 如果没有，或只有 `DISABLED` 流水线，再创建新流水线。

## 本地代码检查

在“开发完立刻部署看效果”的语境下，先检查本地是否还有没进入远端的改动：

```bash
git status --porcelain
git rev-list --count @{u}..HEAD 2>/dev/null || echo NA
```

- `git status --porcelain` 非空：有未提交或未跟踪改动。
- `rev-list` 输出大于 0：有已 commit 但未 push 的提交。
- `rev-list` 输出 `NA`：没有 upstream，按未 push 处理。

## 推导构建命令和产物目录

模板默认假设是 npm 项目，构建命令为：

```bash
npm install --registry=https://registry.anpm.alibaba-inc.com
npm run build
```

默认产物目录为 `build/`。与默认一致时可省略参数；不一致时通过模板参数覆盖：

```bash
--param build-website-command='<构建命令>'
--param deploy-dir=<产物目录>
```

### 非 Node 静态站点

| 特征文件 | `build-website-command` | `deploy-dir` |
| --- | --- | --- |
| `config.toml` + `themes/` | `hugo --minify` | `public` |
| `_config.yml` + `Gemfile` | `bundle install && bundle exec jekyll build` | `_site` |
| `mkdocs.yml` | `pip install -r requirements.txt && mkdocs build` | `site` |

### 纯静态文件

如果仓库没有 `package.json`，也没有上述生成器配置：

- 可部署文件集中在干净子目录，如 `public/`、`dist/`、`docs/`：跳过构建并将 `deploy-dir` 指到该目录。

```bash
--param build-website-command=':'
--param deploy-dir=public
```

- 可部署文件散在仓库根目录：不要使用 `--param deploy-dir=.`。应把需要发布的文件复制到干净目录，例如：

```bash
--param 'build-website-command=mkdir -p build && cp index.html digest-*.html style.css build/'
```

先用 `ls -A` 或 `a1 repo file list .` 看清实际文件，再列出要发布的文件。

### Node.js 项目

读取 `package.json` 和框架配置：

```bash
jq '.scripts' package.json
ls vite.config.* next.config.* astro.config.* docusaurus.config.* 2>/dev/null
```

常见产物目录：

| 框架 | 默认产物目录 |
| --- | --- |
| Docusaurus | `build` |
| Vite / Astro | `dist` |
| Next.js 静态导出 | `out` |
| VitePress | `docs/.vitepress/dist` |
| VuePress | `docs/.vuepress/dist` |

如果配置文件显式修改了 `outDir` 或 `build.outDir`，以配置为准。脚本不是 `build`，例如 `docs:build` 或 `pages:build`，必须显式传 `build-website-command`。

无法推导时，停下询问用户“构建命令是什么？产物在哪个目录？”，不要凭感觉填 `npm run build`。

## 创建流水线

```bash
a1 ci pipeline create \
  --repo <group/project> \
  --template-id 10014197 \
  --name "部署Aone Pages" \
  --param site-name=<站点名> \
  --param build-website-command='<非默认构建命令>' \
  --param deploy-dir=<非默认产物目录> \
  --trigger-push-branch '**' \
  --trigger-mr-target-branch '**' \
  --trigger-mr-type opened
```

关键点：

- `site-name` 默认必带。命名规则：小写字母、数字、连字符，长度 1-64，不以连字符开头或结尾。用户没指定时可用仓库名小写化作为默认值；如果仓库名含大写、下划线、点等不合规字符，先询问用户，不要偷偷转换。
- `production-branch` 默认是 `master`。如果仓库默认分支不是 `master`，创建时追加 `--param production-branch=<默认分支>`。
- 默认分支用下面命令获取，不要用 `git branch --show-current`：

```bash
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'
```

如果该命令返回空（常见于 shallow clone、`--single-branch` 克隆或 `origin/HEAD` 未设置的仓库），应询问用户确认默认分支名称，不要猜测。

- `'**'` 表示所有分支。`production-branch` 触发正式版本，其他分支或 CR 触发预览版本。
- CI 当前不支持通过 `pipeline update --param site-name` 或同项目新流水线更新 `site-name`。如需调整站点名称，到 Code 仓库的 `设置` -> `Pages` 页面修改。

## 获取部署地址

run 终态为 `SUCCESS` 后，访问地址只在部署 job 的 summary 中，以 Markdown 链接形式出现，例如 `[网站地址](https://...)`。不要从 `a1 ci run get` 输出或日志里猜 URL，也不要用 run-id 拼 URL。

```bash
a1 ci job list --run <run-id>
a1 ci job summary <job-id> --run <run-id>
```

如果 summary 没有 `[网站地址]` 链接，先确认 run 是否已成功：

```bash
a1 ci run get <run-id>
```

## 维护已有 YAML

APG 生成的项目可能已包含 `.aoneci/deploy-pages.yaml`。只有在用户明确维护已有 CI 文件，或不能通过模板创建时，再编辑 YAML：

```yaml
name: deploy-pages

triggers:
  push:

jobs:
  deploy:
    image: alios-8u
    steps:
      - uses: checkout
      - uses: setup-env
        inputs:
          node-version: 20
          tnpm-version: 10
      - id: build-website
        run: |
          npm install --registry=https://registry.anpm.alibaba-inc.com
          npm run build
      - uses: deploy-pages
        inputs:
          deploy-dir: build/
          production-branch: master
          site-name: my-site
```

如需校验 YAML：

```bash
a1 ci yaml lint .aoneci/deploy-pages.yaml --repo <group/project> --ref <branch>
```
