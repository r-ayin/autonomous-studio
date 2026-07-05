#!/usr/bin/env node
/**
 * report-event.js — Deploy event reporting script (replaces MCP tools).
 *
 * Usage:
 *   node report-event.js --task-id <id> <event_type> [--field value ...]
 *
 * Event types: pipeline_check, build, pre_check, deploy_plan, deploy_batch
 *
 * Environment variables:
 *   DEVOUT_SERVER_URL — base URL of the aone-agent-server HTTP API
 */

import { findEvent, findBatchEvent, createEvent, updateEvent } from './lib/event-client.js';
import { parseArgs } from 'node:util';

const TERMINAL_STATUSES = new Set(['SUCCESS', 'FAILED']);

// ─── Event Handlers ─────────────────────────────────────────────────────────

async function handlePipelineCheck(taskId, args) {
  const { values } = parseArgs({
    args,
    options: {
      'pipeline-id': { type: 'string' },
      'app-name': { type: 'string' },
      'status': { type: 'string' },
      'pipeline-status': { type: 'string' },
      'error-message': { type: 'string' },
    },
    strict: false,
  });

  const existing = await findEvent(taskId, 'pipeline_check');

  if (!existing) {
    const payload = { pipeline_id: values['pipeline-id'], app_name: values['app-name'] };
    if (values['pipeline-status']) payload.pipeline_status = values['pipeline-status'];
    if (values['error-message']) payload.error_message = values['error-message'];
    const event = await createEvent(taskId, 'pipeline_check', payload);
    if (values.status) {
      const fields = {};
      if (values['pipeline-status']) fields.pipeline_status = values['pipeline-status'];
      if (values['error-message']) fields.error_message = values['error-message'];
      return updateEvent(event, values.status, Object.keys(fields).length > 0 ? fields : null);
    }
    return event;
  }

  if (TERMINAL_STATUSES.has(existing.status)) {
    return { ...existing, _already_terminal: true };
  }

  if (values.status) {
    const fields = {};
    if (values['pipeline-status']) fields.pipeline_status = values['pipeline-status'];
    if (values['error-message']) fields.error_message = values['error-message'];
    return updateEvent(existing, values.status, Object.keys(fields).length > 0 ? fields : null);
  }

  return existing;
}

async function handleBuild(taskId, args) {
  const { values } = parseArgs({
    args,
    options: {
      'pipeline-id': { type: 'string' },
      'cr-id': { type: 'string' },
      'status': { type: 'string' },
      'error-message': { type: 'string' },
    },
    strict: false,
  });

  const existing = await findEvent(taskId, 'build');

  if (!existing) {
    const payload = { pipeline_id: values['pipeline-id'], cr_id: values['cr-id'] };
    const event = await createEvent(taskId, 'build', payload);
    if (values.status) {
      const fields = values['error-message'] ? { error_message: values['error-message'] } : null;
      return updateEvent(event, values.status, fields);
    }
    return event;
  }

  if (TERMINAL_STATUSES.has(existing.status)) {
    return { ...existing, _already_terminal: true };
  }

  if (values.status) {
    const fields = {};
    if (values['error-message']) fields.error_message = values['error-message'];
    return updateEvent(existing, values.status, Object.keys(fields).length > 0 ? fields : null);
  }

  return existing;
}

async function handlePreCheck(taskId, args) {
  const { values } = parseArgs({
    args,
    options: {
      'pipeline-id': { type: 'string' },
      'task-id': { type: 'string' },
      'check-items': { type: 'string' },
      'status': { type: 'string' },
      'error-message': { type: 'string' },
    },
    strict: false,
  });

  const checkItems = values['check-items'] ? JSON.parse(values['check-items']) : null;
  const existing = await findEvent(taskId, 'pre_check');

  if (!existing) {
    const payload = {};
    if (values['pipeline-id']) payload.pipeline_id = values['pipeline-id'];
    if (values['task-id']) payload.task_id = values['task-id'];
    if (checkItems) payload.check_items = checkItems;
    if (values['error-message']) payload.error_message = values['error-message'];
    const event = await createEvent(taskId, 'pre_check', payload);
    if (values.status) {
      return updateEvent(event, values.status, null);
    }
    return event;
  }

  if (TERMINAL_STATUSES.has(existing.status)) {
    return { ...existing, _already_terminal: true };
  }

  const fields = {};
  if (values['task-id']) fields.task_id = values['task-id'];
  if (checkItems) {
    const existingItems = existing.payload.check_items || [];
    const merged = [...existingItems];
    for (const newItem of checkItems) {
      const idx = merged.findIndex(e => e.name === newItem.name);
      if (idx >= 0) {
        merged[idx] = newItem;
      } else {
        merged.push(newItem);
      }
    }
    fields.check_items = merged;
  }
  if (values['error-message']) fields.error_message = values['error-message'];

  return updateEvent(existing, values.status || null, Object.keys(fields).length > 0 ? fields : null);
}

async function handleDeployPlan(taskId, args) {
  const { values } = parseArgs({
    args,
    options: {
      'deploy-order-id': { type: 'string' },
      'resolved-strategy': { type: 'string' },
      'status': { type: 'string' },
    },
    strict: false,
  });

  const resolvedStrategy = values['resolved-strategy'] ? JSON.parse(values['resolved-strategy']) : {};
  const existing = await findEvent(taskId, 'deploy_plan');

  if (existing) {
    return updateEvent(existing, values.status || null, {
      deploy_order_id: values['deploy-order-id'],
      resolved_strategy: resolvedStrategy,
    });
  }

  const payload = { deploy_order_id: values['deploy-order-id'], resolved_strategy: resolvedStrategy };
  return createEvent(taskId, 'deploy_plan', payload, values['deploy-order-id'], values.status);
}

async function handleDeployBatch(taskId, args) {
  const { values } = parseArgs({
    args,
    options: {
      'deploy-order-id': { type: 'string' },
      'batch-index': { type: 'string' },
      'batch-total': { type: 'string' },
      'group': { type: 'string' },
      'instances': { type: 'string' },
      'payload': { type: 'string' },
      'status': { type: 'string' },
      'error-message': { type: 'string' },
    },
    strict: false,
  });

  const batchIndex = parseInt(values['batch-index'], 10);
  const batchTotal = values['batch-total'] ? parseInt(values['batch-total'], 10) : null;
  const instances = values['instances'] ? parseInt(values['instances'], 10) : null;
  const extraPayload = values.payload ? JSON.parse(values.payload) : null;

  const existing = await findBatchEvent(taskId, batchIndex);

  if (!existing) {
    const eventPayload = { deploy_order_id: values['deploy-order-id'], batch_index: batchIndex };
    if (batchTotal != null) eventPayload.batch_total = batchTotal;
    if (values.group) eventPayload.group = values.group;
    if (instances != null) eventPayload.instances = instances;
    if (extraPayload) Object.assign(eventPayload, extraPayload);
    const event = await createEvent(taskId, 'deploy_batch', eventPayload, values['deploy-order-id']);
    if (values.status) {
      const fields = {};
      if (values['error-message']) fields.error_message = values['error-message'];
      // PD-TIME-01: stamp success_at when the batch transitions to SUCCESS so the
      // observation time-gate measures from real success, not updated_at (which
      // report-observation bumps every tick). Readers fall back to updated_at for in-flight batches.
      if (values.status === 'SUCCESS') fields.success_at = Date.now();
      return updateEvent(event, values.status, Object.keys(fields).length > 0 ? fields : null);
    }
    return event;
  }

  if (TERMINAL_STATUSES.has(existing.status)) {
    return { ...existing, _already_terminal: true };
  }

  if (values.status) {
    const fields = {};
    if (values['error-message']) fields.error_message = values['error-message'];
    // PD-TIME-01: stamp success_at on SUCCESS transition (existing.status is non-terminal here
    // per the TERMINAL_STATUSES guard above, so this is a fresh success). extraPayload may
    // override if the caller supplies an explicit success_at.
    if (values.status === 'SUCCESS') fields.success_at = Date.now();
    if (extraPayload) Object.assign(fields, extraPayload);
    return updateEvent(existing, values.status, Object.keys(fields).length > 0 ? fields : null);
  }

  if (extraPayload) {
    return updateEvent(existing, null, extraPayload);
  }

  return existing;
}

// ─── Main ───────────────────────────────────────────────────────────────────

// Split argv at the event type positional so sub-command --task-id
// (e.g. pre_check's --task-id) doesn't overwrite the top-level SRE task id.
const argv = process.argv.slice(2);
let eventTypeIdx = -1;
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--task-id') {
    i++;
    continue;
  }
  if (!argv[i].startsWith('-')) {
    eventTypeIdx = i;
    break;
  }
}

const globalArgs = eventTypeIdx >= 0 ? argv.slice(0, eventTypeIdx) : argv;
const eventType = eventTypeIdx >= 0 ? argv[eventTypeIdx] : null;
const remainingArgs = eventTypeIdx >= 0 ? argv.slice(eventTypeIdx + 1) : [];

const { values: globalValues } = parseArgs({
  args: globalArgs,
  options: {
    'task-id': { type: 'string' },
  },
  strict: false,
});

const taskId = globalValues['task-id'];

if (!taskId) {
  console.error('ERROR: --task-id is required');
  process.exit(1);
}

if (!eventType) {
  console.error('ERROR: event_type positional argument is required');
  console.error('Usage: node report-event.js --task-id <id> <event_type> [--field value ...]');
  process.exit(1);
}

let handler;
switch (eventType) {
  case 'pipeline_check':
    handler = handlePipelineCheck;
    break;
  case 'build':
    handler = handleBuild;
    break;
  case 'pre_check':
    handler = handlePreCheck;
    break;
  case 'deploy_plan':
    handler = handleDeployPlan;
    break;
  case 'deploy_batch':
    handler = handleDeployBatch;
    break;
  default:
    console.error(`ERROR: Unknown event type: ${eventType}`);
    process.exit(1);
}

handler(taskId, remainingArgs)
  .then(result => {
    console.log(JSON.stringify(result, null, 2));
  })
  .catch(err => {
    console.error('ERROR:', err.message);
    process.exit(1);
  });
