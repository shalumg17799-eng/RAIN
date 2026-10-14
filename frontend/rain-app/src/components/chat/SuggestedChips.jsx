import { motion } from 'framer-motion';

export default function SuggestedChips({ chips, onChipClick }) {
  if (!chips || chips.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: 0.1 }}
      className="flex flex-wrap gap-2 pl-11"
    >
      {chips.map((chip, idx) => (
        <button
          key={idx}
          onClick={() => onChipClick(chip)}
          className="px-4 py-2 rounded-full text-sm font-medium border border-[#003087]/20 text-[#003087] bg-white hover:bg-[#003087]/5 hover:border-[#003087]/40 transition-all cursor-pointer shadow-sm"
        >
          {chip}
        </button>
      ))}
    </motion.div>
  );
}
