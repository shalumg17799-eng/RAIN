#!/usr/bin/env node
/**
 * Lint ratchet — eslint problem counts per rule may only go down.
 *
 *   node scripts/lint-ratchet.mjs           compare with lint-baseline.json, exit 1 if any rule rose
 *   node scripts/lint-ratchet.mjs --update  record the current counts as the new ceiling
 *
 * `npm run lint` still reports every problem; this answers the narrower question
 * a reviewer asks of a change: did it add any?
 */
import { ESLint } from 'eslint';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const APP = join(dirname(fileURLToPath(import.meta.url)), '..');
const BASELINE = join(APP, 'lint-baseline.json');

const eslint = new ESLint({ cwd: APP });
const results = await eslint.lintFiles(['.']);

const counts = {};
let errors = 0;
let warnings = 0;
for (const r of results) {
  for (const m of r.messages) {
    const key = `${m.severity === 2 ? 'error' : 'warn'}:${m.ruleId || 'unused-directive'}`;
    counts[key] = (counts[key] || 0) + 1;
    if (m.severity === 2) errors += 1; else warnings += 1;
  }
}
const sorted = Object.fromEntries(Object.entries(counts).sort(([a], [b]) => a.localeCompare(b)));

if (process.argv.includes('--update')) {
  writeFileSync(BASELINE, `${JSON.stringify({ errors, warnings, rules: sorted }, null, 2)}\n`);
  console.log(`lint baseline: ${errors} errors, ${warnings} warnings`);
  process.exit(0);
}

const base = existsSync(BASELINE) ? JSON.parse(readFileSync(BASELINE, 'utf8')) : { rules: {} };
const rose = Object.entries(sorted).filter(([k, v]) => v > (base.rules[k] || 0));
console.log(`lint: ${errors} errors, ${warnings} warnings (baseline ${base.errors ?? '?'} / ${base.warnings ?? '?'})`);
if (rose.length) {
  for (const [k, v] of rose) console.log(`  ✗ ${k}: ${v} (baseline ${base.rules[k] || 0})`);
  console.log('Run `npx eslint .` to see where.');
  process.exit(1);
}
const fell = Object.entries(base.rules).filter(([k, v]) => (sorted[k] || 0) < v);
if (fell.length) console.log(`  ↓ ${fell.length} rule count(s) fell — run with --update to lock them in.`);
