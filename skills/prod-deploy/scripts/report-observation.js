#!/usr/bin/env node
/**
 * report-observation.js — Query Sunfire and store observation results in batch event.
 *
 * Called during each observation tick (every 60s) to query Sunfire for deploy
 * insight data and write the results into the deploy_batch event's payload
 * as `observation_result`.
 *
 * Usage:
 *   node report-observation.js --task-id <id> --batch-index <N> \
 *     --app-name <app> [--start-time <epoch_ms>] [--analysis <text>]
 *
 * If --start-time is omitted, uses the batch event's payload.success_at timestamp
 * (stamped when the batch became SUCCESS) as the observation start time, falling
 * back to updated_at for batches stamped before the success_at fix (PD-TIME-01).
 *
 * Output (JSON):
 *   { observation_result: {...}, conclusion: "passed"|"warning"|"failed", skipped?: boolean }
 *
 * Environment variables:
 *   DEVOUT_SERVER_URL    — aone-agent-server base URL
 *   SUNFIRE_ACCESS_ID    — Sunfire OpenAPI accessKeyId
 *   SUNFIRE_SECRET_KEY   — Sunfire OpenAPI secretKey
 */

import { parseArgs } from 'node:util';
import { findBatchEvent, updateEvent } from './lib/event-client.js';
import { querySunfireInsights, buildObservationResult, deriveConclusion } from './lib/sunfire-client.js';

const { values } = parseArgs({
  options: {
    'task-id':          { type: 'string' },
    'batch-index':      { type: 'string' },
    'app-name':         { type: 'string' },
    'start-time':       { type: 'string' },
    'analysis':         { type: 'string' },
  },
  strict: false,
});

const taskId = values['task-id'];
const batchIndex = parseInt(values['batch-index'], 10);
const appName = values['app-name'];

if (!taskId)   { console.error('ERROR: --task-id is required');   process.exit(1); }
if (!appName)  { console.error('ERROR: --app-name is required');  process.exit(1); }
if (isNaN(batchIndex)) { console.error('ERROR: --batch-index is required'); process.exit(1); }

async function main() {
  // 1. Find the existing batch event
  const batchEvent = await findBatchEvent(taskId, batchIndex);
  if (!batchEvent) {
    console.log(JSON.stringify({ error: true, message: `Batch ${batchIndex} event not found` }));
    process.exit(1);
  }

  // 2. Determine observation time window
  // PD-TIME-01: prefer payload.success_at (stamped when the batch hit SUCCESS) over
  // updated_at, which this script bumps every tick via updateEvent. Fall back to updated_at
  // for in-flight batches stamped before this fix.
  const successAt = batchEvent.payload?.success_at;
  const startTime = values['start-time']
    ? parseInt(values['start-time'], 10)
    : (successAt != null ? new Date(successAt).getTime() : new Date(batchEvent.updated_at).getTime());
  const endTime = Date.now();

  // 3. Query Sunfire — querySunfireInsights handles missing credentials gracefully
  const result = await querySunfireInsights({ appName, startTime, endTime });

  if (result.skipped) {
    // Credentials missing or API error — store skipped marker, don't block deployment
    const observationResult = {
      skipped: true,
      checked_at: new Date().toISOString(),
      reason: result.reason,
    };
    await updateEvent(batchEvent, null, { observation_result: observationResult });
    console.log(JSON.stringify({
      observation_result: observationResult,
      conclusion: 'passed',
      skipped: true,
    }));
    return;
  }

  // 4. Build observation_result in the format backend expects:
  //    observation_result.checks[] = raw Sunfire items with ALL fields
  //    observation_result.checked_at = ISO timestamp
  //    observation_result.analysis = optional LLM text
  const observationResult = buildObservationResult(result.items, values.analysis);

  // 5. Derive conclusion
  const conclusion = deriveConclusion(observationResult.checks);

  // 6. Write observation_result into the batch event payload
  await updateEvent(batchEvent, null, { observation_result: observationResult });

  // 7. Output result
  console.log(JSON.stringify({
    observation_result: observationResult,
    conclusion,
    items_count: result.items.length,
    time_window: { start: startTime, end: endTime },
  }));
}

main().catch(err => { console.error('ERROR:', err.message); process.exit(1); });
