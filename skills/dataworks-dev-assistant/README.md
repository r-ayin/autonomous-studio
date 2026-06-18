# DataWorks 助手

操作 DataWorks 平台的 agent skill。让 AI agent 通过 BFF 接口查询和操作 DataWorks 平台。

## 安装

### 1. 安装 Python 依赖

需要 Python >= 3.8。

```bash
pip install -r requirements.txt
```

### 2. 配置认证

**获取 Token**：访问 https://dw.alibaba-inc.com/dmc/skill-auth 获取个人 Token。

**配置 Token**（二选一）：

方式一：写入配置文件（推荐）
```bash
mkdir -p ~/.dataworks
cat > ~/.dataworks/.env << 'EOF'
BFF_TOKEN=your_token_here
BFF_ENDPOINT=http://bff.dw.alibaba-inc.com
EOF
```

方式二：直接设置环境变量（优先级更高，会覆盖 .env 文件）
```bash
export BFF_TOKEN=your_token_here
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `BFF_TOKEN` | 必填，Personal Token | — |
| `BFF_ENDPOINT` | BFF 网关地址 | — |
| `BFF_ENV` | 环境名（BFF_ENDPOINT 未设置时生效） | — |

可用环境名：cn-hangzhou、cn-shanghai、cn-beijing、cn-shenzhen、cn-guangzhou、cn-chengdu、cn-hongkong、ap-southeast-1 等。支持中文别名（北京、上海、杭州）。

### 3. 安装 Skill

在 agent 中启用本 skill（Claude Code / Qwen Code 均支持）。

## 使用方式

安装后 agent 会自动识别触发词并加载 skill。直接用自然语言提问即可：

- "查一下 m_task_sql 表的血缘"
- "工作空间 14255 有哪些数据源"
- "表 xxx 的历史产出情况"
- "帮我看看失败的任务实例"
- "任务 178434076 运行正常吗"
- "帮我重跑实例 92550586011"
- "ods_order 表好像停止产出了，帮我排查一下"

## 支持的能力

| 领域 | 示例 |
|------|------|
| 数据发现 | 查表、搜表、表详情、表结构、血缘、分区、历史产出 |
| SQL 执行 | 执行 SQL、跑 SQL |
| 节点管理 | 查看代码、创建节点、工作流管理 |
| 发布部署 | 提交发布、检查器分析 |
| 任务运维 | 任务实例、冒烟测试、补数据、重跑、终止 |
| 数据集成 | 创建离线同步任务 |
| 数据治理 | 治理规则、告警规则、数据质量 |
| 资源管理 | 数据源、资源组 |
| 审批流 | 审批策略管理 |
| 工作空间 | 项目列表、成员管理、角色管理 |

## 致谢与说明

本 skill 在 **dw-bff-kits**（作者：@乾离）的基础上开发，在此真诚感谢乾离同学提供了优秀的底层 BFF 客户端框架，以及在开发过程中的耐心指导和帮助。

在原有能力的基础上，主要做了以下方向的补充和优化：

- **补数据**：新增两层状态轮询（DAG 创建 vs 实例执行分离）、失败时自动拉取报错日志、规范化 `--start/--end` 时间参数
- **UDF 开发**：新增 `--class-name` 参数支持、完善 Python 版本陷阱说明（ODPS 默认 Python 2 导致 f-string 报错）、增加 `view_udf.py` 查看源码能力
- **发布描述**：`deploy_node.py` 支持 `--description` 参数，发布时可附带说明
- **节点调度参数**：新增 `update_node_code.py --param` 支持命令行设置 `bizdate` 等调度变量，规避 `updateVertex` 对 `script.parameters` 的服务端 bug
- **开发习惯管理**：集成会话级习惯观察与持久化（`~/.dataworks/dev_habits.md`），避免同类问题重复踩坑
- **运行时路径**：将会话状态、backlog 等运行时文件从工作目录统一迁移至 `~/.dataworks/`，多项目切换不再互相干扰
- **SKILL.md 文档**：将实际使用中积累的 API 陷阱、规范速查、意图路由等整合进文档，降低 agent 踩坑概率

以上改动均已通过实际业务场景验证。如有任何问题或建议，欢迎反馈。
