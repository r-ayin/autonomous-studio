#!/usr/bin/env node
/**
 * poll-pre-check.js — Single-shot pre-check status poll.
 *
 * Drills down pipeline → stage → job → task to find the "发布准入" task,
 * then polls its check items. Claude calls this in a loop.
 *
 * Usage:
 *   node poll-pre-check.js --task-id <id> --pipeline-id <pid> --app-name <app>
 */

import { execFile } from 'child_process';
import { promisify } from 'util';
import { parseArgs } from 'node:util';
import { findEvent, updateEvent } from './lib/event-client.js';
import { extractUrlFromTips } from './lib/extract-url-from-tips.js';

const execFileAsync = promisify(execFile);

const { values } = parseArgs({
  options: {
    'task-id': { type: 'string' },
    'pipeline-id': { type: 'string' },
    'app-name': { type: 'string' },
  },
  strict: false,
});

const taskId = values['task-id'];
const pipelineId = values['pipeline-id'];
const appName = values['app-name'];

if (!taskId || !pipelineId || !appName) {
  console.error('ERROR: --task-id, --pipeline-id, and --app-name are required');
  process.exit(1);
}

const STATUS_MAP = {
  PASS: 'SUCCESS',
  PASS_WITH_LOW_RISK: 'SUCCESS',
  FAIL: 'FAILED',
  FAILED: 'FAILED',
  RUNNING: 'RUNNING',
  CHECKING: 'RUNNING',
  WAITING: 'RUNNING',
  SUCCESS: 'SUCCESS',
};

function mapCheckStatus(raw) {
  return STATUS_MAP[raw] || 'INIT';
}

function tryParseJson(text) {
  try { return JSON.parse(text.trim()); } catch { return null; }
}

async function runA1(...args) {
  const { stdout } = await execFileAsync('a1', args, {
    timeout: 30000,
    maxBuffer: 1024 * 1024,
  });
  return stdout;
}

function extractIdFromLine(line) {
  const match = line.match(/(\d{4,})/);
  return match ? match[1] : null;
}

function findMatchingRows(text, keyword) {
  return text.split('\n').filter(l => l.trim() && l.includes(keyword));
}

async function drillDownToPreCheckTask() {
  const stagesRaw = await runA1('app', 'pipeline', 'stage', 'list', '--pipeline-id', pipelineId, '--app', appName, '--format', 'json');
  const stagesData = tryParseJson(stagesRaw);

  let stageId = null;

  if (stagesData) {
    const stages = Array.isArray(stagesData) ? stagesData : (stagesData.stages || stagesData.data || []);
    const preCheckStage = stages.find(s =>
      /准入|pre.?check|构建.*准入/i.test(s.name || '')
    ) || stages.find(s =>
      ['RUNNING', 'SUCCESS', 'FAILED'].includes((s.status || '').toUpperCase()) &&
      !/构建|build|compile/i.test(s.name || '')
    );
    if (preCheckStage) {
      stageId = preCheckStage.stageId || preCheckStage.stage_id || preCheckStage.id;
    }
  }

  if (!stageId) {
    const rows = findMatchingRows(stagesRaw, '准入');
    if (rows.length > 0) stageId = extractIdFromLine(rows[0]);
  }

  if (!stageId) {
    throw new Error(`找不到准入 stage (raw: ${stagesRaw.trim().substring(0, 200)})`);
  }

  const jobsRaw = await runA1('app', 'pipeline', 'stage', 'job', 'list', '--stage-id', String(stageId), '--app', appName, '--format', 'json');
  const jobsData = tryParseJson(jobsRaw);

  const allJobIds = [];

  if (jobsData) {
    const jobs = Array.isArray(jobsData) ? jobsData : (jobsData.jobs || jobsData.data || []);
    for (const job of jobs) {
      const id = job.jobId || job.jobInstId || job.job_inst_id || job.id;
      if (id) allJobIds.push(String(id));
    }
  }

  if (allJobIds.length === 0) {
    const lines = jobsRaw.split('\n').filter(l => l.trim() && !/^[-=\s]*$/.test(l));
    for (const line of lines.slice(1)) {
      const id = extractIdFromLine(line);
      if (id) allJobIds.push(id);
    }
  }

  if (allJobIds.length === 0) {
    throw new Error(`准入 stage 无 job (raw: ${jobsRaw.trim().substring(0, 200)})`);
  }

  let preCheckTaskId = null;

  for (const jobId of allJobIds) {
    const tasksRaw = await runA1('app', 'pipeline', 'stage', 'job', 'task', 'list', '--job-inst-id', jobId, '--app', appName, '--format', 'json');
    const tasksData = tryParseJson(tasksRaw);

    if (tasksData) {
      const tasks = Array.isArray(tasksData) ? tasksData : (tasksData.tasks || tasksData.data || []);
      const preCheckTask = tasks.find(t => /发布准入/i.test(t.name || t.taskName || ''));
      if (preCheckTask) {
        preCheckTaskId = preCheckTask.taskId || preCheckTask.task_id || preCheckTask.id;
        break;
      }
    }

    if (!preCheckTaskId) {
      const rows = findMatchingRows(tasksRaw, '发布准入');
      if (rows.length > 0) {
        preCheckTaskId = extractIdFromLine(rows[0]);
        if (preCheckTaskId) break;
      }
    }
  }

  if (!preCheckTaskId) {
    throw new Error(`找不到"发布准入"task (searched ${allJobIds.length} jobs)`);
  }

  return preCheckTaskId;
}

async function main() {
  const event = await findEvent(taskId, 'pre_check');
  if (!event) {
    console.log(JSON.stringify({ error: true, message: 'No pre_check event found. Create it via report-event.js first.' }));
    process.exit(1);
  }

  const existingPayload = event.payload || {};
  let cachedTaskId = existingPayload.task_id || null;

  if (!cachedTaskId) {
    cachedTaskId = await drillDownToPreCheckTask();
    // M-002 fix: persist task_id cache immediately after drill-down so that a
    // later updateEvent failure (network blip) does not force a redundant
    // re-drill on the next poll cycle. Payload-only update (status=null keeps
    // existing event status per event-client terminal-state semantics).
    try {
      await updateEvent(event, null, { task_id: String(cachedTaskId) });
    } catch (cacheErr) {
      // Non-fatal: worst case we re-drill next cycle. Log for observability.
      console.error(`WARN: failed to persist pre-check task_id cache: ${cacheErr.message}`);
    }
  }

  const taskStatusRaw = await runA1('app', 'pipeline', 'stage', 'job', 'task', 'status', '--task-id', String(cachedTaskId), '--app', appName, '--format', 'json');
  const taskStatusData = tryParseJson(taskStatusRaw);

  let checkItems = [];
  let taskStatus = 'RUNNING';

  if (taskStatusData) {
    const checkInsts = taskStatusData.componentData?.checkInsts || taskStatusData.checkInsts || taskStatusData.check_insts || [];
    taskStatus = taskStatusData.status || taskStatusData.taskStatus || 'RUNNING';

    checkItems = checkInsts.map(ci => {
      const detailUrl = ci.detailUrl || extractUrlFromTips(ci.tips) || null;
      return {
        name: ci.name,
        status: mapCheckStatus(ci.status),
        ...(ci.tips ? { tips: ci.tips } : {}),
        ...(detailUrl ? { detailUrl } : {}),
      };
    });
  } else {
    const upper = taskStatusRaw.toUpperCase();
    if (upper.includes('FAILED') || upper.includes('FAIL')) {
      taskStatus = 'FAILED';
    } else if (upper.includes('SUCCESS') || upper.includes('PASS')) {
      taskStatus = 'SUCCESS';
    } else if (upper.includes('CANCELLED') || upper.includes('CANCELED')) {
      taskStatus = 'CANCELLED';
    }
  }

  const passed = checkItems.filter(c => c.status === 'SUCCESS').length;
  const failed = checkItems.filter(c => c.status === 'FAILED').length;
  const running = checkItems.filter(c => c.status === 'RUNNING').length;
  const init = checkItems.filter(c => c.status === 'INIT').length;
  const parts = [];
  if (passed > 0) parts.push(`${passed} 通过`);
  if (failed > 0) parts.push(`${failed} 失败`);
  if (running > 0) parts.push(`${running} 运行中`);
  if (init > 0) parts.push(`${init} 等待中`);
  const summary = parts.join(', ') || '无检查项';

  const payload = {
    pipeline_id: pipelineId,
    task_id: String(cachedTaskId),
    raw_task_status: taskStatusRaw.trim(),
    ...(checkItems.length > 0 ? { check_items: checkItems } : {}),
    summary,
    poll_time: Date.now(),
  };

  const taskStatusTerminal = ['SUCCESS', 'FAILED', 'PASS', 'FAIL', 'CANCELLED'].includes(
    (taskStatus || '').toUpperCase()
  );

  // Check items still pending → not truly terminal regardless of taskStatus
  const hasUnfinished = checkItems.length > 0 && checkItems.some(
    c => c.status === 'INIT' || c.status === 'RUNNING'
  );
  const isTerminal = taskStatusTerminal && !hasUnfinished;

  // Keep event status as RUNNING — agent closes it via report-event.js pre_check --status
  await updateEvent(event, null, payload);

  if (isTerminal) {
    const resultStatus = ['SUCCESS', 'PASS'].includes(taskStatus.toUpperCase()) ? 'completed' : 'failed';
    console.log(JSON.stringify({ done: true, status: resultStatus, payload }));
  } else {
    console.log(JSON.stringify({ done: false, status: 'RUNNING', payload }));
  }
}

main().catch(err => {
  console.log(JSON.stringify({ error: true, message: err.message }));
  process.exit(1);
});
