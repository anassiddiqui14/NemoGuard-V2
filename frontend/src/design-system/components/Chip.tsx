import React from 'react';

/*
 * NemoGuard design-system Chip primitive.
 *
 * WHY THIS EXISTS (UI Modernization Spec, Section 67):
 * The spec explicitly separates three distinct chip/badge concerns that
 * should NOT share styling:
 *   1. Semantic status badges (severityPill/statusBadge in shared.tsx --
 *      already correct, untouched here)
 *   2. Neutral metadata chips (plain informational tags)
 *   3. Interactive filter/selection chips (toggleable, with a
 *      selected/unselected visual state)
 *
 * Verified via grep that the THIRD category -- interactive selection
 * chips -- was hand-duplicated with the identical recipe
 * (`selected ? bg-primary/20 ring-primary/35 : bg-white/[0.03]
 * ring-white/[0.06] hover:...`) in both TeamsRoutesTab.tsx (notification
 * channel toggles) and ModelEvaluationTab.tsx (model picker). This
 * consolidates that pattern into one primitive rather than a third
 * hand-copy the next time an interactive chip selector is needed.
 */
export interface ChipProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'className'> {
    selected?: boolean;
    mono?: boolean;
    className?: string;
}

export function Chip({ selected = false, mono = false, className = '', children, ...rest }: ChipProps) {
    return (
        <button
            type="button"
            aria-pressed={selected}
            className={`press-scale focus-ring text-[11px] font-semibold px-2.5 py-1 rounded-full ring-1 transition-colors ${mono ? 'font-mono' : ''} ${selected
                ? 'bg-primary/20 text-primary ring-primary/35'
                : 'bg-white/[0.03] text-text-muted ring-white/[0.06] hover:text-text-secondary hover:bg-white/[0.05]'
                } ${className}`}
            {...rest}
        >
            {children}
        </button>
    );
}
