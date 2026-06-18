#!/usr/bin/env node
/**
 * resume-next-batch.js — Gate check before resuming next deployment batch.
 *
 * Two gates must pass before approval:
 *   1. Time gate: observation period (observe_minutes from deploy_plan) must have elapsed
 *   2. Observation gate: if observation_result exists, no HIGH-level anomalies can be active
 *
 * Usage:
 *   node resume-next-batch.js --task-id <id> --deploy-order-id <id> --batch-index <N>
 *
 * Environment variables:
 *   DEVOUT_SERVER_URL — base URL of the aone-agent-server HTTP API
 */

import { parseArgs } from 'node:util';
import { findBatchEvent, findEvent } from './lib/event-client.js';
import { deriveConclusion } from './lib/sunfire-client.js';

const { values } = parseArgs({
  options: {
    'task-id': { type: 'string' },
    'deploy-order-id': { type: 'string' },
    'batch-index': { type: 'string' },
  },
  strict: false,
});

const taskId = values['task-id'];
const batchIndex = parseInt(values['batch-index'], 10);

if (!taskId) { console.error('ERROR: --task-id is required'); process.exit(1); }

async function main() {
  const batchEvent = await findBatchEvent(taskId, batchIndex);
  if (!batchEvent) {
    console.log(JSON.stringify({ error: true, message: `Batch ${batchIndex} event not found` }));
    process.exit(1);
  }
  if (batchEvent.status !== 'SUCCESS') {
    console.log(JSON.stringify({ error: true, message: `Batch ${batchIndex} is not SUCCESS (current: ${batchEvent.status})` }));
    process.exit(1);
  }

  const planEvent = await findEvent(taskId, 'deploy_plan');
  const planPayload = planEvent ? planEvent.payload : {};
  const observeMinutes = planPayload.resolved_strategy?.observe_minutes ?? 5;

  // ── Gate 1: Time gate ─────────────────────────────────────────────
  // updated_at from server is an ISO string; convert to ms
  const successTime = new Date(batchEvent.updated_at).getTime();
  const elapsedMs = Date.now() - successTime;
  const requiredMs = observeMinutes * 60 * 1000;

  if (elapsedMs < requiredMs) {
    const remainingMin = Math.ceil((requiredMs - elapsedMs) / 60000);
    console.log(JSON.stringify({
      approved: false,
      message: `第 ${batchIndex} 批观察期未满，剩余 ${remainingMin} 分钟。继续轮询健康检查。`,
    }));
    process.exit(1);
  }

  // ── Gate 2: Observation gate ──────────────────────────────────────
  // If observation_result exists in the batch event payload, check for active anomalies
  const observationResult = batchEvent.payload?.observation_result;
  if (observationResult && !observationResult.skipped) {
    const conclusion = deriveConclusion(observationResult.checks);
    if (conclusion === 'failed') {
      // Dedup to find which HIGH-level rules are still failing
      const byRule = new Map();
      for (const item of (observationResult.checks || [])) {
        if (item.insightRule) byRule.set(item.insightRule, item);
      }
      const failedHighRules = [...byRule.values()]
        .filter(item => item.status !== 'RECOVER' && item.insightLevel === 'HIGH')
        .map(item => item.insightRule);

      console.log(JSON.stringify({
        approved: false,
        message: `第 ${batchIndex} 批观察期检测到 HIGH 级别异常未恢复: ${failedHighRules.join(', ')}。请排查后手动推进。`,
        failed_rules: failedHighRules,
        conclusion,
      }));
      process.exit(1);
    }
    // conclusion === 'warning' (LOW-level only) — log but allow proceeding
    if (conclusion === 'warning') {
      console.error(`WARNING: LOW-level anomalies detected but allowing batch progression`);
    }
  }

  console.log(JSON.stringify({
    approved: true,
    deploy_order_id: values['deploy-order-id'],
    batch_index: batchIndex,
    elapsed_min: Math.floor(elapsedMs / 60000),
    observation_conclusion: observationResult ? deriveConclusion(observationResult.checks) : 'no_data',
  }));
}

main().catch(err => { console.error('ERROR:', err.message); process.exit(1); });
