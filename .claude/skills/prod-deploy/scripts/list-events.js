#!/usr/bin/env node
/**
 * list-events.js — List deploy events for a task (checkpoint recovery).
 *
 * Usage:
 *   node list-events.js --task-id <id> [--status STATUS]
 *
 * Environment variables:
 *   DEVOUT_SERVER_URL — base URL of the aone-agent-server HTTP API
 */

import { parseArgs } from 'node:util';
import { queryEvents } from './lib/event-client.js';

const { values } = parseArgs({
  options: {
    'task-id': { type: 'string' },
    'status': { type: 'string' },
  },
  strict: false,
});

const taskId = values['task-id'];
if (!taskId) { console.error('ERROR: --task-id is required'); process.exit(1); }

async function main() {
  const items = await queryEvents(taskId, { status: values.status });
  console.log(JSON.stringify(items, null, 2));
}

main().catch(err => { console.error('ERROR:', err.message); process.exit(1); });
