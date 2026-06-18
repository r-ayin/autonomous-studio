# 组件索引（快照）

> 本文件是组件仓库 README.md 的快照，用于快速浏览。实际操作时以克隆仓库中的最新内容为准。

---

## 自定义可复用组件

| 组件 | 路径 | 用途 | 依赖 |
|------|------|------|------|
| [钉钉 MCP 客户端](dingtalk-mcp-client/) | `dingtalk-mcp-client/` | 通过 Workflow API 代理读写钉钉文档/电子表格/AI表格，解决 CORS 和 FC 出网限制 | 无（仅 fetch） |
| [ECharts 柱状图](echarts-bar/) | `echarts-bar/` | 基础柱状图 + 堆叠柱状图，支持横向/纵向、dataZoom 滚动 | echarts, react |
| [日期范围选择器](date-range-picker/) | `date-range-picker/` | 自定义日历弹出层，两次点击选起止日期；含 normalizeDate 工具函数和 useDateRangeFilter Hook | react, tailwindcss |
| [钉钉群机器人](dingtalk-robot/) | `dingtalk-robot/` | Webhook + HMAC 加签，发 Markdown 消息（支持 @所有人）+ ActionCard 带跳转按钮 | 无（Web Crypto API） |

---

## 预置 UI 组件集（只读浏览）

### shadcn/ui 组件集（55 个组件）

路径：`shadcn-ui/`，依赖：react, tailwindcss, @radix-ui/*, clsx, tailwind-merge

按功能分为 7 类：
- **base/** — badge, button, button-group, item, kbd, label, separator, spinner
- **form/** — calendar, checkbox, combobox, field, input, input-group, input-otp, native-select, radio-group, select, slider, switch, textarea
- **data-display/** — accordion, avatar, card, carousel, chart, collapsible, empty, hover-card, progress, skeleton, table, aspect-ratio
- **feedback/** — alert, alert-dialog, command, context-menu, dialog, drawer, popover, sheet, sonner, tooltip
- **navigation/** — breadcrumb, dropdown-menu, menubar, navigation-menu, pagination, sidebar, tabs
- **layout/** — direction, resizable, scroll-area, toggle, toggle-group
- **hooks/** — use-mobile.ts

### Ant Design 高级组件（74 个组件）

路径：`antd-components/`，依赖：react, antd 生态

包含完整源码：affix, alert, anchor, back-top, badge, breadcrumb, button, calendar, card, cascader, checkbox, collapse, color-picker, config-provider, date-picker, descriptions, divider, drawer, dropdown, empty, flex, float-button, form, grid, image, input, input-number, layout, list, masonry, mentions, menu, message, modal, notification, pagination, popconfirm, popover, progress, qr-code, radio, rate, result, segmented, select, skeleton, slider, space, spin, splitter, statistic, steps, switch, table, tabs, tag, theme, timeline, time-picker, tooltip, tour, transfer, tree, tree-select, typography, upload, watermark 等。

---

## 快速使用示例

### 钉钉 MCP 客户端

```ts
import { createDingtalkClient, parseNodeIdFromUrl } from './dingtalk-mcp-client';

const client = createDingtalkClient(mcpBaseUrl, mcpKey);
const nodeId = parseNodeIdFromUrl(dingtalkUrl);
const data = await client.getRange(nodeId, 'Sheet1');
```

### ECharts 柱状图

```tsx
import { BarChart, StackedBarChart } from './echarts-bar';
<BarChart data={[{ name: '分类A', value: 120 }]} layout="vertical" />
```

### 日期范围选择器

```tsx
import { DateRangePicker, useDateRangeFilter } from './date-range-picker';

const { filtered, range, handleRangeChange } = useDateRangeFilter(
  items,
  item => item.createdAt,
);

<DateRangePicker startDate={range.start} endDate={range.end} onRangeChange={handleRangeChange} />
```

### 钉钉群机器人

```ts
import { sendDingtalkMarkdown, sendDingtalkActionCard } from './dingtalk-robot';

await sendDingtalkMarkdown('标题', '### 消息内容\n- 第一行\n- 第二行', true);

await sendDingtalkActionCard('报表已生成', '### 本周报表\n准确率：**98.5%**', '查看报表 →', 'https://your-app.com/report');
```

### shadcn/ui 组件

```tsx
// 复制 shadcn-ui/base/button.tsx 到项目 components/ui/button.tsx
import { Button } from '@/components/ui/button';
<Button variant="destructive" size="lg">删除</Button>
```

---

## 设计原则

- **零业务耦合**：纯通信/UI 层，不含特定项目的业务逻辑
- **零/低外部依赖**：尽量只用浏览器原生 API 或主流库
- **TypeScript 类型完备**：所有组件全量类型导出
- **配置可注入**：通过参数/工厂函数自定义，不写死配置
- **即拿即用**：复制文件夹到目标项目即可工作
