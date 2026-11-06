/**
 * The dashed connector arrows between layers of the capability deep-dive
 * diagrams. Shared by all six diagrams, which each used to define these inside
 * their render (a new component type every render, so React remounted them).
 */

/** Data flows up a layer. */
export function UpArrow() {
  return (
    <div className="flex justify-center flex-shrink-0" style={{ height: 'min(2.2vh, 20px)' }}>
      <svg width="14" height="100%" viewBox="0 0 14 24" fill="none" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">
        <polygon points="7,0 2,8 12,8" fill="var(--color-brand)" />
        <line x1="7" y1="7" x2="7" y2="24" stroke="var(--color-brand)" strokeWidth="1.8" strokeDasharray="4 3" />
      </svg>
    </div>
  );
}

/** Actions flow down a layer. */
export function DownArrow() {
  return (
    <div className="flex justify-center flex-shrink-0" style={{ height: 'min(2.2vh, 20px)' }}>
      <svg width="14" height="100%" viewBox="0 0 14 24" fill="none" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">
        <line x1="7" y1="0" x2="7" y2="17" stroke="var(--color-brand)" strokeWidth="1.8" strokeDasharray="4 3" />
        <polygon points="7,24 2,16 12,16" fill="var(--color-brand)" />
      </svg>
    </div>
  );
}
