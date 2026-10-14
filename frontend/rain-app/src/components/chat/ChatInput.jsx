import { useState, useRef, useEffect } from 'react';
import { Send, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function ChatInput({ onSend, disabled = false, placeholder, suggestions = [] }) {
  const [value, setValue] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const wrapperRef = useRef(null);
  const inputRef = useRef(null);

  const filtered = value.trim()
    ? suggestions.filter((s) => s.toLowerCase().includes(value.toLowerCase()))
    : suggestions;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!value.trim() || disabled) return;
    onSend(value.trim());
    setValue('');
    setShowSuggestions(false);
  };

  const handleSuggestionClick = (suggestion) => {
    onSend(suggestion);
    setValue('');
    setShowSuggestions(false);
    inputRef.current?.blur();
  };

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const hasSuggestions = filtered.length > 0 && !disabled;

  return (
    <div ref={wrapperRef} className="relative">
      {/* Suggestions dropdown */}
      <AnimatePresence>
        {showSuggestions && hasSuggestions && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
            transition={{ duration: 0.15 }}
            className="absolute bottom-full left-0 right-0 mb-2 bg-white rounded-xl border border-gray-200/80 overflow-hidden z-50"
            style={{ boxShadow: '0 4px 24px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.02)' }}
          >
            <div className="px-4 py-2.5 border-b border-gray-100/80 flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-[#003087]/60" />
              <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Suggested questions</span>
            </div>
            <ul className="max-h-[200px] overflow-y-auto py-1">
              {filtered.map((suggestion, idx) => (
                <li key={idx}>
                  <button
                    type="button"
                    onClick={() => handleSuggestionClick(suggestion)}
                    className="w-full text-left px-4 py-2.5 text-[13px] text-gray-600 hover:bg-[#003087]/[0.03] hover:text-[#003087] transition-colors cursor-pointer flex items-start gap-2.5"
                  >
                    <span className="w-1 h-1 rounded-full bg-[#003087]/25 mt-2 flex-shrink-0" />
                    <span className="leading-snug">{suggestion}</span>
                  </button>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input form with gradient border effect */}
      <div className={`rounded-2xl p-[1px] transition-all duration-300 ${
        isFocused
          ? 'bg-gradient-to-r from-[#003087]/30 via-[#003087]/15 to-[#003087]/30 shadow-[0_0_0_3px_rgba(0,48,135,0.08)]'
          : 'bg-gray-300/60 shadow-[0_1px_6px_rgba(0,0,0,0.06)]'
      }`}>
        <form
          onSubmit={handleSubmit}
          className="flex items-center gap-3 bg-white rounded-[15px] px-5 py-3"
        >
          <Sparkles className={`w-4 h-4 flex-shrink-0 transition-colors duration-200 ${
            isFocused ? 'text-[#003087]/50' : 'text-[#003087]/25'
          }`} />
          <input
            ref={inputRef}
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onFocus={() => { setIsFocused(true); setShowSuggestions(true); }}
            onBlur={() => setIsFocused(false)}
            placeholder={placeholder || "Ask anything about your members, signals, or operations..."}
            disabled={disabled}
            className="flex-1 text-sm text-gray-800 placeholder-gray-500 outline-none bg-transparent disabled:opacity-40"
          />
          <button
            type="submit"
            disabled={!value.trim() || disabled}
            className="w-9 h-9 rounded-xl bg-[#003087] flex items-center justify-center text-white hover:bg-[#002570] transition-all disabled:opacity-30 disabled:cursor-not-allowed flex-shrink-0 cursor-pointer shadow-sm hover:shadow-md"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>
    </div>
  );
}
