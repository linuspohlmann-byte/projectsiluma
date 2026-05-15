import { cn } from '@/lib/cn';
import type { InputHTMLAttributes } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, className, id, ...props }: InputProps) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={inputId} className="text-sm font-medium text-[var(--text-secondary)]">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={cn(
          'min-h-11 w-full rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-[var(--fg)] placeholder:text-[var(--muted)] focus:border-[var(--accent)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-light)]',
          error && 'border-[var(--danger)]',
          className,
        )}
        {...props}
      />
      {error && <p className="text-sm text-[var(--danger)]">{error}</p>}
    </div>
  );
}
