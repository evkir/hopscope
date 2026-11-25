'use strict';
// hopscope lab recorder, no deps.
// ROLE=tap:  record POST body to $SINK_DIR/$HOP.jsonl, forward request to $UPSTREAM.
// ROLE=sink: record POST body, answer /tasks/send like a DVAA worker (never follows context).
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const { ROLE, UPSTREAM = '', SINK_DIR = '/out' } = process.env;
const HOP = process.env.HOP || ROLE;
const PORT = Number(process.env.PORT);
const MAX_BODY = 256 * 1024;

if (!['tap', 'sink'].includes(ROLE) || !Number.isInteger(PORT) || PORT <= 0) {
  console.error('recorder: ROLE=tap|sink and PORT required');
  process.exit(2);
}
if (ROLE === 'tap' && !UPSTREAM) {
  console.error('recorder: UPSTREAM required for ROLE=tap');
  process.exit(2);
}

const record = (entry) =>
  fs.appendFileSync(path.join(SINK_DIR, `${HOP}.jsonl`), JSON.stringify(entry) + '\n');

const readBody = (req) =>
  new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', (c) => {
      size += c.length;
      if (size > MAX_BODY) {
        reject(new Error('body too large'));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });

const send = (res, status, obj) => {
  const body = JSON.stringify(obj);
  res.writeHead(status, {
    'content-type': 'application/json',
    'content-length': Buffer.byteLength(body),
  });
  res.end(body);
};

async function handle(req, res) {
  let raw;
  try {
    raw = await readBody(req);
  } catch {
    return send(res, 413, { error: 'body too large' });
  }
  let body = null;
  if (req.method === 'POST') {
    try {
      body = JSON.parse(raw);
    } catch {
      return send(res, 400, { error: 'bad json' });
    }
    record({ ts: new Date().toISOString(), hop: HOP, role: ROLE, path: req.url, body });
  }
  if (ROLE === 'tap') {
    const isPost = req.method === 'POST';
    const up = await fetch(UPSTREAM + req.url, {
      method: req.method,
      headers: isPost ? { 'content-type': 'application/json' } : {},
      body: isPost ? raw : undefined,
    });
    const text = await up.text();
    res.writeHead(up.status, {
      'content-type': up.headers.get('content-type') || 'application/json',
    });
    return res.end(text);
  }
  if (req.method === 'POST' && req.url === '/tasks/send') {
    return send(res, 200, {
      taskId: body?.id ?? null,
      status: 'completed',
      result: {
        summary: 'hopscope sink: task recorded',
        findings: [],
        executedWith: body?.permissions ?? null,
      },
    });
  }
  if (req.method === 'GET' && req.url === '/.well-known/agent.json') {
    return send(res, 200, { name: 'hopscope-sink', version: '0.2.0', capabilities: ['record'] });
  }
  return send(res, 404, { error: 'not found' });
}

http
  .createServer((req, res) => {
    handle(req, res).catch((e) => {
      if (res.headersSent) return res.destroy();
      return send(res, 502, { error: String(e?.message || e) });
    });
  })
  .listen(PORT, () => console.log(`recorder ${ROLE} hop=${HOP} on :${PORT}`));
