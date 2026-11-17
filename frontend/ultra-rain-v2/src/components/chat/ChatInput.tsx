import { useEffect, useId, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import { Send, Sparkles } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';

/**
 * The ask bar under every persona's conversation (workspace, chat drawer,
 * askable and signals-column pages). One bordered surface: the field, its
 * send button and a typeahead of suggested questions above it.
 *
 * Radii are concentric (the bar is `rounded-lg`, the button sits 8px in and
 * is `rounded-sm`), so the corners never show a seam. The typeahead is an
 * ARIA combobox: arrow keys move through it, Enter asks the highlighted
 * question, Escape closes it. A real <form> submits on Enter, which the demo
 * runner relies on, as it does on finding the field by its placeholder.
 */
export interface ChatInputProps {
  onSend: (text: string) => void;
  /** True while an answer is being written; the field and button rest. */
  disabled?: boolean;
  placeholder?: string;
  /** Questions offered as the user types; filtered by what they have typed. */
  suggestions?: string[];
}

const DEFAULT_PLACEHOLDER = 'Ask anything about your members, signals, or operations...';

export default function ChatInput({ onSend, disabled = false, placeholder, suggestions = [] }: ChatInputProps) {
  const [value, setValue] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();

  const query = value.trim().toLowerCase();
  const filtered = query ? suggestions.filter((s) => s.toLowerCase().includes(query)) : suggestions;
  const showList = open && filtered.length > 0 && !disabled;
  const canSend = !!value.trim() && !disabled;

  const send = (text: string) => {
    onSend(text);
    setValue('');
    setOpen(false);
    setActive(-1);
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (canSend) send(value.trim());
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setOpen(false);
      setActive(-1);
      return;
    }
    if (!filtered.length || disabled) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      setOpen(true);
      const step = e.key === 'ArrowDown' ? 1 : -1;
      setActive((i) => (i + step + filtered.length) % filtered.length);
    } else if (e.key === 'Enter' && showList && active >= 0) {
      e.preventDefault();
      send(filtered[active]);
      inputRef.current?.blur();
    }
  };

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const optionId = (i: number) => `${listId}-option-${i}`;

  return (
    <div ref={wrapperRef} className="relative">
      <AnimatePresence>
        {showList && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
            transition={{ duration: 0.15 }}
            className="absolute inset-x-0 bottom-full z-50 mb-2 overflow-hidden rounded-lg border border-border bg-surface shadow-lg"
          >
            <div className="flex items-center gap-2 border-b border-border-subtle px-4 py-2.5">
              <Sparkles className="h-3.5 w-3.5 text-brand" aria-hidden="true" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-text-subtle">Suggested questions</span>
            </div>
            <ul id={listId} role="listbox" aria-label="Suggested questions" className="max-h-60 overflow-y-auto py-1">
              {filtered.map((suggestion, i) => (
                <li
                  key={`${i}-${suggestion}`}
                  id={optionId(i)}
                  role="option"
                  aria-selected={i === active}
                  // Chosen on press, before the field blurs; the keyboard path is the field's own handler.
                  onMouseDown={(e) => {
                    e.preventDefault();
                    send(suggestion);
                    inputRef.current?.blur();
                  }}
                  onMouseEnter={() => setActive(i)}
                  className={`flex cursor-pointer items-start gap-2.5 px-4 py-2.5 text-[13px] leading-snug transition-colors ${
                    i === active ? 'bg-brand-subtle text-brand' : 'text-text-muted'
                  }`}
                >
                  <span className={`mt-[7px] h-1 w-1 flex-shrink-0 rounded-full ${i === active ? 'bg-brand' : 'bg-text-subtle'}`} aria-hidden="true" />
                  <span>{suggestion}</span>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>

      <form
        onSubmit={handleSubmit}
        className={`group flex items-center gap-2 rounded-lg border py-2 pl-3.5 pr-2 shadow-sm transition-[border-color,box-shadow] duration-200 sm:gap-3 sm:pl-4 ${
          disabled
            ? 'border-border-subtle bg-surface-2'
            : 'border-border bg-surface hover:border-brand/30 focus-within:border-brand/50 focus-within:ring-[3px] focus-within:ring-brand-ring/40'
        }`}
      >
        <Sparkles
          className="h-4 w-4 flex-shrink-0 text-text-subtle transition-colors duration-200 group-focus-within:text-brand"
          aria-hidden="true"
        />
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || DEFAULT_PLACEHOLDER}
          aria-label={placeholder || DEFAULT_PLACEHOLDER}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={showList}
          aria-controls={listId}
          aria-activedescendant={showList && active >= 0 ? optionId(active) : undefined}
          disabled={disabled}
          className="min-w-0 flex-1 text-ellipsis bg-transparent py-1.5 text-sm text-text outline-none placeholder:text-text-muted disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          disabled={!canSend}
          aria-label="Send"
          className="grid h-9 w-9 flex-shrink-0 cursor-pointer place-items-center rounded-sm bg-brand text-brand-fg shadow-sm transition-colors duration-200 hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-text-subtle disabled:shadow-none"
        >
          <Send className="h-4 w-4" aria-hidden="true" />
        </button>
      </form>
    </div>
  );
}
