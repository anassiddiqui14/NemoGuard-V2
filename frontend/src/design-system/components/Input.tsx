import React from 'react';

/*
 * NemoGuard design-system Input/Select primitives.
 *
 * WHY THIS EXISTS (UI Modernization Spec, Section 68):
 * Confirmed via grep: the exact recipe
 * `rounded-lg px-3 py-2 text-[12.5px] bg-white/[0.03] ring-1
 * ring-white/[0.06] text-text-primary placeholder:text-text-muted
 * focus:outline-none focus:ring-primary/50` was hand-duplicated 12 times
 * across the Admin tabs alone (TeamsRoutesTab, ModelEvaluationTab, and
 * others) for text inputs, with the <select> variant repeating the same
 * classes minus the placeholder styling. This consolidates both into one
 * place so every form field in the app shares identical height, padding,
 * border, and focus treatment by construction.
 */

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
    ({ className = '', ...rest }, ref) => (
        <input
            ref={ref}
            className={`w-full rounded-lg px-3 py-2 text-[12.5px] bg-white/[0.03] ring-1 ring-white/[0.06] text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-primary/50 transition-all ${className}`}
            {...rest}
        />
    ),
);
Input.displayName = 'Input';

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
    ({ className = '', children, ...rest }, ref) => (
        <select
            ref={ref}
            className={`w-full rounded-lg px-3 py-2 text-[12.5px] bg-white/[0.03] ring-1 ring-white/[0.06] text-text-primary focus:outline-none focus:ring-primary/50 transition-all ${className}`}
            {...rest}
        >
            {children}
        </select>
    ),
);
Select.displayName = 'Select';

/** Label + description + Input/Select, matching the hand-rolled `<label className="text-[11px] text-text-muted">` pattern used throughout Admin forms. */
export function FormField({ label, children, className = '' }: { label: string; children: React.ReactNode; className?: string }) {
    return (
        <label className={`block text-[11px] text-text-muted ${className}`}>
            {label}
            <div className="mt-1">{children}</div>
        </label>
    );
}
