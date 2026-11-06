// ============================================================
// GUIDED DEMO RUNNER — v6 (Persona-driven)
// Reads active persona from window.__activePersona.
// Follows persona-specific Golden Path through capabilities.
// Natural pacing with Pause / Resume / Stop controls.
// ============================================================

import { getDemoSteps } from './personaDemoSteps';
import { devError, devInfo, devWarn } from '@core/log';
import { now } from '../core/clock';

let isStopped = false;
let isPaused = false;
let isRunning = false;
let onStepChange = null;
let onComplete = null;
let onStopped = null;
let onPauseChange = null;

let totalSteps = 0;
let currentStep = 0;

// ── Aria-live announcer ──────────────────────────────────────
let announcer = null;
function getAnnouncer() {
  if (!announcer) {
    announcer = document.createElement('div');
    announcer.setAttribute('aria-live', 'polite');
    announcer.setAttribute('aria-atomic', 'true');
    announcer.className = 'sr-only';
    announcer.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);';
    document.body.appendChild(announcer);
  }
  return announcer;
}
function announce(text) { getAnnouncer().textContent = text; }

// ── DOM Helpers ──────────────────────────────────────────────

/** Pause-aware sleep. Checks for stop/pause every 100ms. */
function sleep(ms) {
  return new Promise((resolve, reject) => {
    let elapsed = 0;
    const tick = () => {
      if (isStopped) { reject(new Error('__DEMO_STOPPED__')); return; }
      if (isPaused) {
        setTimeout(tick, 100);
        return;
      }
      elapsed += 100;
      if (elapsed >= ms) { resolve(); return; }
      setTimeout(tick, 100);
    };
    setTimeout(tick, 100);
  });
}

function checkStopped() { if (isStopped) throw new Error('__DEMO_STOPPED__'); }

/** Wait while paused, then check stopped. */
async function checkPausedAndStopped() {
  while (isPaused && !isStopped) {
    await new Promise(r => setTimeout(r, 100));
  }
  checkStopped();
}

/** Wait for a capability badge to appear in the chat, click it, then wait for user to dismiss the modal. */
async function clickCapabilityBadge(capabilityName) {
  const start = now();
  let badge = null;
  while (now() - start < 10000) {
    await checkPausedAndStopped();
    badge = document.querySelector(`[data-capability-badge="${capabilityName}"]`);
    if (badge) break;
    await new Promise(r => setTimeout(r, 200));
  }
  if (!badge) {
    devWarn(`[DEMO]   ↳ Capability badge "${capabilityName}" not found — skipping`);
    return;
  }

  devInfo(`[DEMO]   ↳ Opening capability: "${capabilityName}"`);
  const pk = Object.keys(badge).find(k => k.startsWith('__reactProps'));
  if (pk && badge[pk]?.onClick) badge[pk].onClick({ preventDefault() {}, stopPropagation() {} });
  else badge.click();
  await sleep(500);

  const continueBtn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Continue');
  if (continueBtn) {
    devInfo(`[DEMO]   ↳ Capability: "${capabilityName}" — waiting for user to click Continue`);
    while (true) {
      if (isStopped) throw new Error('__DEMO_STOPPED__');
      const stillOpen = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Continue');
      if (!stillOpen) break;
      await new Promise(r => setTimeout(r, 200));
    }
    devInfo(`[DEMO]   ↳ Capability: "${capabilityName}" — user dismissed modal`);
    await sleep(400);
  }
}

/** Wait for typing indicator to disappear. */
async function waitForTypingDone(timeout = 15000) {
  await sleep(600);
  const start = now();
  while (now() - start < timeout) {
    await checkPausedAndStopped();
    const grayDots = document.querySelectorAll('.typing-dot');
    if (grayDots.length === 0) return;
    await new Promise(r => setTimeout(r, 150));
  }
}

/** Wait for a button containing partial text to appear, then click it. */
async function waitAndClickContaining(partial, timeout = 12000) {
  const start = now();
  while (now() - start < timeout) {
    await checkPausedAndStopped();
    const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim().includes(partial));
    if (btn) {
      const pk = Object.keys(btn).find(k => k.startsWith('__reactProps'));
      if (pk && btn[pk]?.onClick) btn[pk].onClick({ preventDefault() {}, stopPropagation() {} });
      else btn.click();
      await sleep(300);
      return btn;
    }
    await new Promise(r => setTimeout(r, 200));
  }
  throw new Error(`Timed out waiting for button containing: "${partial}"`);
}

/** Click first Confirm button. */
async function clickFirstConfirm() {
  await checkPausedAndStopped();
  const start = now();
  while (now() - start < 8000) {
    const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Confirm');
    if (btn) {
      const pk = Object.keys(btn).find(k => k.startsWith('__reactProps'));
      if (pk && btn[pk]?.onClick) btn[pk].onClick({ preventDefault() {}, stopPropagation() {} });
      else btn.click();
      await sleep(300);
      return;
    }
    await new Promise(r => setTimeout(r, 200));
  }
  throw new Error('No Confirm button found');
}

/** Submit a query via input form. */
async function submitQuery(query, hint = 'Ask') {
  await checkPausedAndStopped();
  const input = [...document.querySelectorAll('input')].find(i => i.placeholder.includes(hint)) || document.querySelector('input');
  if (!input) throw new Error('No input');
  const nativeSet = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  nativeSet.call(input, query);
  input.dispatchEvent(new Event('input', { bubbles: true }));
  await sleep(200);
  const form = input.closest('form');
  if (form) form.requestSubmit();
  await sleep(400);
}

/** Close chat drawer X button. */
async function closeDrawer() {
  await sleep(400);
  const x = [...document.querySelectorAll('button')].find(b => b.querySelector('.lucide-x') && b.closest('.fixed'));
  if (x) { x.click(); await sleep(400); }
}

/** Navigate via React Router. */
async function navigateTo(path) {
  await checkPausedAndStopped();
  if (window.demoNavigate) window.demoNavigate(path);
  else window.location.href = path;
  await sleep(1200);
}

// ── Action interpreter ──────────────────────────────────────
async function runAction(action) {
  switch (action.type) {
    case 'navigate': return navigateTo(action.path);
    case 'waitTyping': return waitForTypingDone();
    case 'sleep': return sleep(action.ms);
    case 'clickCapability': return clickCapabilityBadge(action.name);
    case 'clickChip': return waitAndClickContaining(action.partial);
    case 'confirmAction': return clickFirstConfirm();
    case 'submitQuery': return submitQuery(action.query, action.hint);
    case 'closeDrawer': return closeDrawer();
    default: devWarn(`[DEMO] Unknown action type: ${action.type}`);
  }
}

// ── Step Runner ──────────────────────────────────────────────

function logStep(num, label) {
  currentStep = num;
  devInfo(`[DEMO] Step ${num}/${totalSteps}: ${label}`);
  announce(`Demo step ${num}: ${label}`);
  if (onStepChange) onStepChange(num, totalSteps, label);
}

async function runStepDef(num, stepDef) {
  await checkPausedAndStopped();
  logStep(num, stepDef.label);
  try {
    for (const action of stepDef.actions) {
      await runAction(action);
    }
  } catch (err) {
    if (err.message === '__DEMO_STOPPED__') throw err;
    devWarn(`[DEMO] Step ${num} skipped: ${err.message}`);
  }
}

// ── Demo Sequence ────────────────────────────────────────────

async function runDemo() {
  const personaId = window.__activePersona || 'ops';
  const steps = getDemoSteps(personaId);
  totalSteps = steps.length;

  devInfo(`[DEMO] ▶ Running demo for persona: ${personaId} (${totalSteps} steps)`);

  for (let i = 0; i < steps.length; i++) {
    await runStepDef(i + 1, steps[i]);
  }
}

// ── Public API ───────────────────────────────────────────────

const DemoRunner = {
  get isRunning() { return isRunning; },
  get isPaused() { return isPaused; },
  get totalSteps() { return totalSteps; },
  get currentStep() { return currentStep; },

  /** Return total steps for the given persona (or active persona). */
  getTotalSteps(personaId) {
    const pid = personaId || window.__activePersona || 'ops';
    return getDemoSteps(pid).length;
  },

  subscribe({ onStep, onDone, onStop, onPause }) {
    onStepChange = onStep || null;
    onComplete = onDone || null;
    onStopped = onStop || null;
    onPauseChange = onPause || null;
  },

  async start() {
    if (isRunning) return;
    isStopped = false;
    isPaused = false;
    isRunning = true;
    currentStep = 0;

    const personaId = window.__activePersona || 'ops';
    totalSteps = getDemoSteps(personaId).length;

    devInfo('[DEMO] ▶ Starting guided demo...');
    announce('Guided demo starting');

    const keyHandler = (e) => {
      if (e.key === 'Escape') DemoRunner.stop();
      if (e.key === ' ' && isRunning) {
        e.preventDefault();
        if (isPaused) DemoRunner.resume();
        else DemoRunner.pause();
      }
    };
    window.addEventListener('keydown', keyHandler);

    try {
      await runDemo();
      if (!isStopped) {
        devInfo('[DEMO] ✅ Demo complete!');
        announce('Guided demo complete');
        if (onComplete) onComplete();
      }
    } catch (err) {
      if (err.message === '__DEMO_STOPPED__') {
        devInfo('[DEMO] ⏹ Demo stopped by user');
        announce('Guided demo stopped');
        if (onStopped) onStopped();
      } else {
        devError('[DEMO] ❌ Demo error:', err);
        if (onComplete) onComplete();
      }
    } finally {
      isRunning = false;
      isPaused = false;
      window.removeEventListener('keydown', keyHandler);
    }
  },

  pause() {
    if (!isRunning || isPaused) return;
    devInfo('[DEMO] ⏸ Demo paused');
    isPaused = true;
    announce('Guided demo paused');
    if (onPauseChange) onPauseChange(true);
  },

  resume() {
    if (!isRunning || !isPaused) return;
    devInfo('[DEMO] ▶ Demo resumed');
    isPaused = false;
    announce('Guided demo resumed');
    if (onPauseChange) onPauseChange(false);
  },

  stop() {
    if (!isRunning) return;
    devInfo('[DEMO] ⏹ Stopping demo...');
    isStopped = true;
    isPaused = false;
  },
};

export default DemoRunner;
