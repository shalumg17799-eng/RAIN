/**
 * A test-only stand-in for `React.lazy` that starts the dynamic import at once
 * and lets a test wait for every import to finish.
 *
 * The render nets fingerprint server-rendered HTML. Behind a real `lazy()` that
 * HTML is the Suspense fallback until the import resolves and the real component
 * after, so a fingerprint would depend on how fast a module happened to load.
 * With this mock and `await settleLazy()` before drawing, every lazy boundary
 * is resolved and the fingerprint is the component itself, every run.
 *
 *   vi.mock('react', async (importOriginal) => {
 *     const actual = await importOriginal();
 *     const { createEagerLazy } = await import('@/test/eagerLazy');
 *     return { ...actual, lazy: createEagerLazy(actual.createElement) };
 *   });
 *
 * This module does not import React itself: it is loaded from inside the
 * `react` mock, so the real `createElement` is passed in.
 */
const pending = new Set();

export const createEagerLazy = (createElement) => function eagerLazy(factory) {
  let Component = null;
  let failure = null;
  const load = factory().then(
    (mod) => { Component = mod.default; },
    (err) => { failure = err; },
  );
  pending.add(load);
  load.finally(() => pending.delete(load));
  function EagerLazy(props) {
    if (failure) throw failure;
    if (!Component) throw load; // suspends, exactly like React.lazy while loading
    return createElement(Component, props);
  }
  return EagerLazy;
};

/** Resolves once every lazy import started so far (and any they start) has loaded. */
export async function settleLazy() {
  while (pending.size) await Promise.all([...pending]);
}
