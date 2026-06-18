# APG 建议模板和 Docusaurus 参考

当用户希望快速创建 Docusaurus 文档/产品站点，或需要理解 APG 生成项目结构时使用本参考。APG 是 Aone Pages 推荐的站点模板和快速起点，不是使用 Aone Pages 的前置条件。

## APG

APG 即 Aone Pages Generator，是基于 Docusaurus、由 Yeoman 驱动的静态站点模板生成器。用户也可以使用任意其他静态站点生成器，只要最终产出可部署的静态文件。

前置要求：

- Node.js >= 18
- tnpm >= 10

安装：

```bash
tnpm install -g yo
tnpm install -g @ali/generator-aone-pages@latest
```

创建项目：

```bash
yo @ali/aone-pages <your-project-name>
```

在当前目录生成文件：

```bash
yo @ali/aone-pages <your-project-name> --local
```

常用选项：

| 选项 | 默认值 | 用途 |
| --- | --- | --- |
| `local` | `false` | 在当前目录中生成模板文件。 |
| `ci` | `false` | CI 模式；跳过依赖安装和开发服务器启动。 |
| `name` | `您的网站名称` | 用于生成模板中的网站名称。 |
| `url` | `https://pages.alibaba-inc.com/` | 网站 URL。 |
| `repo` | `https://pages.alibaba-inc.com/` | 编辑链接使用的仓库 URL。 |

## 生成站点结构

APG 站点是 Docusaurus 站点。常见路径：

- `docs/`：产品文档。所有产品文档都应放在这里。
- `docusaurus.config.ts`：站点标题、导航栏、页脚、文档配置、主题配置。
- `sidebars.ts`：文档侧边栏。
- `src/pages/index.tsx`：首页。
- `src/css/custom.css`：全局主题色。
- `static/img/`：logo、favicon 和静态图片。
- `i18n/en/docusaurus-plugin-content-docs/current/`：英文文档镜像。

## 编写约定

- 文档文件名使用 `01-`、`02-` 等数字前缀控制顺序。
- 维护中英文文档时，保持 `docs/` 与 `i18n/en/docusaurus-plugin-content-docs/current/` 的结构一致。
- 在 `i18n/en/docusaurus-plugin-content-docs/current.json` 中翻译侧边栏或目录名称。
- 自定义新 APG 站点前，先搜索生成的模板占位字段。
- 首页页脚内容配置在 `docusaurus.config.ts` 中。

## 本地行为

`npm start` 下搜索和多语言支持可能不会生效。需要更接近线上效果的预览时，运行：

```bash
npm run build
npm run serve
```
