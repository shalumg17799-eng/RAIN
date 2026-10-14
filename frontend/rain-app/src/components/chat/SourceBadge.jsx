const sourceColors = {
  'All connected sources':              { dot: 'bg-gray-400',   text: 'text-gray-500' },
};

const defaultColor = { dot: 'bg-gray-400', text: 'text-gray-500' };

export default function SourceBadge({ source }) {
  const colors = sourceColors[source] || defaultColor;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[10px] font-medium ${colors.text} bg-gray-50 border border-gray-100/60`}>
      <span className={`w-1.5 h-1.5 rounded-full ${colors.dot}`} />
      {source}
    </span>
  );
}
