import { cn } from '@/lib/cn';
import type { HTMLAttributes } from 'react';

export function Card({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
