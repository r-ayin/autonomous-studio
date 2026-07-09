#!/usr/bin/env bash
# setup-e2e.sh — 小白环境一键配 Playwright E2E
# 检测项目无 @playwright/test → 自动装 + 装 chromium + 跑冒烟。零配置可用。
# 用法: bash ~/.claude/skills/autonomous-studio/scripts/setup-e2e.sh [project-dir]
set -euo pipefail
PROJ="${1:-.}"
cd "$PROJ"

echo "=== 1. 检测 @playwright/test ==="
if ! grep -q '"@playwright/test"' package.json 2>/dev/null; then
  echo "未装 @playwright/test,自动安装..."
  npm i -D @playwright/test
else
  echo "已装 @playwright/test ✓"
fi

echo "=== 2. 检测 playwright.config.ts ==="
if [[ ! -f playwright.config.ts && ! -f playwright.config.js ]]; then
  echo "无 playwright.config,生成默认配置..."
  cat > playwright.config.ts <<'EOF'
import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  timeout: 60000,
  use: { headless: true, viewport: { width: 1440, height: 900 }, screenshot: 'only-on-failure' },
  reporter: 'list',
  webServer: { command: 'node_modules/.bin/webpack serve --mode development --port 9128', url: 'http://localhost:9128', reuseExistingServer: true, timeout: 120000 },
  projects: [{ name: 'chromium', use: { channel: 'chromium' } }],
});
EOF
else
  echo "已配 playwright.config ✓"
fi

echo "=== 3. 装 chromium 无头浏览器 ==="
npx playwright install chromium 2>&1 | tail -3

echo "=== 4. 跑冒烟(若有 e2e/*.spec.ts) ==="
if ls e2e/*.spec.ts 2>/dev/null | grep -q .; then
  npx playwright test --reporter=list 2>&1 | tail -20 || echo "（冒烟失败，看上面输出）"
else
  echo "无 e2e/*.spec.ts,跳过冒烟。建议先建 e2e/v6-smoke.spec.ts"
fi

echo "=== 完成。E2E 环境就绪 ==="
echo "本地预览数据提示:若看不见数据(SDK 占位符 SB_KEY),跑: SUPABASE_KEY=真实值 npm run dev"
