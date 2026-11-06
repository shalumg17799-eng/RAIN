import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, Search } from 'lucide-react';

/**
 * KPI kit select: one consistent dropdown for filters (scope, measure, sort,
 * goal). The native <select> renders its arrow flush against the border and
 * its menu in the operating system's style, so filters looked different on
 * every screen; this draws the trigger and the list in the design tokens.
 *
 * Accessible listbox pattern: the trigger is a button with aria-haspopup and
 * aria-expanded; the list is role="listbox" with role="option" children and
 * aria-activedescendant. Keyboard: Enter / Space / Arrow keys open it; Arrow
 * keys, Home and End move; Enter selects; Escape closes and returns focus;
 * Tab closes; typing jumps to the next match. Long lists get a search box.
 *
 * Props: label, labelPosition 'inline' | 'stacked' | 'hidden', value,
 * onChange(value), options [{ value, label }] or groups [{ label, options }],
 * searchable (default: more than 12 options), width (class), disabled,
 * placeholder, className.
 */
export default function Select({ label, labelPosition = 'inline', value, onChange, options, groups, searchable, width = 'w-56', disabled = false, placeholder = 'Select…', className = '' }) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '');
  const labelId = `sel-l-${uid}`;
  const listId = `sel-list-${uid}`;
  const triggerRef = useRef(null);
  const listRef = useRef(null);
  const searchRef = useRef(null);
  const wrapRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [up, setUp] = useState(false);
  const typed = useRef({ text: '', at: 0 });

  const sections = useMemo(() => groups ?? [{ label: null, options: options ?? [] }], [groups, options]);
  const flat = useMemo(() => sections.flatMap((g) => g.options), [sections]);
  const canSearch = searchable ?? flat.length > 12;
  const q = query.trim().toLowerCase();
  // The options left after the search, each with its position in the flat list (for aria-activedescendant).
  const visible = useMemo(() => {
    let n = 0;
    return sections
      .map((g) => ({ ...g, options: (q ? g.options.filter((o) => o.label.toLowerCase().includes(q)) : g.options).map((o) => ({ ...o, i: n++ })) }))
      .filter((g) => g.options.length);
  }, [sections, q]);
  const visibleFlat = useMemo(() => visible.flatMap((g) => g.options), [visible]);
  const current = flat.find((o) => o.value === value);
  const optId = (i) => `${listId}-o${i}`;

  const openList = () => {
    if (disabled) return;
    const r = triggerRef.current?.getBoundingClientRect();
    setUp(!!r && r.bottom + 340 > window.innerHeight && r.top > 360);
    setQuery('');
    setActive(Math.max(0, flat.findIndex((o) => o.value === value)));
    setOpen(true);
  };
  const close = (refocus = true) => {
    setOpen(false);
    if (refocus) triggerRef.current?.focus();
  };
  const choose = (o) => {
    if (o && o.value !== value) onChange?.(o.value);
    close();
  };

  // Focus the search box or the list when it opens; keep the active option in view.
  useEffect(() => {
    if (!open) return;
    (canSearch ? searchRef.current : listRef.current)?.focus();
  }, [open, canSearch]);
  useEffect(() => {
    if (!open) return;
    listRef.current?.querySelector(`#${CSS.escape(optId(active))}`)?.scrollIntoView?.({ block: 'nearest' });
  }, [active, open]); // eslint-disable-line react-hooks/exhaustive-deps

  // A click outside closes it.
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => {
      if (!wrapRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener('pointerdown', onDown);
    return () => document.removeEventListener('pointerdown', onDown);
  }, [open]);

  const onListKey = (e) => {
    const n = visibleFlat.length;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(n - 1, a + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
    else if (e.key === 'Home') { e.preventDefault(); setActive(0); }
    else if (e.key === 'End') { e.preventDefault(); setActive(n - 1); }
    else if (e.key === 'Enter' || (e.key === ' ' && !canSearch)) { e.preventDefault(); choose(visibleFlat[active]); }
    else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); }
    else if (e.key === 'Tab') { close(false); }
    else if (!canSearch && e.key.length === 1 && /\S/.test(e.key)) {
      // Typeahead: letters typed within a second build one search.
      const now = e.timeStamp;
      typed.current = { text: (now - typed.current.at < 1000 ? typed.current.text : '') + e.key.toLowerCase(), at: now };
      const i = visibleFlat.findIndex((o) => o.label.toLowerCase().startsWith(typed.current.text));
      if (i >= 0) setActive(i);
    }
  };

  const onTriggerKey = (e) => {
    if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
      e.preventDefault();
      openList();
    }
  };

  const labelEl = label ? (
    <span id={labelId} className={labelPosition === 'hidden' ? 'sr-only' : 'flex-shrink-0 text-[12px] font-semibold text-text-muted'}>
      {label}
    </span>
  ) : null;

  return (
    <div ref={wrapRef} className={`relative ${labelPosition === 'stacked' ? 'flex flex-col gap-1' : 'inline-flex items-center gap-2'} max-w-full ${className}`}>
      {labelEl}
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-labelledby={label ? `${labelId} ${listId}-v` : undefined}
        onClick={() => (open ? close() : openList())}
        onKeyDown={onTriggerKey}
        className={`relative flex h-9 min-w-0 max-w-full items-center rounded-lg border bg-surface pl-3 pr-9 text-left text-[12.5px] font-medium text-text shadow-sm transition-colors ${width} ${open ? 'border-brand ring-2 ring-brand/20' : 'border-border hover:border-brand/40'} focus-visible:border-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/25 disabled:cursor-not-allowed disabled:opacity-60`}
      >
        <span id={`${listId}-v`} className="truncate">
          {current?.label ?? placeholder}
        </span>
        <ChevronDown className={`pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>
      {open && (
        <div
          className={`absolute z-50 min-w-full overflow-hidden rounded-xl border border-border bg-surface shadow-lg ${labelPosition === 'inline' && label ? 'right-0' : 'left-0'} ${up ? 'bottom-full mb-1' : 'top-full mt-1'}`}
          style={{ minWidth: triggerRef.current?.offsetWidth }}
        >
          {canSearch && (
            <div className="flex items-center gap-2 border-b border-border-subtle px-3 py-2">
              <Search className="h-3.5 w-3.5 flex-shrink-0 text-text-muted" aria-hidden="true" />
              <input
                ref={searchRef}
                type="text"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActive(0);
                }}
                onKeyDown={onListKey}
                placeholder="Search…"
                aria-label={`Search ${label ?? 'options'}`}
                aria-controls={listId}
                aria-activedescendant={visibleFlat.length ? optId(active) : undefined}
                className="w-full bg-transparent text-[12.5px] text-text outline-none placeholder:text-text-subtle"
              />
            </div>
          )}
          <ul
            ref={listRef}
            id={listId}
            role="listbox"
            tabIndex={-1}
            aria-labelledby={label ? labelId : undefined}
            aria-activedescendant={!canSearch && visibleFlat.length ? optId(active) : undefined}
            onKeyDown={onListKey}
            className="max-h-72 overflow-y-auto py-1 outline-none"
          >
            {visible.map((g) => (
              <li key={g.label ?? 'all'} role="presentation">
                {g.label && <p className="px-3 pb-1 pt-2 text-[10.5px] font-bold uppercase tracking-wider text-text-subtle">{g.label}</p>}
                <ul role={g.label ? 'group' : 'presentation'} aria-label={g.label ?? undefined}>
                  {g.options.map((o) => {
                    const { i } = o;
                    const selected = o.value === value;
                    return (
                      // Keyboard selection is handled on the listbox (aria-activedescendant); a click picks directly.
                      // eslint-disable-next-line jsx-a11y/click-events-have-key-events
                      <li
                        key={o.value}
                        id={optId(i)}
                        role="option"
                        aria-selected={selected}
                        onPointerEnter={() => setActive(i)}
                        onClick={() => choose(o)}
                        className={`flex cursor-pointer items-center gap-2 px-3 py-1.5 text-[12.5px] ${i === active ? 'bg-brand/[0.08] text-text' : 'text-text'} ${selected ? 'font-semibold' : ''}`}
                      >
                        <Check className={`h-3.5 w-3.5 flex-shrink-0 ${selected ? 'text-brand' : 'invisible'}`} aria-hidden="true" />
                        <span className="min-w-0 truncate">{o.label}</span>
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
            {!visibleFlat.length && <li className="px-3 py-2 text-[12px] text-text-muted">No matches</li>}
          </ul>
        </div>
      )}
    </div>
  );
}
