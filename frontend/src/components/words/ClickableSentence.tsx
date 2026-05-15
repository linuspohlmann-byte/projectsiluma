const WORD_RE = /([\p{L}\p{M}'’-]+|[^\p{L}\p{M}\s]+|\s+)/gu;

export function ClickableSentence({
  text,
  onWordClick,
}: {
  text: string;
  onWordClick: (word: string) => void;
}) {
  const parts = text.match(WORD_RE) ?? [text];

  return (
    <p className="text-lg font-medium leading-relaxed">
      {parts.map((part, i) => {
        const isWord = /^[\p{L}\p{M}]/u.test(part);
        if (!isWord) return <span key={i}>{part}</span>;
        return (
          <button
            key={i}
            type="button"
            className="mx-0.5 rounded px-0.5 underline decoration-[var(--accent)] decoration-dotted underline-offset-4 hover:bg-[var(--accent)]/10"
            onClick={() => onWordClick(part.replace(/^[^\p{L}\p{M}]+|[^\p{L}\p{M}]+$/gu, ''))}
          >
            {part}
          </button>
        );
      })}
    </p>
  );
}
