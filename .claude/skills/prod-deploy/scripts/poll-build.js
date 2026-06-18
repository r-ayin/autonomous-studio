#!/usr/bin/env node
/**
 * poll-build.js — Single-shot build status poll.
 *
 * Calls `a1` CLI to check pipeline build status, writes result to event store,
 * returns current status as JSON. Claude calls this in a loop.
 *
 * Usage:
 *   node poll-build.js --task-id <id> --pipeline-id <pid> --app-name <app>
 */

import { execFile } from 'child_process';
import { promisify } from 'util';
import { parseArgs } from 'node:util';
import { findEvent, updateEvent } from './lib/event-client.js';

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

async function main() {
  const event = await findEvent(taskId, 'build');
  if (!event) {
    console.log(JSON.stringify({ error: true, message: 'No build event found. Create it via report-event.js first.' }));
    process.exit(1);
  }

  const statusRaw = await runA1('app', 'pipeline', 'status', '--pipeline-id', pipelineId, '--app', appName);
  const stagesRaw = await runA1('app', 'pipeline', 'stage', 'list', '--pipeline-id', pipelineId, '--app', appName);

  const statusData = tryParseJson(statusRaw);
  const stagesData = tryParseJson(stagesRaw);

  let pipelineStatus = 'UNKNOWN';
  let stages = [];
  let buildStageStatus = null;

  if (statusData) {
    pipelineStatus = statusData.status || statusData.pipelineStatus || 'UNKNOWN';
  }

  if (stagesData) {
    stages = Array.isArray(stagesData) ? stagesData : (stagesData.stages || stagesData.data || []);
    const buildStage = stages.find(s => /构建|build|compile/i.test(s.name || ''));
    buildStageStatus = buildStage?.status || pipelineStatus;
  }

  if (!buildStageStatus || buildStageStatus === 'UNKNOWN') {
    const combined = (statusRaw + '\n' + stagesRaw).toUpperCase();
    if (combined.includes('FAILED') || combined.includes('FAIL')) {
      buildStageStatus = 'FAILED';
    } else if (combined.includes('CANCELLED') || combined.includes('CANCELED')) {
      buildStageStatus = 'CANCELLED';
    } else if (combined.includes('SUCCESS')) {
      buildStageStatus = 'SUCCESS';
    } else {
      buildStageStatus = 'RUNNING';
    }
  }

  const payload = {
    pipeline_id: pipelineId,
    pipeline_status: pipelineStatus,
    raw_pipeline_status: statusRaw.trim(),
    raw_stage_list: stagesRaw.trim(),
    ...(stages.length > 0 ? { stages: stages.map(s => ({ name: s.name, status: s.status })) } : {}),
    poll_time: Date.now(),
  };

  const isTerminal = ['SUCCESS', 'FAILED', 'CANCELLED'].includes(buildStageStatus.toUpperCase());

  if (isTerminal) {
    const finalStatus = buildStageStatus.toUpperCase() === 'SUCCESS' ? 'SUCCESS' : 'FAILED';
    if (finalStatus === 'FAILED') {
      payload.error_message = `构建失败: ${buildStageStatus}`;
    }
    await updateEvent(event, finalStatus, payload);
    console.log(JSON.stringify({ done: true, status: finalStatus, payload }));
  } else {
    await updateEvent(event, null, payload);
    console.log(JSON.stringify({ done: false, status: 'RUNNING', payload }));
  }
}

main().catch(err => {
  console.log(JSON.stringify({ error: true, message: err.message }));
  process.exit(1);
});
