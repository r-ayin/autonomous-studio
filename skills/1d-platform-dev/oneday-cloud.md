# OneDay Cloud 数据库详解

> 替代 1d 平台内置的 `OneDayCloudEnable`（项目初始化）和 `OneDayCloudSearchDocs`（文档查询）。

## 核心原则

**必须使用 `@ali/oneday-frontend-sdk`，禁止直接使用 `@supabase/supabase-js`**

前置条件：进入「项目设置」→「数据库」，开启 OneDay Cloud。不开则 `ONEDAY_CONFIG.database_config` 为空，token 变成 `undefined`，所有请求被 PostgreSQL RLS 拦截返回 403。

## 依赖配置

```json
// ✅ 正确
{ "dependencies": { "@ali/oneday-frontend-sdk": "^1.0.1" } }

// ❌ 错误
{ "dependencies": { "@supabase/supabase-js": "^2.39.0" } }
```

## 客户端初始化（推荐：带容错和延迟重试）

```typescript
// src/onedaycloud/client.ts
import { createClient as sdkCreateClient } from "@ali/oneday-frontend-sdk";
import type { Database } from './types';

interface OneDayClientShape {
  supabase: any;
  [key: string]: any;
}

function tryCreateClient(): OneDayClientShape | null {
  try {
    const client = sdkCreateClient<Database>();
    if (client?.supabase) {
      console.log('[oneday] SDK client created successfully');
      return client as unknown as OneDayClientShape;
    }
    console.warn('[oneday] SDK createClient returned no supabase');
    return null;
  } catch (err: any) {
    console.warn('[oneday] SDK init failed:', err.message);
    return null;
  }
}

export let oneday: OneDayClientShape | null = tryCreateClient();

// SDK 可能在页面加载后才被平台注入，2 秒后重试一次
if (!oneday) {
  setTimeout(() => {
    if (!oneday) {
      oneday = tryCreateClient();
      if (oneday) console.log('[oneday] SDK delayed retry succeeded');
    }
  }, 2000);
}

export function ensureOnedayClient(): OneDayClientShape | null {
  if (!oneday) oneday = tryCreateClient();
  return oneday;
}
```

**为什么需要容错**：1D 平台通过 `window.oneday` 注入 SDK，但在发布后的 iframe 环境中，注入时机可能晚于 webpack bundle 的模块初始化。

## CRUD 操作

```typescript
import { oneday } from '@/onedaycloud/client';

// 查询
const { data, error } = await oneday.supabase
  .from('table_name')
  .select('*')
  .order('created_at', { ascending: false });

// 条件查询
const { data } = await oneday.supabase
  .from('staff')
  .select('id, name, role')
  .eq('is_active', true)
  .limit(100);

// 插入
const { data, error } = await oneday.supabase
  .from('table_name')
  .insert([{ field1: 'value1', field2: 'value2' }])
  .select();

// 更新
const { data, error } = await oneday.supabase
  .from('table_name')
  .update({ field: 'new_value' })
  .eq('id', recordId)
  .select();

// Upsert（冲突时更新）
const { data, error } = await oneday.supabase
  .from('table_name')
  .upsert({ id: 'xxx', field: 'value' }, { onConflict: 'id' })
  .select();

// 删除
const { error } = await oneday.supabase
  .from('table_name')
  .delete()
  .eq('id', recordId);
```

## Storage 文件存储

```typescript
// 上传
const { data, error } = await oneday.supabase.storage
  .from('bucket-name')
  .upload('path/to/file.png', arrayBuffer, { contentType: 'image/png', upsert: true });

// 公开 URL
const { data } = oneday.supabase.storage.from('bucket-name').getPublicUrl('path/to/file.png');

// 签名 URL（私有文件，3600秒）
const { data, error } = await oneday.supabase.storage
  .from('bucket-name').createSignedUrl('path/to/file.png', 3600);

// 删除
const { error } = await oneday.supabase.storage.from('bucket-name').remove(['path/to/file.png']);
```

## Realtime 实时订阅

```typescript
// 订阅（需先在 Migration 中 ALTER PUBLICATION supabase_realtime ADD TABLE xxx）
const channel = oneday.supabase
  .channel('my-channel')
  .on('postgres_changes', { event: '*', schema: 'public', table: 'table_name' }, (payload) => {
    console.log('变更:', payload.eventType, payload.new, payload.old);
  })
  .subscribe();

// 取消订阅
await oneday.supabase.removeChannel(channel);
```

## Migration DDL 模板

```sql
CREATE TABLE public.table_name (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id TEXT NOT NULL,           -- 关联 BUC 工号
  content TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.table_name ENABLE ROW LEVEL SECURITY;

CREATE POLICY "用户读自己数据" ON public.table_name
  FOR SELECT USING (user_id = auth.uid()::text);
CREATE POLICY "用户写自己数据" ON public.table_name
  FOR INSERT WITH CHECK (user_id = auth.uid()::text);
CREATE POLICY "用户改自己数据" ON public.table_name
  FOR UPDATE USING (user_id = auth.uid()::text);

-- 可选：开启 Realtime
ALTER PUBLICATION supabase_realtime ADD TABLE public.table_name;

-- 可选：自动更新 updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$ BEGIN NEW.updated_at = NOW(); RETURN NEW; END; $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_updated_at BEFORE UPDATE ON public.table_name
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

## 常见错误速查

| 错误现象 | 根因 | 解决 |
|---------|------|------|
| `Authorization: Bearer undefined` | 未开启 OneDay Cloud | 项目设置→数据库→开启 OneDay Cloud |
| 403 / RLS 拦截 | RLS 策略未配置或 auth.uid() 不匹配 | 检查 CREATE POLICY 语句 |
| `createClient is not a function` | 用了 @supabase/supabase-js | 替换为 @ali/oneday-frontend-sdk |
| 远端沙盒 SecurityError | 预览链接不携带项目 id | index.html head 注入 `window.ONEDAY_CONFIG = { url_id: 'xxx' }` |
| 上传 413 | 文件超过 Nginx 30MB 限制 | 压缩文件或改用 OSS |
| BUC/FK 冲突 | profiles 表和 users 表不同步 | 联系平台，钉钉群 176010005082 |
| 开发可用、发布后失效 | externals 用了 commonjs 格式 | 改为 var 前缀格式（见下方修复指南第1步） |
| 开发和发布都连不上 | externals 缺 var 前缀 / 无容错 / 无 polyfill | 按下方修复指南逐项检查 |
| `oneday.supabase` 为 undefined | SDK 注入时序问题 | client.ts 使用 tryCreateClient() + 2秒延迟重试 |
| 发布后无 `[oneday]` 日志 | TerserPlugin drop_console: true | 设 drop_console: false |

## Cloud 连接完整修复指南（按顺序检查）

**第 1 步：webpack.config.js externals**

```js
// ✅ 正确
externals: {
  '@ali/oneday-frontend-sdk': 'var (typeof oneday !== "undefined" ? oneday : { createClient: function() { return null; } })',
  '@supabase/supabase-js': '{}',
},
```

**第 2 步：src/onedaycloud/client.ts**

必须有 try-catch + 延迟重试（见上方「客户端初始化」）。直接 `export const oneday = createClient<Database>()` 无容错，SDK 未就绪即永久失败。

**第 3 步：public/index.html — oneday polyfill**

在 `<head>` 最前面（所有 webpack 脚本之前）插入：

```html
<script>
(function() {
  if (window.oneday) return;
  var noopSupabase = new Proxy(function(){}, {
    get: function(_, prop) {
      if (prop === 'then') return function(resolve) { resolve({ data: null, error: { message: 'Supabase not available', code: 'NOT_AVAILABLE' }, count: 0 }); };
      if (prop === 'data') return null;
      if (prop === 'error') return { message: 'Supabase not available', code: 'NOT_AVAILABLE' };
      if (prop === 'count') return 0;
      return noopSupabase;
    },
    apply: function() { return noopSupabase; }
  });
  window.oneday = {
    __polyfill: true,
    createClient: function() { return null; },
    supabase: noopSupabase,
    auth: noopSupabase,
    storage: noopSupabase
  };
})();
</script>
```

**第 4 步：环境差异**

| 环境 | SDK 来源 | ONEDAY_CONFIG 注入方式 |
|------|---------|---------------------|
| 开发页面 (WebContainer) | 平台注入 `window.oneday` | 平台直接设置 `window.ONEDAY_CONFIG` |
| 发布后 (iframe) | 宿主页设置 `window.oneday`，iframe 通过 externals 读取 | `parent.ONEDAY_CONFIG`（可能跨域失败）|

## 项目初始化（OneDayCloudEnable 替代）

用户说「初始化 OneDay Cloud」、「启用 Cloud」时，立即执行（无需询问）：

**步骤 1**：读取 `package.json`，确认现有依赖。

**步骤 2**：更新 `package.json`：
- 添加 `"@ali/oneday-frontend-sdk": "^1.0.1"` 到 dependencies
- 若有 `"@supabase/supabase-js"`，移到 devDependencies 或删除

**步骤 3**：创建 `src/onedaycloud/` 目录，写三个文件：

`client.ts`：见上方「客户端初始化」完整代码。

`types.ts`：
```typescript
export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];
export interface Database {
  public: {
    Tables: { /* Migration 执行后自动生成 */ };
    Views: Record<string, never>;
    Functions: Record<string, never>;
    Enums: Record<string, never>;
  };
}
```

`index.ts`：
```typescript
export { oneday } from './client';
export type { Database } from './types';
```

**步骤 4**：确保 `webpack.config.js` externals 包含正确配置（见修复指南第1步）。

**步骤 5**：输出指引：
```
✅ OneDay Cloud 本地结构已搭建完成

下一步（在 1d 平台内操作）：
1. 项目设置 → 数据库 → 开启 OneDay Cloud
2. 在 1d 平台 Agent 中调用 OneDayCloudApplyMigration 建表
3. Migration 成功后 src/onedaycloud/types.ts 自动更新
4. 业务代码中：import { oneday } from '@/onedaycloud/client'
```

## 旧版数据库升级 OneDay Cloud

1. 打开 Studio 模式和 OneDay Cloud 选项
2. 复制原项目为新项目
3. 在新项目中：先执行 `rm -rf migrations/`，然后启用 OneDay Cloud
4. 使用升级 skill：`https://1d.alibaba-inc.com/skills/upgrade-oneday-cloud`
5. 旧项目重定向：释放旧域名 → 新项目设置旧域名
