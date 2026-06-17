/**
 * confidence-calibrator.js — 信心阈值自适应调整器
 *
 * 基于历史决策成功率自动校准各阶段的信心阈值。
 * 每月运行一次校准，生成校准报告。
 *
 * 输入: autonomous-studio/claude/decisions/decision-log.jsonl (历史决策记录)
 * 输出: 更新 autonomous-studio/claude/decisions/calibration.json 中的阈值配置
 *       生成 autonomous-studio/claude/decisions/monthly-reports/month-{YYYY-MM}.md
 *
 * 使用方式:
 *   node confidence-calibrator.js [--dry-run]
 *
 * 环境变量:
 *   CLAUDE_PROJECT_DIR — 项目根目录（默认当前目录）
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { join } from 'path';

// ─── 默认配置 ─────────────────────────────────────────────────────────────

/** 各阶段默认信心阈值 */
const DEFAULT_THRESHOLDS = {
  project_onboarding: 60,    // ⓪ 项目接入
  requirement_exploration: 65, // ① 需求探索
  prd: 70,                   // ② PRD
  tech_plan: 70,             // ③ 技术方案
  code_development: 75,      // ④ 代码开发
  verification: 80,          // ⑤ 验证
  code_review: 75,           // ⑥ 评审
  deployment: 80,            // ⑦ 部署
};

/** 阶段名称映射（中文） */
const STAGE_NAMES = {
  project_onboarding: '项目接入',
  requirement_exploration: '需求探索',
  prd: 'PRD',
  tech_plan: '技术方案',
  code_development: '代码开发',
  verification: '验证',
  code_review: '评审',
  deployment: '部署',
};

/** 校准参数 */
const CALIBRATION_CONFIG = {
  min_sample_size: 5,        // 最小样本数，低于此值不调整阈值
  adjustment_step: 5,        // 每次调整步长（分）
  max_threshold: 95,         // 阈值上限
  min_threshold: 50,         // 阈值下限
  high_success_rate: 0.85,   // 高成功率阈值（可调低信心）
  low_success_rate: 0.65,    // 低成功率阈值（需调高信心）
  overconfidence_threshold: 0.80, // 过度自信检测阈值
};

// ─── 工具函数 ─────────────────────────────────────────────────────────────

/**
 * 读取 JSONL 文件，返回解析后的记录数组
 */
function readDecisionLog(logPath) {
  if (!existsSync(logPath)) {
    return [];
  }
  const content = readFileSync(logPath, 'utf-8').trim();
  if (!content) return [];
  return content
    .split('\n')
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

/**
 * 读取 calibration.json
 */
function readCalibration(calibrationPath) {
  if (!existsSync(calibrationPath)) {
    return null;
  }
  try {
    return JSON.parse(readFileSync(calibrationPath, 'utf-8'));
  } catch {
    return null;
  }
}

/**
 * 写入 calibration.json
 */
function writeCalibration(calibrationPath, data) {
  writeFileSync(calibrationPath, JSON.stringify(data, null, 2), 'utf-8');
}

/**
 * 确保目录存在
 */
function ensureDir(dirPath) {
  if (!existsSync(dirPath)) {
    mkdirSync(dirPath, { recursive: true });
  }
}

// ─── 核心分析逻辑 ─────────────────────────────────────────────────────────

/**
 * 按阶段统计成功率
 */
function calculateStageStats(records) {
  const stats = {};

  for (const record of records) {
    const stage = record.stage;
    if (!stage) continue;

    if (!stats[stage]) {
      stats[stage] = { total: 0, success: 0, failure: 0, overconfidence: 0 };
    }

    stats[stage].total += 1;

    // 判断成功/失败
    const result = record.result;
    if (result === 'success') {
      stats[stage].success += 1;
    } else if (result === 'failure' || result === 'user_rejected' || result === 'timeout') {
      stats[stage].failure += 1;
    } else if (result === 'partial_success') {
      stats[stage].success += 0.5;
      stats[stage].failure += 0.5;
    }
    // aborted 不计入统计

    // 过度自信检测
    if (record.confidence_score >= CALIBRATION_CONFIG.overconfidence_threshold * 100 &&
        ['failure', 'user_rejected'].includes(result)) {
      stats[stage].overconfidence += 1;
    }
  }

  // 计算成功率
  for (const stage of Object.keys(stats)) {
    const s = stats[stage];
    s.success_rate = s.total > 0 ? s.success / s.total : 0;
  }

  return stats;
}

/**
 * 计算各阶段建议阈值
 */
function calculateThresholdAdjustments(stats, currentThresholds) {
  const adjustments = {};

  for (const [stage, s] of Object.entries(stats)) {
    if (s.total < CALIBRATION_CONFIG.min_sample_size) {
      // 样本不足，不调整
      adjustments[stage] = {
        current: currentThresholds[stage] || DEFAULT_THRESHOLDS[stage],
        suggested: currentThresholds[stage] || DEFAULT_THRESHOLDS[stage],
        change: 0,
        reason: `样本不足（${s.total}/${CALIBRATION_CONFIG.min_sample_size}），暂不调整`,
      };
      continue;
    }

    const current = currentThresholds[stage] || DEFAULT_THRESHOLDS[stage];
    let suggested = current;
    let reason = '';

    if (s.success_rate >= CALIBRATION_CONFIG.high_success_rate) {
      // 成功率高，可适当降低阈值（说明当前阈值过高）
      suggested = Math.max(CALIBRATION_CONFIG.min_threshold, current - CALIBRATION_CONFIG.adjustment_step);
      reason = `成功率 ${((s.success_rate) * 100).toFixed(1)}% >= ${CALIBRATION_CONFIG.high_success_rate * 100}%，调低阈值`;
    } else if (s.success_rate < CALIBRATION_CONFIG.low_success_rate) {
      // 成功率低，需提高阈值（说明当前阈值过低）
      suggested = Math.min(CALIBRATION_CONFIG.max_threshold, current + CALIBRATION_CONFIG.adjustment_step);
      reason = `成功率 ${((s.success_rate) * 100).toFixed(1)}% < ${CALIBRATION_CONFIG.low_success_rate * 100}%，调高阈值`;
    } else {
      reason = `成功率 ${((s.success_rate) * 100).toFixed(1)}% 在正常范围内，维持当前阈值`;
    }

    // 过度自信预警
    if (s.overconfidence >= 2) {
      suggested = Math.min(CALIBRATION_CONFIG.max_threshold, suggested + CALIBRATION_CONFIG.adjustment_step);
      reason += `；过度自信预警（${s.overconfidence} 次）`;
    }

    adjustments[stage] = {
      current,
      suggested,
      change: suggested - current,
      reason,
      success_rate: s.success_rate,
      total_decisions: s.total,
      overconfidence_count: s.overconfidence,
    };
  }

  return adjustments;
}

// ─── 报告生成 ─────────────────────────────────────────────────────────────

/**
 * 生成月度校准报告
 */
function generateMonthlyReport(adjustments, stats, month) {
  const lines = [];
  const monthStr = month || new Date().toISOString().slice(0, 7); // YYYY-MM

  lines.push(`# 信心阈值月度校准报告 — ${monthStr}`);
  lines.push('');
  lines.push(`> 生成时间: ${new Date().toISOString()}`);
  lines.push('');

  lines.push('## 一、总体概况');
  lines.push('');

  let totalDecisions = 0;
  let totalSuccess = 0;
  for (const s of Object.values(stats)) {
    totalDecisions += s.total;
    totalSuccess += s.success;
  }
  const overallRate = totalDecisions > 0 ? (totalSuccess / totalDecisions * 100).toFixed(1) : 'N/A';

  lines.push(`- 总决策数: ${totalDecisions}`);
  lines.push(`- 总体成功率: ${overallRate}%`);
  lines.push(`- 校准阶段数: ${Object.keys(adjustments).length}`);
  lines.push('');

  lines.push('## 二、各阶段校准详情');
  lines.push('');
  lines.push('| 阶段 | 当前阈值 | 建议阈值 | 变化 | 成功率 | 决策数 | 原因 |');
  lines.push('|------|---------|---------|------|--------|--------|------|');

  for (const [stage, adj] of Object.entries(adjustments)) {
    const name = STAGE_NAMES[stage] || stage;
    const changeStr = adj.change > 0 ? `+${adj.change}` : `${adj.change}`;
    const rateStr = adj.success_rate != null ? `${(adj.success_rate * 100).toFixed(1)}%` : 'N/A';
    lines.push(`| ${name} | ${adj.current} | ${adj.suggested} | ${changeStr} | ${rateStr} | ${adj.total_decisions || 0} | ${adj.reason} |`);
  }

  lines.push('');
  lines.push('## 三、校准建议');
  lines.push('');

  const hasChanges = Object.values(adjustments).some((a) => a.change !== 0);
  if (hasChanges) {
    lines.push('✅ 检测到需要调整的阈值，建议执行校准。');
    lines.push('');
    lines.push('### 调整汇总');
    lines.push('');
    for (const [stage, adj] of Object.entries(adjustments)) {
      if (adj.change !== 0) {
        const name = STAGE_NAMES[stage] || stage;
        lines.push(`- **${name}**: ${adj.current} → ${adj.suggested} (${adj.change > 0 ? '+' : ''}${adj.change})`);
      }
    }
  } else {
    lines.push('ℹ️ 所有阶段阈值均在合理范围内，无需调整。');
  }

  lines.push('');
  lines.push('## 四、过度自信预警');
  lines.push('');

  const overconfidentStages = Object.entries(stats).filter(([, s]) => s.overconfidence > 0);
  if (overconfidentStages.length > 0) {
    lines.push('⚠️ 以下阶段存在过度自信情况：');
    lines.push('');
    for (const [stage, s] of overconfidentStages) {
      const name = STAGE_NAMES[stage] || stage;
      lines.push(`- **${name}**: ${s.overconfidence} 次（信心 ≥80 但决策失败）`);
    }
  } else {
    lines.push('✅ 未检测到过度自信情况。');
  }

  lines.push('');
  lines.push('---');
  lines.push(`*本报告由 confidence-calibrator.js 自动生成*`);
  lines.push('');

  return lines.join('\n');
}

// ─── 主流程 ─────────────────────────────────────────────────────────────

/**
 * 执行校准
 */
export async function runCalibration(options = {}) {
  const { dryRun = false } = options;

  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const decisionsDir = join(projectDir, '.claude', 'decisions');
  const logPath = join(decisionsDir, 'decision-log.jsonl');
  const calibrationPath = join(decisionsDir, 'calibration.json');

  // 1. 读取历史决策记录
  const records = readDecisionLog(logPath);
  if (records.length === 0) {
    console.log('[CALIBRATOR] 无历史决策记录，跳过校准');
    return { status: 'skipped', reason: 'no_records' };
  }
  console.log(`[CALIBRATOR] 读取到 ${records.length} 条历史决策记录`);

  // 2. 按阶段统计
  const stats = calculateStageStats(records);

  // 3. 读取当前阈值
  const calibration = readCalibration(calibrationPath);
  const currentThresholds = calibration?.confidence_thresholds || { ...DEFAULT_THRESHOLDS };

  // 4. 计算建议调整
  const adjustments = calculateThresholdAdjustments(stats, currentThresholds);

  // 5. 生成月度报告
  const month = new Date().toISOString().slice(0, 7);
  const reportContent = generateMonthlyReport(adjustments, stats, month);
  const reportsDir = join(decisionsDir, 'monthly-reports');
  ensureDir(reportsDir);
  const reportPath = join(reportsDir, `month-${month}.md`);

  if (!dryRun) {
    writeFileSync(reportPath, reportContent, 'utf-8');
    console.log(`[CALIBRATOR] 月度报告已写入: ${reportPath}`);
  }

  // 6. 更新 calibration.json（如果有调整）
  const hasChanges = Object.values(adjustments).some((a) => a.change !== 0);
  if (hasChanges && !dryRun) {
    const newThresholds = {};
    for (const [stage, adj] of Object.entries(adjustments)) {
      newThresholds[stage] = adj.suggested;
    }

    if (calibration) {
      calibration.confidence_thresholds = newThresholds;
      calibration.last_calibration = new Date().toISOString();
      writeCalibration(calibrationPath, calibration);
    } else {
      const newCalibration = {
        confidence_thresholds: newThresholds,
        last_calibration: new Date().toISOString(),
        calibration_history: [{
          month,
          adjustments,
          timestamp: new Date().toISOString(),
        }],
      };
      writeCalibration(calibrationPath, newCalibration);
    }
    console.log('[CALIBRATOR] calibration.json 已更新');
  } else if (hasChanges && dryRun) {
    console.log('[CALIBRATOR] [DRY RUN] 检测到需要调整，但未执行写入');
    console.log(JSON.stringify(adjustments, null, 2));
  } else {
    console.log('[CALIBRATOR] 无需调整阈值');
  }

  return {
    status: hasChanges ? 'adjusted' : 'no_change',
    adjustments,
    stats,
    report_path: reportPath,
    total_records: records.length,
  };
}

// ─── CLI 入口 ─────────────────────────────────────────────────────────────

if (process.argv[1]?.endsWith('confidence-calibrator.js')) {
  const dryRun = process.argv.includes('--dry-run');

  runCalibration({ dryRun })
    .then((result) => {
      console.log(`[CALIBRATOR] 校准完成: ${JSON.stringify(result, null, 2)}`);
      process.exit(0);
    })
    .catch((err) => {
      console.error(`[CALIBRATOR] 校准失败: ${err.message}`);
      process.exit(1);
    });
}
