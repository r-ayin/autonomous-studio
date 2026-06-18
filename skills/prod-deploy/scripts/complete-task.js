#!/usr/bin/env node
/**
 * complete-task.js — Mark a deployment task as completed.
 *
 * Usage:
 *   node complete-task.js --task-id <id> --success true|false --summary "..."
 *
 * Environment variables:
 *   DEVOUT_SERVER_URL — base URL of the aone-agent-server HTTP API
 */

import { parseArgs } from 'node:util';
import { createEvent } from './lib/event-client.js';
import { getTask, updateTask } from './lib/task-client.js';

const { values } = parseArgs({
  options: {
    'task-id': { type: 'string' },
    'success': { type: 'string' },
    'summary': { type: 'string' },
  },
  strict: false,
});

const taskId = values['task-id'];
const success = values.success === 'true';
const summary = values.summary || '';

if (!taskId) { console.error('ERROR: --task-id is required'); process.exit(1); }

async function main() {
  const task = await getTask(taskId);
  if (!task) {
    console.log(JSON.stringify({ error: true, message: `Task ${taskId} not found` }));
    process.exit(1);
  }
  if (task.status === 'SUCCESS' || task.status === 'FAILED' || task.status === 'CANCELLED') {
    console.log(JSON.stringify({ error: true, message: `Task already in terminal state: ${task.status}` }));
    process.exit(1);
  }

  const finishStatus = success ? 'SUCCESS' : 'FAILED';

  await createEvent(taskId, 'finish', { summary }, null, finishStatus);

  await updateTask(taskId, {
    status: finishStatus,
    output: JSON.stringify({ summary }),
    error_message: success ? null : summary,
  });

  console.log(JSON.stringify({ success: true, task_id: taskId, status: finishStatus, summary }));
}

main().catch(err => { console.error('ERROR:', err.message); process.exit(1); });
